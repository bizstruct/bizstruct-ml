"""scripts/e2e_smoke.py against a mocked be: the polling loop, a failing project, a timeout and the checks."""

import copy
import importlib.util
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import httpx
import pytest
from bizstruct_domain.schemas import ConsistencyReport, ConsistencyViolation, Stage
from bizstruct_domain.schemas import StageErrorCode

from bizstruct_ml.judge.fake import FakeJudgeModel
from tests.support.fake_backend import FakeBackend
from tests.support.projects import NO_FINDINGS, ONE, SPLIT_IN_TWO, THREE_IN_ONE_MULTI_SIDED, scripted_llm, stage_runner

SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"
IDEA = "An app that delivers boxes of fresh produce from local farms to busy city parents."
PASSWORD = "smoke-password-1234"
TOKEN = "tok-abc-secret-value"


@pytest.fixture(scope="module")
def smoke():
    spec = importlib.util.spec_from_file_location("e2e_smoke", SCRIPTS / "e2e_smoke.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules["e2e_smoke"] = module
    spec.loader.exec_module(module)
    return module


# --------------------------------------------------------------------------- a project as be's public API serves it


def public_project(backend: FakeBackend, *, status: str = "completed", project_id: str = "p-1") -> dict:
    """The rows of a finished fake-backend project in the shape of GET /api/projects/{id}."""
    start = datetime(2026, 10, 11, 12, 0, tzinfo=timezone.utc)
    rows = []
    for n, row in enumerate(backend.rows.values()):
        rows.append(
            {
                "id": row.id,
                "stage": row.stage.value,
                "instanceIndex": row.instance_index,
                "status": row.status.value,
                "refs": {stage.value: ids for stage, ids in row.refs.items()},
                "attemptId": row.attempt_id,
                "retryCount": row.retry_count,
                "error": None,
                "consistency": row.consistency.model_dump(mode="json") if row.consistency else None,
                "artifacts": [a.model_dump(mode="json") for a in row.artifacts],
                "startedAt": (start + timedelta(seconds=n)).isoformat(),
                "finishedAt": (start + timedelta(seconds=n + 2.5)).isoformat(),
            }
        )
    return {
        "id": project_id,
        "title": "Smoke",
        "idea": IDEA,
        "language": "en",
        "enabledOptional": [],
        "autoApprove": True,
        "status": status,
        "rows": rows,
    }


async def finished(shape, enabled=()) -> dict:
    backend = FakeBackend(through=Stage.PITCH, enabled_optional=list(enabled))
    await backend.run_to_completion(stage_runner(scripted_llm(shape, scores=(100, 90, 95)), FakeJudgeModel([NO_FINDINGS])))
    return public_project(backend)


class FakeBe:
    """Serves the public endpoints the smoke script calls; GET answers come from a queue of (status, body)."""

    def __init__(self, polls: list[tuple[int, dict | None]], *, user_status: int = 201, login_status: int = 200, create_status: int = 201):
        self.polls = list(polls)
        self.user_status, self.login_status, self.create_status = user_status, login_status, create_status
        self.requests: list[httpx.Request] = []
        self.created_body: dict | None = None
        self.logins = 0

    def handler(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        path = request.url.path
        if request.method == "POST" and path == "/api/users/":
            return httpx.Response(self.user_status, json={})
        if request.method == "POST" and path == "/api/auth/login":
            self.logins += 1
            return httpx.Response(self.login_status, json={"access_token": f"{TOKEN}-{self.logins}", "refresh_token": "r"})
        if request.method == "POST" and path == "/api/generation":
            self.created_body = json.loads(request.content)
            running = {"id": "p-1", "status": "running", "rows": []}
            return httpx.Response(self.create_status, json=running)
        if request.method == "GET" and path == "/api/projects/p-1":
            status, body = self.polls.pop(0) if len(self.polls) > 1 else self.polls[0]
            return httpx.Response(status, json=body or {})
        return httpx.Response(404)

    def client(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(base_url="http://be.test", transport=httpx.MockTransport(self.handler))


class Clock:
    """A fake clock that advances only when the script sleeps."""

    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        return self.now

    async def sleep(self, seconds: float) -> None:
        self.now += max(seconds, 0.001)


async def run(smoke, be: FakeBe, tmp_path, *, timeout=60, enabled=(), clock: Clock | None = None, **extra):
    clock = clock or Clock()
    lines: list[str] = []
    async with be.client() as client:
        outcome = await smoke.run_smoke(
            client,
            email="smoke@example.com",
            password=PASSWORD,
            idea=IDEA,
            language="en",
            timeout=timeout,
            enabled_optional=list(enabled),
            dump_dir=tmp_path / "dumps",
            interval=5,
            sleep=clock.sleep,
            clock=clock,
            log=lines.append,
            **extra,
        )
    return outcome, lines, clock


def running(project: dict) -> dict:
    return {**project, "status": "running", "rows": project["rows"][:2]}


# --------------------------------------------------------------------------- the happy path


@pytest.mark.parametrize("shape,canvases", [(ONE, 1), (THREE_IN_ONE_MULTI_SIDED, 1), (SPLIT_IN_TWO, 2)], ids=["one", "three-in-one", "split"])
async def test_a_completed_project_passes_every_check(smoke, tmp_path, shape, canvases):
    project = await finished(shape)
    be = FakeBe([(200, running(project)), (200, running(project)), (200, project)])

    outcome, lines, clock = await run(smoke, be, tmp_path)

    assert outcome.ok, (outcome.reason, outcome.problems)
    assert len([r for r in outcome.project["rows"] if r["stage"] == "canvas"]) == canvases
    assert len(outcome.summary) == canvases and all("final version" in line for line in outcome.summary)
    assert clock.now == 10  # two sleeps of 5 s before the third poll answered completed


async def test_the_request_asks_for_auto_approve_and_the_enabled_optional_stages(smoke, tmp_path):
    project = await finished(ONE)
    be = FakeBe([(200, project)])

    await run(smoke, be, tmp_path, enabled=["environment_scan"])

    assert be.created_body == {"idea": IDEA, "language": "en", "enabledOptional": ["environment_scan"], "autoApprove": True}


async def test_an_existing_user_is_fine_and_the_login_uses_the_form_endpoint(smoke, tmp_path):
    project = await finished(ONE)
    be = FakeBe([(200, project)], user_status=409)

    outcome, _, _ = await run(smoke, be, tmp_path)

    assert outcome.ok
    login = next(r for r in be.requests if r.url.path == "/api/auth/login")
    assert login.headers["content-type"].startswith("application/x-www-form-urlencoded")
    assert b"username=smoke%40example.com" in login.content


async def test_the_table_lists_every_row_with_duration_error_and_violations(smoke, tmp_path):
    project = await finished(ONE)
    row = project["rows"][0]
    row["consistency"] = ConsistencyReport(
        score=3,
        violations=[
            ConsistencyViolation(rule_id="r", severity="error", message="m", artifact_ids=["a"]),
            ConsistencyViolation(rule_id="r", severity="warning", message="m", artifact_ids=["a"]),
            ConsistencyViolation(rule_id="r", severity="warning", message="m", artifact_ids=["a"]),
        ],
    ).model_dump(mode="json")
    row["retryCount"] = 1

    table = smoke.rows_table(project)

    first = table.splitlines()[1]
    assert first.split() == ["brief", "0", "done", "1", "2.5s", "-", "1e/2w"]
    assert len(table.splitlines()) == len(project["rows"]) + 1


async def test_the_dump_is_written_and_holds_no_token_or_password(smoke, tmp_path):
    project = await finished(ONE)
    be = FakeBe([(200, project)])

    outcome, _, _ = await run(smoke, be, tmp_path)

    text = outcome.dump_path.read_text()
    assert json.loads(text)["id"] == "p-1"
    assert TOKEN not in text and PASSWORD not in text and "SharedAccessKey" not in text


async def test_a_project_that_carries_a_token_is_never_written_to_disk(smoke, tmp_path):
    project = await finished(ONE)
    project["title"] = f"leaked {TOKEN}-1"  # the token the mocked login hands out
    be = FakeBe([(200, project)])

    with pytest.raises(smoke.SmokeError, match="refusing to write the dump"):
        await run(smoke, be, tmp_path)

    assert not (tmp_path / "dumps").exists() or list((tmp_path / "dumps").iterdir()) == []


# --------------------------------------------------------------------------- failures


async def test_a_failed_project_is_a_failure_with_the_reason(smoke, tmp_path):
    project = await finished(ONE)
    broken = copy.deepcopy(project)
    broken["status"] = "failed"
    pitch = next(r for r in broken["rows"] if r["stage"] == "pitch")
    pitch["status"] = "error"
    pitch["error"] = {"code": StageErrorCode.GENERATION_FAILED.value, "message": "the model returned nonsense"}
    be = FakeBe([(200, running(project)), (200, broken)])

    outcome, lines, _ = await run(smoke, be, tmp_path)

    assert not outcome.ok
    assert "failed" in outcome.reason and "pitch[0] generation_failed: the model returned nonsense" in outcome.reason
    assert any("project status is failed" in p for p in outcome.problems)
    assert outcome.dump_path is not None  # the evidence is kept


async def test_a_timeout_is_a_failure_with_the_reason(smoke, tmp_path):
    project = await finished(ONE)
    be = FakeBe([(200, running(project))])

    outcome, _, clock = await run(smoke, be, tmp_path, timeout=30)

    assert not outcome.ok
    assert outcome.reason.startswith("timeout after 30 s") and "running" in outcome.reason
    assert 30 <= clock.now < 40
    assert any("not completed" in p for p in outcome.problems)


async def test_be_going_away_is_reported_after_repeated_failed_polls(smoke, tmp_path):
    be = FakeBe([(503, None)])

    outcome, _, _ = await run(smoke, be, tmp_path)

    assert not outcome.ok and "unreachable" in outcome.reason and outcome.project is None


async def test_an_expired_token_is_refreshed_by_logging_in_again(smoke, tmp_path):
    project = await finished(ONE)
    be = FakeBe([(401, None), (200, project)])

    outcome, _, _ = await run(smoke, be, tmp_path)

    assert outcome.ok and be.logins == 2
    polls = [r for r in be.requests if r.url.path == "/api/projects/p-1"]
    assert polls[0].headers["authorization"].endswith("-1") and polls[1].headers["authorization"].endswith("-2")


async def test_a_refused_generation_stops_the_run(smoke, tmp_path):
    be = FakeBe([(200, {})], create_status=422)
    with pytest.raises(smoke.SmokeError, match="422"):
        await run(smoke, be, tmp_path)


async def test_a_failed_login_stops_the_run(smoke, tmp_path):
    be = FakeBe([(200, {})], login_status=401)
    with pytest.raises(smoke.SmokeError, match="login failed"):
        await run(smoke, be, tmp_path)


# --------------------------------------------------------------------------- the checks


async def test_an_artifact_that_does_not_parse_is_reported(smoke, tmp_path):
    project = await finished(ONE)
    pitch = next(r for r in project["rows"] if r["stage"] == "pitch")
    pitch["artifacts"][0]["data"] = {"hook": "only this"}
    be = FakeBe([(200, project)])

    outcome, _, _ = await run(smoke, be, tmp_path)

    assert not outcome.ok
    assert any(p.startswith("does not parse: pitch[0] pitch") for p in outcome.problems)


async def test_a_record_id_that_differs_from_the_artifacts_own_id_is_reported(smoke, tmp_path):
    project = await finished(ONE)
    story = next(r for r in project["rows"] if r["stage"] == "storytelling")
    story["artifacts"][0]["id"] = "not-its-own-id"

    problems, _ = smoke.run_checks(project, [])

    assert any("does not parse: storytelling[0]" in p and "differs" in p for p in problems)


async def test_a_wrong_row_count_is_reported(smoke, tmp_path):
    project = await finished(SPLIT_IN_TWO)
    pitches = [r for r in project["rows"] if r["stage"] == "pitch"]
    project["rows"].remove(pitches[-1])
    be = FakeBe([(200, project)])

    outcome, _, _ = await run(smoke, be, tmp_path)

    assert not outcome.ok
    assert any(p == "pitch: expected 2 rows, found 1" for p in outcome.problems)


async def test_the_segment_count_must_match_the_briefs_candidates(smoke):
    project = await finished(THREE_IN_ONE_MULTI_SIDED)
    dropped = next(r for r in project["rows"] if r["stage"] == "empathy_map" and r["instanceIndex"] == 2)
    project["rows"].remove(dropped)

    problems, _ = smoke.run_checks(project, [])

    assert any("empathy_map rows (2) differ from the brief's segment candidates (3)" in p for p in problems)


async def test_the_canvas_count_must_match_the_patterns_groups(smoke):
    project = await finished(SPLIT_IN_TWO)
    project["rows"] = [r for r in project["rows"] if not (r["stage"] == "canvas" and r["instanceIndex"] == 1)]

    problems, _ = smoke.run_checks(project, [])

    assert any("canvas rows (1) differ from the Patterns groups (2)" in p for p in problems)


async def test_a_row_that_is_not_done_is_reported(smoke):
    project = await finished(ONE)
    next(r for r in project["rows"] if r["stage"] == "future_scenario")["status"] = "awaiting_decision"

    problems, _ = smoke.run_checks(project, [])

    assert "row future_scenario[0] is awaiting_decision, not done" in problems


async def test_a_duplicated_row_is_reported(smoke):
    project = await finished(ONE)
    project["rows"].append(copy.deepcopy(next(r for r in project["rows"] if r["stage"] == "ideation")))

    problems, _ = smoke.run_checks(project, [])

    assert any("duplicated row: ideation[0]" in p for p in problems)
    assert any("row id" in p and "appears 2 times" in p for p in problems)
    assert any("ideation: expected 1 rows, found 2" in p for p in problems)


async def test_an_enabled_optional_stage_must_have_its_row_and_a_disabled_one_must_not(smoke):
    project = await finished(ONE)

    assert "environment_scan: expected 1 rows, found 0" in smoke.run_checks(project, ["environment_scan"])[0]
    project["rows"].append({**copy.deepcopy(project["rows"][0]), "id": "scan", "stage": "environment_scan", "artifacts": [], "refs": {"brief": [project["rows"][0]["id"]]}})
    assert "environment_scan: expected 0 rows, found 1" in smoke.run_checks(project, [])[0]


async def test_a_cycle_without_swots_cannot_yield_a_final_canvas(smoke):
    project = await finished(ONE)
    cycle = next(r for r in project["rows"] if r["stage"] == "swot_errc_cycle")
    cycle["artifacts"] = [a for a in cycle["artifacts"] if a["type"] != "swot"]

    problems, _ = smoke.run_checks(project, [])

    assert any(p.startswith("canvas[0]: cannot derive the final canvas") for p in problems)


# --------------------------------------------------------------------------- guards and arguments


def test_the_dump_guard_refuses_tokens_passwords_and_connection_strings(smoke, tmp_path):
    for text in (f'{{"x": "{TOKEN}"}}', f'{{"x": "{PASSWORD}"}}', '{"x": "SharedAccessKey=abc"}', '{"x": "Endpoint=sb://ns.servicebus.windows.net/"}'):
        with pytest.raises(smoke.SmokeError):
            smoke.assert_no_secrets(text, [TOKEN, PASSWORD])
    smoke.assert_no_secrets('{"x": "clean"}', [TOKEN, PASSWORD])


def test_the_arguments_are_validated(smoke, monkeypatch):
    monkeypatch.delenv("SMOKE_PASSWORD", raising=False)
    base = ["--base-url", "http://x", "--email", "a@b.c", "--idea", IDEA]
    with pytest.raises(SystemExit):
        smoke.parse_args(base)  # no password
    with pytest.raises(SystemExit):
        smoke.parse_args([*base[:-1], "too short", "--password", "x"])
    with pytest.raises(SystemExit):
        smoke.parse_args([*base, "--password", "x", "--enable-optional", "team_info"])
    args = smoke.parse_args([*base, "--password", "x", "--enable-optional", "environment_scan", "business_case", "--language", "uk"])
    assert args.enable_optional == ["environment_scan", "business_case"] and args.language == "uk" and args.timeout == 1800

    monkeypatch.setenv("SMOKE_PASSWORD", "from-env")
    assert smoke.parse_args(base).password == "from-env"


# --------------------------------------------------------------------------- tokens through Langfuse

LF_KEYS = {"LANGFUSE_PUBLIC_KEY": "pk-lf-PUBLIC123", "LANGFUSE_SECRET_KEY": "sk-lf-SECRET456", "LANGFUSE_HOST": "http://lf.test"}


class FakeLangfuse:
    """The Langfuse public API as a mock transport: traces of a session and their generation observations."""

    def __init__(self, project: dict, *, per_call: tuple[int, int] = (100, 20), appear_after: int = 0, page_size: int = 100, status: int = 200,
                 usage_key: str = "usageDetails") -> None:
        self.traces = [
            {"id": f"t-{r['id']}", "sessionId": project["id"], "metadata": {"block": r["stage"], "row_id": r["id"]}, "tags": [r["stage"]]}
            for r in project["rows"]
        ]
        self.per_call, self.appear_after, self.page_size, self.status, self.usage_key = per_call, appear_after, page_size, status, usage_key
        self.trace_requests = 0
        self.requests: list[httpx.Request] = []

    def handler(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        if self.status != 200:
            return httpx.Response(self.status, text="no")
        params = request.url.params
        page, limit = int(params["page"]), min(int(params["limit"]), self.page_size)
        if request.url.path == "/api/public/traces":
            self.trace_requests += 1
            assert params["sessionId"] == "p-1"
            visible = self.traces if self.trace_requests > self.appear_after else self.traces[:1]
            return httpx.Response(200, json=self._page(visible, page, limit))
        assert request.url.path == "/api/public/observations" and params["type"] == "GENERATION"
        inp, out = self.per_call
        usage = {"input": inp, "output": out, "total": inp + out}
        calls = [{"name": "llm_call", self.usage_key: usage}, {"name": "llm_call", self.usage_key: usage}]
        return httpx.Response(200, json=self._page(calls, page, limit))

    @staticmethod
    def _page(items: list, page: int, limit: int) -> dict:
        pages = max(1, -(-len(items) // limit))
        return {"data": items[(page - 1) * limit : page * limit], "meta": {"page": page, "limit": limit, "totalItems": len(items), "totalPages": pages}}

    def transport(self) -> httpx.MockTransport:
        return httpx.MockTransport(self.handler)


LEDGER = """# Ledger

| stage | prompt version | idea | calls | input | output | total | date |
|---|---|---|---|---|---|---|---|
| pitch | 1 | farm (EN) | 1 | 2,493 | 711 | 3,204 | d |
| pitch | 1 | photo (EN) | 1 | 2,670 | 839 | 3,509 | d |
| pitch | 1 | split (EN) | 1 | 2,644 | 830 | 3,474 | d |

| idea | rows | LLM calls | total tokens | cycle |
|---|---|---|---|---|
| farm (EN) | 10 | 12 | 40,759 | x |
| split (EN) | 13 | 17 | 63,523 | x |

| idea | description | iterations | score series | final version | calls | input | output | total | wall-clock |
|---|---|---|---|---|---|---|---|---|---|
| farm | single segment | 5 | [1] | 4 | 9 | 26,687 | 12,895 | 39,582 | 129 s |
"""


async def langfuse_run(smoke, tmp_path, lf: FakeLangfuse | None, environ: dict, project: dict, **kwargs):
    be = FakeBe([(200, project)])
    ledger = tmp_path / "ledger.md"
    ledger.write_text(LEDGER)
    extra = {"langfuse": True, "langfuse_kwargs": {"environ": environ, "transport": lf.transport() if lf else None, "wait": 30, "ledger_path": ledger, **kwargs}}
    outcome, lines, clock = await run(smoke, be, tmp_path, **extra)
    report_lines: list[str] = []
    smoke.report(outcome, report_lines.append)  # what the script prints
    return outcome, report_lines, clock


async def test_langfuse_prints_tokens_per_stage_and_in_total_next_to_the_ledger(smoke, tmp_path):
    project = await finished(ONE)
    lf = FakeLangfuse(project)
    outcome, lines, _ = await langfuse_run(smoke, tmp_path, lf, LF_KEYS, project, sleep=Clock().sleep)
    assert outcome.ok
    report = "\n".join(lines)
    rows = len(project["rows"])
    assert f"{rows} traces, {rows} of {rows} rows traced" in report
    # two calls of 100 in / 20 out per trace; one trace per row, one row per stage in this shape
    pitch_line = next(line for line in lines if line.strip().startswith("pitch"))
    assert " 2 " in pitch_line and "200" in pitch_line and "40" in pitch_line and "240" in pitch_line and "3,474 - 3,509" not in pitch_line  # ledger range of pitch: 3,204 - 3,509
    assert "3,204 - 3,509 (3 runs)" in pitch_line
    all_line = next(line for line in lines if line.strip().startswith("ALL"))
    assert f"{rows * 240:,}" in all_line and "40,759 - 63,523 (2 runs)" in all_line
    assert "WARNING" not in report


async def test_the_langfuse_keys_are_never_printed_or_dumped(smoke, tmp_path):
    project = await finished(ONE)
    lf = FakeLangfuse(project)
    outcome, lines, _ = await langfuse_run(smoke, tmp_path, lf, LF_KEYS, project, sleep=Clock().sleep)
    printed = "\n".join(lines) + "\n".join(outcome.usage_lines) + outcome.dump_path.read_text()
    assert "PUBLIC123" not in printed and "SECRET456" not in printed
    assert all(request.headers["authorization"].startswith("Basic ") for request in lf.requests)


async def test_without_the_keys_it_says_so_and_the_verdict_is_unaffected(smoke, tmp_path):
    project = await finished(ONE)
    outcome, lines, _ = await langfuse_run(smoke, tmp_path, None, {"LANGFUSE_PUBLIC_KEY": "pk-only"}, project)
    assert outcome.ok and any("Langfuse is not configured" in line for line in lines)


async def test_traces_that_appear_late_are_waited_for(smoke, tmp_path):
    project = await finished(ONE)
    lf = FakeLangfuse(project, appear_after=3)
    clock = Clock()
    outcome, lines, _ = await langfuse_run(smoke, tmp_path, lf, LF_KEYS, project, sleep=clock.sleep)
    rows = len(project["rows"])
    assert lf.trace_requests == 4 and f"{rows} traces" in "\n".join(lines) and "WARNING" not in "\n".join(lines)


async def test_traces_that_never_appear_give_a_warning_not_a_failure(smoke, tmp_path):
    project = await finished(ONE)
    lf = FakeLangfuse(project, appear_after=10_000)
    outcome, lines, _ = await langfuse_run(smoke, tmp_path, lf, LF_KEYS, project, sleep=Clock().sleep, wait=10)
    assert outcome.ok and any(line.strip().startswith("WARNING: only 1 of") for line in lines)


async def test_a_langfuse_error_is_reported_and_does_not_fail_the_smoke(smoke, tmp_path):
    project = await finished(ONE)
    outcome, lines, _ = await langfuse_run(smoke, tmp_path, FakeLangfuse(project, status=401), LF_KEYS, project, sleep=Clock().sleep)
    assert outcome.ok and any("Langfuse token report failed" in line and "HTTP 401" in line for line in lines)
    assert "SECRET456" not in "\n".join(lines)


async def test_every_page_is_read_and_the_older_usage_field_is_understood(smoke, tmp_path):
    project = await finished(SPLIT_IN_TWO)
    lf = FakeLangfuse(project, page_size=2, usage_key="usage")
    outcome, lines, _ = await langfuse_run(smoke, tmp_path, lf, LF_KEYS, project, sleep=Clock().sleep)
    rows = len(project["rows"])
    assert rows > 2 and f"{rows} traces, {rows} of {rows} rows traced" in "\n".join(lines)
    assert f"{rows * 240:,}" in next(line for line in lines if line.strip().startswith("ALL"))


def test_the_ledger_is_read_by_table_header(smoke):
    ledger = smoke.load_ledger()  # the real file: loose checks, it grows with every measurement
    assert {3204, 3474, 3509} <= set(ledger["pitch"]) and len(ledger["ALL"]) >= 3 and len(ledger["swot_errc_cycle"]) >= 3
    assert "brief" in ledger and "canvas" in ledger


def test_the_langfuse_flag_is_opt_in(smoke):
    base = ["--base-url", "http://x", "--email", "a@b.c", "--password", "p", "--idea", IDEA]
    assert smoke.parse_args(base).langfuse is False
    assert smoke.parse_args([*base, "--langfuse"]).langfuse is True


async def test_the_host_and_the_basic_auth_come_from_the_environment(smoke, tmp_path):
    import base64

    project = await finished(ONE)
    lf = FakeLangfuse(project)
    await langfuse_run(smoke, tmp_path, lf, LF_KEYS, project, sleep=Clock().sleep)
    assert {request.url.host for request in lf.requests} == {"lf.test"}
    sent = base64.b64decode(lf.requests[0].headers["authorization"].split()[1]).decode()
    assert sent == "pk-lf-PUBLIC123:sk-lf-SECRET456"
    assert smoke.langfuse_settings({"LANGFUSE_PUBLIC_KEY": "a", "LANGFUSE_SECRET_KEY": "b"})[2] == smoke.DEFAULT_LANGFUSE_HOST


def test_a_generation_without_a_total_is_summed_from_input_and_output(smoke):
    assert smoke._usage_of({"usageDetails": {"input": 7, "output": 3}}) == (7, 3, 10)
    assert smoke._usage_of({"usageDetails": {"input": 7, "output": 3, "total": 12}}) == (7, 3, 12)
    assert smoke._usage_of({}) == (0, 0, 0)


async def test_a_rate_limited_langfuse_is_waited_for_with_retry_after(smoke, tmp_path):
    project = await finished(ONE)
    lf = FakeLangfuse(project)
    limited = {"left": 3}
    inner = lf.handler

    def handler(request):
        if limited["left"] > 0:
            limited["left"] -= 1
            return httpx.Response(429, headers={"Retry-After": "7"})
        return inner(request)

    lf.transport = lambda: httpx.MockTransport(handler)  # type: ignore[method-assign]
    clock = Clock()
    outcome, lines, _ = await langfuse_run(smoke, tmp_path, lf, LF_KEYS, project, sleep=clock.sleep)
    assert outcome.ok and "WARNING" not in "\n".join(lines) and "failed" not in "\n".join(lines)
    assert clock.now >= 21  # three waits of 7 s


async def test_a_langfuse_that_stays_rate_limited_is_reported_as_429(smoke, tmp_path):
    project = await finished(ONE)
    lf = FakeLangfuse(project, status=429)
    outcome, lines, _ = await langfuse_run(smoke, tmp_path, lf, LF_KEYS, project, sleep=Clock().sleep)
    assert outcome.ok and any("HTTP 429" in line for line in lines)
    assert len(lf.requests) == smoke.LANGFUSE_RATE_LIMIT_RETRIES
