"""The experiment runner against a mocked be and Langfuse: planning, resume, concurrency, budget, the result line,
the secret guard, the config registry and the report. No network."""
import ast
import asyncio
import hashlib
import importlib
import json
import statistics
from datetime import datetime, timezone
from pathlib import Path

import bizstruct_domain
import httpx
import pytest

from experiments import __main__ as cli
from experiments import report as report_module
from experiments import run_meta as run_meta_module
from experiments.configs import CONFIGS, Config, RunOptions
from experiments.ideaset import Idea, IdeasFileError, load_ideas
from experiments.runner import RunSpec, estimate_tokens, load_results, plan_runs, select_runs
from tests.support.experiment_be import LF_KEYS, PASSWORD, TOKEN, MultiBe
from tests.test_e2e_smoke_script import finished, public_project
from tests.support.projects import ONE, SPLIT_IN_TWO

SAMPLE = Path(__file__).resolve().parent.parent / "experiments" / "ideas" / "ideas.jsonl"
HYPOTHESIS = "ZZ-HIDDEN-HYPOTHESIS"
TAG = "zz-hidden-tag"
TEXT = "An app that delivers boxes of fresh produce from local farms to busy city parents."


def idea(idea_id: str, text: str = TEXT, **extra) -> dict:
    return {"id": idea_id, "language": "en", "text": text, "expected_shape": HYPOTHESIS, "tags": [TAG], **extra}


def write_ideas(path: Path, *ideas: dict) -> Path:
    path.write_text("\n".join(json.dumps(i) for i in ideas) + "\n", encoding="utf-8")
    return path


_BASE: dict[str, dict] = {}


async def base_project(shape=ONE) -> dict:
    if shape.name not in _BASE:
        _BASE[shape.name] = await finished(shape)
    return _BASE[shape.name]


async def fast_sleep(seconds: float) -> None:
    await asyncio.sleep(0)


class Ticker:
    """A fake clock: it advances by the seconds the code sleeps."""

    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        return self.now

    async def sleep(self, seconds: float) -> None:
        self.now += max(seconds, 0.01)
        await asyncio.sleep(0)


def parse(*argv: str):
    return cli.build_parser().parse_args(["run", *argv])


class Machine:
    """Stands in for git, docker and az: answers by command, records every call. `heads` maps repo name -> HEAD."""

    def __init__(self, heads: dict[str, str] | None = None, *, dirty: set[str] = frozenset(), docker: bool = True, az: dict | None = None):
        self.heads = heads if heads is not None else {r: str(n) * 40 for n, r in enumerate(run_meta_module.SIBLING_REPOS, start=1)}
        self.dirty, self.docker, self.az = set(dirty), docker, az
        self.calls: list[list[str]] = []

    def __call__(self, argv: list[str]) -> str:
        self.calls.append(argv)
        if argv[0] == "git":
            repo = Path(argv[2]).name
            if argv[3:] == ["rev-parse", "HEAD"]:
                return self.heads[repo] + "\n"
            if argv[3:] == ["rev-parse", "--abbrev-ref", "HEAD"]:
                return "main\n"
            return " M file\n" if repo in self.dirty else ""
        if argv[0] == "docker":
            if not self.docker:
                raise FileNotFoundError("docker")
            if argv[1] == "ps":
                service = [a for a in argv if a.startswith("label=com.docker.compose.service=")][0].rsplit("=", 1)[1]
                return f"c-{service}\n"
            return f"sha256:img-{argv[-1]}\n"
        if argv[0] == "az":
            if self.az is None:
                raise FileNotFoundError("az")
            return json.dumps(self.az)
        raise AssertionError(argv)


def fake_repos(tmp_path: Path, names=("bizstruct-domain", "bizstruct-be", "bizstruct-ml", "bizstruct-fe")) -> Path:
    root = tmp_path / "repos"
    for name in names:
        (root / name).mkdir(parents=True, exist_ok=True)
    return root


async def run_cli(tmp_path, be: MultiBe, ideas: Path, *argv: str, environ=None, ticker: Ticker | None = None, machine: Machine | None = None, repos: Path | None = None):
    args = parse("--ideas", str(ideas), "--out", str(tmp_path / "out"), "--base-url", "http://be.test", "--email", "x@example.com",
                 "--password", PASSWORD, "--poll-interval", "1", *argv)
    lines: list[str] = []
    ticker = ticker or Ticker()
    code = await cli.run_command(args, transport=be.transport(), langfuse_transport=be.langfuse_transport(), environ=environ or {},
                                 log=lines.append, sleep=ticker.sleep, clock=ticker, meta_cmd=machine or Machine(),
                                 repos_root=repos or fake_repos(tmp_path),
                                 command_line=["python", "-m", "experiments", "run", *argv, "--password", PASSWORD])
    return code, lines


def read_results(tmp_path) -> list[dict]:
    return [json.loads(line) for line in (tmp_path / "out" / "results.jsonl").read_text().splitlines()]


# --------------------------------------------------------------------------- ideas


def test_the_sample_file_loads_and_only_idea_input_leaves_the_module():
    ideas = load_ideas(SAMPLE)
    assert len(ideas) == 2 and all(50 <= len(i.text) <= 2000 for i in ideas)
    sent = ideas[0].for_system()
    assert set(sent.model_dump()) == {"id", "language", "text"}


@pytest.mark.parametrize(
    ("line", "message"),
    [
        ('{"id": "a", "language": "en", "text": "too short"}', "text"),
        (json.dumps(idea("a", language="fr")) , "language"),
        (json.dumps({**idea("a"), "surprise": 1}), "surprise"),
        (json.dumps(idea("../escape")), "id"),
        (json.dumps(idea("a", text="x" * 2001)), "text"),
        ("not json", "not JSON"),
    ],
)
def test_a_bad_line_is_refused_with_its_line_number(tmp_path, line, message):
    path = tmp_path / "ideas.jsonl"
    path.write_text(json.dumps(idea("ok")) + "\n\n" + line + "\n")
    with pytest.raises(IdeasFileError, match=f":3: .*{message}"):
        load_ideas(path)


def test_the_text_length_limits_are_exact(tmp_path):
    for length, fine in ((49, False), (50, True), (2000, True), (2001, False)):
        path = write_ideas(tmp_path / f"{length}.jsonl", idea("a", text="x" * length))
        if fine:
            assert load_ideas(path)[0].text == "x" * length
        else:
            with pytest.raises(IdeasFileError):
                load_ideas(path)


def test_duplicate_ids_and_an_empty_file_are_refused(tmp_path):
    with pytest.raises(IdeasFileError, match="duplicate"):
        load_ideas(write_ideas(tmp_path / "a.jsonl", idea("a"), idea("a")))
    with pytest.raises(IdeasFileError, match="no ideas"):
        load_ideas(write_ideas(tmp_path / "b.jsonl"))


async def test_the_hypothesis_and_the_tags_are_never_sent(tmp_path):
    be = MultiBe(await base_project())
    ideas = write_ideas(tmp_path / "i.jsonl", idea("a"), idea("b", text=TEXT + " Second."))
    code, _ = await run_cli(tmp_path, be, ideas)
    assert code == 0 and len(be.created) == 2
    everything = " ".join(str(r.url) + r.content.decode() + str(dict(r.headers)) for r in be.requests)
    assert HYPOTHESIS not in everything and TAG not in everything
    assert be.created[0] == {"idea": TEXT, "language": "en", "enabledOptional": [], "autoApprove": True}


# --------------------------------------------------------------------------- planning and resume


def test_the_plan_is_repeat_major_and_complete():
    ideas = [Idea(**idea("a")), Idea(**idea("b"))]
    plan = plan_runs(ideas, 3)
    assert [(s.idea.id, s.repeat) for s in plan] == [("a", 1), ("b", 1), ("a", 2), ("b", 2), ("a", 3), ("b", 3)]


def test_recorded_pairs_are_skipped_and_failed_ones_only_retried_on_request():
    plan = plan_runs([Idea(**idea("a")), Idea(**idea("b"))], 2)
    previous = {("a", 1): {"status": "completed"}, ("b", 1): {"status": "failed"}, ("a", 2): {"status": "timeout"}}
    plain = select_runs(plan, previous, retry_failed=False)
    assert [s.key for s in plain.to_run] == [("b", 2)] and len(plain.skipped) == 3 and plain.retried == []
    retry = select_runs(plan, previous, retry_failed=True)
    assert [s.key for s in retry.to_run] == [("b", 1), ("a", 2), ("b", 2)] and [s.key for s in retry.retried] == [("b", 1), ("a", 2)]


async def test_a_second_invocation_resumes_and_runs_nothing_that_is_recorded(tmp_path):
    be = MultiBe(await base_project())
    ideas = write_ideas(tmp_path / "i.jsonl", idea("a"), idea("b", text=TEXT + " Second."))
    await run_cli(tmp_path, be, ideas, "--repeats", "1")
    assert len(be.created) == 2
    code, lines = await run_cli(tmp_path, be, ideas, "--repeats", "2")  # only the second repeats are new
    assert code == 0 and len(be.created) == 4
    assert sorted((r["idea_id"], r["repeat"]) for r in read_results(tmp_path)) == [("a", 1), ("a", 2), ("b", 1), ("b", 2)]
    code, lines = await run_cli(tmp_path, be, ideas, "--repeats", "2")
    assert len(be.created) == 4 and "0 to run, 4 already recorded" in lines[0]


async def test_retry_failed_runs_a_failed_pair_again_and_the_latest_line_wins(tmp_path):
    state = {"fail": True}
    be = MultiBe(await base_project(), outcome_of=lambda text: "failed" if state["fail"] else "completed")
    ideas = write_ideas(tmp_path / "i.jsonl", idea("a"))
    await run_cli(tmp_path, be, ideas)
    assert read_results(tmp_path)[0]["status"] == "failed"
    state["fail"] = False
    await run_cli(tmp_path, be, ideas)  # without the flag: left alone
    assert len(be.created) == 1
    await run_cli(tmp_path, be, ideas, "--retry-failed")
    assert len(be.created) == 2
    lines = read_results(tmp_path)
    assert [r["status"] for r in lines] == ["failed", "completed"]
    await run_cli(tmp_path, be, ideas, "--retry-failed")  # the pair is completed now, whatever its first line said
    assert len(be.created) == 2
    assert report_module.summarize(report_module.load_latest(tmp_path / "out" / "results.jsonl"))["ALL"]["completed"] == 1


# --------------------------------------------------------------------------- concurrency and budgets


@pytest.mark.parametrize("limit", [1, 2, 3])
async def test_no_more_projects_run_at_once_than_asked_for(tmp_path, limit):
    be = MultiBe(await base_project(), polls_needed=3)
    ideas = write_ideas(tmp_path / "i.jsonl", *[idea(f"i{n}", text=TEXT + f" {n}") for n in range(5)])
    code, _ = await run_cli(tmp_path, be, ideas, "--concurrency", str(limit))
    assert code == 0 and len(be.created) == 5
    assert be.max_active == limit


async def test_max_tokens_stops_launching_once_the_measured_total_exceeds_it(tmp_path):
    be = MultiBe(await base_project())
    ideas = write_ideas(tmp_path / "i.jsonl", *[idea(f"i{n}", text=TEXT + f" {n}") for n in range(6)])
    budget = be.tokens_per_project * 2 + 1  # exceeded after the third run
    code, lines = await run_cli(tmp_path, be, ideas, "--max-tokens", str(budget), environ=LF_KEYS)
    assert code == 0 and len(be.created) == 3
    assert any("--max-tokens" in line and "exceeded" in line and "3 not launched" in line for line in lines)
    assert all(r["tokens"]["total"] == be.tokens_per_project for r in read_results(tmp_path))


async def test_the_budget_counts_this_invocation_only_and_a_total_at_the_limit_is_not_exceeded(tmp_path):
    be = MultiBe(await base_project())
    ideas = write_ideas(tmp_path / "i.jsonl", *[idea(f"i{n}", text=TEXT + f" {n}") for n in range(6)])
    limit = str(be.tokens_per_project * 2)
    await run_cli(tmp_path, be, ideas, "--max-tokens", limit, environ=LF_KEYS)
    assert len(be.created) == 3  # two runs sit exactly at the limit, which is not "exceeded", so a third is launched
    await run_cli(tmp_path, be, ideas, "--max-tokens", limit, environ=LF_KEYS)
    assert len(be.created) == 6  # a fresh invocation starts from zero and resumes where the first stopped


async def test_without_langfuse_keys_max_tokens_cannot_be_enforced_and_runs_are_counted(tmp_path):
    be = MultiBe(await base_project())
    ideas = write_ideas(tmp_path / "i.jsonl", *[idea(f"i{n}", text=TEXT + f" {n}") for n in range(4)])
    code, lines = await run_cli(tmp_path, be, ideas, "--max-tokens", "1", "--max-runs", "2", environ={})
    assert len(be.created) == 2
    assert any("Langfuse is not configured" in line and "cannot be enforced" in line for line in lines)
    assert all(r["tokens"] is None for r in read_results(tmp_path))


async def test_max_runs_limits_the_launches(tmp_path):
    be = MultiBe(await base_project())
    ideas = write_ideas(tmp_path / "i.jsonl", idea("a"), idea("b", text=TEXT + " b"), idea("c", text=TEXT + " c"))
    code, lines = await run_cli(tmp_path, be, ideas, "--max-runs", "2")
    assert len(be.created) == 2 and any("--max-runs 2 reached" in line and "1 not launched" in line for line in lines)


async def test_a_dry_run_calls_nothing_writes_nothing_and_estimates_from_the_ledger(tmp_path):
    def boom(request):
        raise AssertionError("a dry run must not call anything")

    args = parse("--ideas", str(SAMPLE), "--repeats", "3", "--out", str(tmp_path / "out"), "--dry-run")
    lines: list[str] = []
    assert await cli.run_command(args, transport=httpx.MockTransport(boom), langfuse_transport=httpx.MockTransport(boom), log=lines.append) == 0
    text = "\n".join(lines)
    assert "6 runs (2 ideas)" in text and "6 to run" in text and "sample-farm: 3 run(s)" in text
    assert "estimated tokens: about" in text and "nothing was called" in text
    assert not (tmp_path / "out").exists()


def test_the_estimate_is_runs_times_the_median_of_the_whole_run_totals():
    ledger = {"ALL": [10, 20, 60]}
    assert estimate_tokens(3, ledger) == (30, 60, 180)
    assert estimate_tokens(3, {}) is None


def test_a_dry_run_needs_no_credentials_but_a_real_run_does():
    parser = cli.build_parser()
    args = parser.parse_args(["run", "--ideas", "x", "--out", "y", "--dry-run"])
    cli.validate_run_args(parser, args)
    args = parser.parse_args(["run", "--ideas", "x", "--out", "y"])
    args.password = None
    with pytest.raises(SystemExit):
        cli.validate_run_args(parser, args)


@pytest.mark.parametrize("flag", ["--repeats", "--concurrency"])
def test_repeats_and_concurrency_must_be_positive(flag):
    parser = cli.build_parser()
    args = parser.parse_args(["run", "--ideas", "x", "--out", "y", "--dry-run", flag, "0"])
    with pytest.raises(SystemExit):
        cli.validate_run_args(parser, args)


async def test_the_enabled_optional_stages_are_sent(tmp_path):
    be = MultiBe(await base_project())
    await run_cli(tmp_path, be, write_ideas(tmp_path / "i.jsonl", idea("a")), "--enable-optional", "business_case")
    assert be.created[0]["enabledOptional"] == ["business_case"]


# --------------------------------------------------------------------------- the result line


async def test_the_result_line_describes_the_run(tmp_path):
    be = MultiBe(await base_project(SPLIT_IN_TWO))
    ideas = write_ideas(tmp_path / "i.jsonl", idea("a"))
    await run_cli(tmp_path, be, ideas, "--langfuse", environ=LF_KEYS)
    (record,) = read_results(tmp_path)
    assert (record["idea_id"], record["repeat"], record["config"], record["project_id"], record["status"]) == ("a", 1, "pipeline", "p-1", "completed")
    assert record["started_at"] <= record["finished_at"] and record["wall_clock_s"] > 0
    assert record["errors"] == [] and record["checks"] == {"ok": True, "problems": []}
    stages = [row["stage"] for row in record["rows"]]
    assert stages.count("canvas") == 2 and stages.count("pitch") == 2
    row = record["rows"][0]
    assert set(row) == {"stage", "instance", "status", "retries", "duration_s", "violations"} and row["duration_s"] == 2.5
    shape = record["shape"]
    assert shape["segments"] == stages.count("empathy_map") and shape["canvases"] == 2 and len(shape["cycles"]) == 2
    assert all(c["iterations"] == len(c["scores"]) and c["final_version"] == 2 for c in shape["cycles"])  # scores (100, 90, 95): version 2
    tokens = record["tokens"]
    assert tokens["total"] == be.tokens_per_project and tokens["rows_traced"] == len(record["rows"])
    assert set(tokens["per_stage"]) == set(stages) and tokens["per_stage"]["pitch"]["total"] == 2 * 120
    project_file = tmp_path / "out" / "projects" / "a-1.json"
    assert json.loads(project_file.read_text())["id"] == "p-1"


async def test_violations_are_recorded_per_rule_id_and_severity(tmp_path):
    base = await base_project()

    def with_violations(project: dict) -> dict:
        project["rows"][0]["consistency"] = {"score": 3, "violations": [
            {"rule_id": "rule_a", "severity": "warning", "message": "m", "artifact_ids": []},
            {"rule_id": "rule_a", "severity": "warning", "message": "m2", "artifact_ids": []},
            {"rule_id": "rule_b", "severity": "error", "message": "m", "artifact_ids": []}]}
        return project

    be = MultiBe(base, mutate=with_violations)
    await run_cli(tmp_path, be, write_ideas(tmp_path / "i.jsonl", idea("a")))
    (record,) = read_results(tmp_path)
    assert record["rows"][0]["violations"] == [
        {"rule_id": "rule_a", "severity": "warning", "count": 2}, {"rule_id": "rule_b", "severity": "error", "count": 1}]


async def test_failed_stuck_and_refused_runs_are_recorded_with_their_reason_and_the_others_go_on(tmp_path):
    outcomes = {TEXT: "failed", TEXT + " stuck": "stuck", TEXT + " fine": "completed"}
    be = MultiBe(await base_project(), outcome_of=lambda text: outcomes[text])
    ideas = write_ideas(tmp_path / "i.jsonl", idea("f"), idea("s", text=TEXT + " stuck"), idea("c", text=TEXT + " fine"))
    code, _ = await run_cli(tmp_path, be, ideas, "--timeout", "30")
    by_id = {r["idea_id"]: r for r in read_results(tmp_path)}
    assert {k: v["status"] for k, v in by_id.items()} == {"f": "failed", "s": "timeout", "c": "completed"}
    assert "generation_failed" in by_id["f"]["errors"][0] and by_id["s"]["errors"][0].startswith("timeout after 30")
    assert by_id["f"]["checks"]["ok"] is False and by_id["f"]["rows"]

    refused = MultiBe(await base_project(), create_status=500)
    out = tmp_path / "refused"
    out.mkdir()
    code, _ = await run_cli(out, refused, write_ideas(out / "i.jsonl", idea("a")))
    (record,) = read_results(out)
    assert record["status"] == "error" and "POST /api/generation was refused" in record["errors"][0] and record["rows"] == []


# --------------------------------------------------------------------------- the secret guard


async def test_no_key_password_or_token_reaches_any_output(tmp_path):
    be = MultiBe(await base_project())
    await run_cli(tmp_path, be, write_ideas(tmp_path / "i.jsonl", idea("a")), "--langfuse", environ=LF_KEYS)
    text = "".join(p.read_text() for p in (tmp_path / "out").rglob("*") if p.is_file())
    for secret in (PASSWORD, TOKEN, "pk-lf-EXPPUBLIC", "sk-lf-EXPSECRET"):
        assert secret not in text


async def test_a_project_that_carries_a_secret_is_not_written_and_the_line_says_why(tmp_path):
    def leak(project: dict) -> dict:
        project["title"] = f"leaked {TOKEN}"
        return project

    be = MultiBe(await base_project(), mutate=leak)
    await run_cli(tmp_path, be, write_ideas(tmp_path / "i.jsonl", idea("a")))
    (record,) = read_results(tmp_path)
    assert not (tmp_path / "out" / "projects" / "a-1.json").exists()
    assert any("project file not written" in e for e in record["errors"])
    assert TOKEN not in (tmp_path / "out" / "results.jsonl").read_text()


async def test_a_result_line_that_would_carry_a_connection_string_is_replaced_by_a_minimal_one(tmp_path):
    def leak(project: dict) -> dict:
        project["rows"][3]["error"] = {"code": "x", "message": "Endpoint=sb://example.servicebus.windows.net/;SharedAccessKey=abc"}
        return project

    be = MultiBe(await base_project(), outcome_of=lambda text: "failed", mutate=leak)
    await run_cli(tmp_path, be, write_ideas(tmp_path / "i.jsonl", idea("a")))
    (record,) = read_results(tmp_path)
    assert record["status"] == "error" and record["rows"] == [] and record["errors"] == ["result refused by the secret guard"]
    assert record["meta_ref"] == read_meta(tmp_path)["meta_ref"]
    everything = "".join(p.read_text() for p in (tmp_path / "out").rglob("*") if p.is_file())
    assert "SharedAccessKey" not in everything


# --------------------------------------------------------------------------- the config registry


class RecordingConfig(Config):
    """A second config: it starts the same pipeline project but records what it was given."""

    name = "recording"
    seen: list = []
    torn_down: list = []

    async def start(self, session, idea):
        type(self).seen.append(idea)
        response = await session.request("POST", "/api/generation", json={"idea": idea.text, "language": idea.language, "enabledOptional": [], "autoApprove": True})
        return response.json()["id"]

    async def teardown(self, session, project_id):
        type(self).torn_down.append(project_id)


async def test_a_second_config_runs_through_the_same_code(tmp_path, monkeypatch):
    monkeypatch.setitem(CONFIGS, "recording", RecordingConfig)
    RecordingConfig.seen, RecordingConfig.torn_down = [], []
    be = MultiBe(await base_project())
    code, _ = await run_cli(tmp_path, be, write_ideas(tmp_path / "i.jsonl", idea("a"), idea("b", text=TEXT + " b")), "--config", "recording")
    assert code == 0
    assert {r["config"] for r in read_results(tmp_path)} == {"recording"}
    assert [type(i).__name__ for i in RecordingConfig.seen] == ["IdeaInput", "IdeaInput"]
    assert all(HYPOTHESIS not in i.model_dump_json() for i in RecordingConfig.seen)
    assert sorted(RecordingConfig.torn_down) == ["p-1", "p-2"]


async def test_teardown_runs_even_when_the_project_fails(tmp_path, monkeypatch):
    monkeypatch.setitem(CONFIGS, "recording", RecordingConfig)
    RecordingConfig.seen, RecordingConfig.torn_down = [], []
    be = MultiBe(await base_project(), outcome_of=lambda text: "failed")
    await run_cli(tmp_path, be, write_ideas(tmp_path / "i.jsonl", idea("a")), "--config", "recording")
    assert RecordingConfig.torn_down == ["p-1"] and read_results(tmp_path)[0]["status"] == "failed"


def test_an_unknown_config_is_refused_by_the_parser(capsys):
    with pytest.raises(SystemExit):
        cli.build_parser().parse_args(["run", "--config", "agent", "--ideas", "x", "--out", "y"])
    assert "pipeline" in capsys.readouterr().err


def test_the_pipeline_config_asks_for_the_optional_stages_it_is_given():
    from experiments.configs import PipelineConfig

    assert PipelineConfig(RunOptions(enabled_optional=("business_case",))).options.enabled_optional == ("business_case",)


# --------------------------------------------------------------------------- the report


def record(idea_id, repeat, *, status="completed", wall=100.0, tokens=None, cycles=((2, 2),), violations=(), errors=(), checks_ok=True, problems=()):
    return {
        "idea_id": idea_id, "repeat": repeat, "config": "pipeline", "status": status, "wall_clock_s": wall,
        "tokens": None if tokens is None else {"total": tokens},
        "shape": {"segments": 1, "canvases": 1, "cycles": [{"iterations": i, "scores": [1] * i, "final_version": f} for i, f in cycles]},
        "rows": [{"violations": [{"rule_id": r, "severity": s, "count": n} for r, s, n in violations]}],
        "errors": list(errors), "checks": {"ok": checks_ok, "problems": list(problems)},
    }


FIXTURE = [
    record("a", 1, wall=100, tokens=1000, cycles=((2, 1),), violations=(("r1", "warning", 2),)),
    record("a", 2, wall=200, tokens=2000, cycles=((3, 2),), violations=(("r1", "warning", 1), ("r2", "error", 1))),
    record("a", 3, wall=300, tokens=3000, cycles=((3, 2),)),
    record("a", 4, wall=400, tokens=4000, cycles=((5, 4),)),
    record("b", 1, status="failed", wall=50, errors=["the project failed: pitch[0] generation_failed"], cycles=()),
    record("b", 2, wall=150, tokens=5000, cycles=((2, 1),), checks_ok=False, problems=["row canvas[0] is error, not done"]),
]


def test_the_report_numbers_on_a_fixture():
    summary = report_module.summarize(FIXTURE)
    a, b, overall = summary["a"], summary["b"], summary["ALL"]
    assert (a["n"], a["completed"], a["completion_rate"]) == (4, 4, 1.0)
    assert a["wall"] == (175.0, 250.0, 325.0)  # q1, median, q3 (inclusive) of 100..400
    assert a["tokens"] == (1750.0, 2500.0, 3250.0) and a["tokens_n"] == 4
    assert a["iterations"] == {2: 1, 3: 2, 5: 1} and a["final_version"] == {1: 1, 2: 2, 4: 1}
    assert a["violations"] == {("r1", "warning"): 3, ("r2", "error"): 1}
    assert a["failures"] == {}
    assert (b["n"], b["completed"], b["completion_rate"]) == (2, 1, 0.5)
    assert b["tokens"] == (5000.0, 5000.0, 5000.0) and b["tokens_n"] == 1  # one run with token data
    assert b["failures"] == {"failed: the project failed: pitch[0] generation_failed": 1, "checks: row canvas[0] is error, not done": 1}
    assert (overall["n"], overall["completed"]) == (6, 5) and overall["wall"][1] == statistics.median([100, 200, 300, 400, 50, 150])
    assert overall["violations"][("r1", "warning")] == 3


def test_the_latest_line_per_pair_counts_and_a_torn_line_is_ignored(tmp_path):
    path = tmp_path / "results.jsonl"
    path.write_text("\n".join([json.dumps(record("a", 1, status="failed")), json.dumps(record("a", 1)), '{"idea_id": "a", "rep']))
    records = report_module.load_latest(path)
    assert len(records) == 1 and records[0]["status"] == "completed"
    assert list(load_results(path)) == [("a", 1)]


def test_the_report_prints_tables_and_writes_csv(tmp_path, capsys):
    out = tmp_path / "run"
    out.mkdir()
    (out / "results.jsonl").write_text("\n".join(json.dumps(r) for r in FIXTURE))
    args = cli.build_parser().parse_args(["report", str(out)])
    assert cli.report_command(args) == 0
    printed = capsys.readouterr().out
    assert any(line.startswith("a ") and " 100%" in line for line in printed.splitlines()) and any(line.startswith("ALL") for line in printed.splitlines())
    assert "r1  [warning]" in printed and "failure reasons" in printed
    summary_rows = (out / "summary.csv").read_text().splitlines()
    assert summary_rows[0].startswith("scope,n,completed,completion_rate,wall_median_s")
    assert "a,4,4,1.0,250.0,175.0,325.0,4,2500.0,1750.0,3250.0" in summary_rows
    assert "a,iterations,3,2" in (out / "distributions.csv").read_text().splitlines()
    assert "a,r1,warning,3" in (out / "violations.csv").read_text()
    assert "b,failed: the project failed: pitch[0] generation_failed,1" in (out / "failures.csv").read_text()


def test_the_report_of_a_missing_or_empty_directory_fails_cleanly(tmp_path):
    assert cli.report_command(cli.build_parser().parse_args(["report", str(tmp_path)])) == 2
    (tmp_path / "results.jsonl").write_text("")
    assert cli.report_command(cli.build_parser().parse_args(["report", str(tmp_path)])) == 2


# --------------------------------------------------------------------------- what the tool may import


def imported_modules(path: Path) -> set[str]:
    tree = ast.parse(path.read_text())
    names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names |= {a.name.split(".")[0] for a in node.names}
        elif isinstance(node, ast.ImportFrom) and node.level == 0:
            names.add(node.module.split(".")[0])
    return names


def test_the_tool_imports_no_ml_worker_code():
    root = Path(__file__).resolve().parent.parent
    for path in (root / "experiments").glob("*.py"):
        assert "bizstruct_ml" not in imported_modules(path), path
    assert "bizstruct_ml" not in imported_modules(root / "scripts" / "e2e_smoke.py")


def test_the_report_uses_the_standard_library_only():
    stdlib = set(__import__("sys").stdlib_module_names)
    assert imported_modules(Path(report_module.__file__)) <= stdlib


async def test_the_shape_counts_canvas_rows_and_orders_the_swots_by_version(tmp_path):
    from tests.support.projects import scripted_llm, stage_runner
    from tests.support.fake_backend import FakeBackend
    from bizstruct_ml.judge.fake import FakeJudgeModel
    from tests.support.projects import NO_FINDINGS
    from bizstruct_domain.schemas import Stage

    backend = FakeBackend(through=Stage.PITCH)
    await backend.run_to_completion(stage_runner(scripted_llm(ONE, scores=(100, 95, 90, 85, 80)), FakeJudgeModel([NO_FINDINGS])))
    base = public_project(backend)
    base["rows"] = [r for r in base["rows"] if r["stage"] != "pitch"]  # the counts of canvas and pitch rows now differ
    be = MultiBe(base)
    await run_cli(tmp_path, be, write_ideas(tmp_path / "i.jsonl", idea("a")))
    (record,) = read_results(tmp_path)
    (cycle,) = record["shape"]["cycles"]
    assert record["shape"]["canvases"] == 1 and cycle["iterations"] == 5 and cycle["final_version"] == 5
    assert cycle["scores"] == [100, 95, 90, 85, 80]


# --------------------------------------------------------------------------- run_meta.json

ENV = {
    "AZURE_OPENAI_DEPLOYMENT": "gen-deployment", "AZURE_OPENAI_ENDPOINT": "https://user:hunter2@gen.openai.azure.com/path?key=abc",
    "JUDGE_PROVIDER": "azure_foundry_chat", "JUDGE_DEPLOYMENT": "judge-deployment", "JUDGE_ENDPOINT": "https://judge.services.ai.azure.com/openai/v1",
}
AZ = {"properties": {"model": {"name": "gpt-x", "version": "2026-05-01"}}}
ROOT = Path(__file__).resolve().parent.parent


def read_meta(tmp_path) -> dict:
    return json.loads((tmp_path / "out" / "run_meta.json").read_text())


async def meta_run(tmp_path, *argv, machine=None, environ=None, repos=None, ideas=None):
    be = MultiBe(await base_project())
    ideas = ideas or write_ideas(tmp_path / "i.jsonl", idea("a"))
    return await run_cli(tmp_path, be, ideas, *argv, machine=machine or Machine(az=AZ), environ=environ if environ is not None else ENV, repos=repos)


async def test_the_meta_records_the_conditions_of_the_run(tmp_path):
    machine = Machine(dirty={"bizstruct-ml"}, az=AZ)
    ideas = write_ideas(tmp_path / "i.jsonl", idea("a"))
    await meta_run(tmp_path, "--repeats", "1", "--concurrency", "2", "--max-runs", "5", "--azure-account-name", "acct", "--azure-resource-group", "rg",
                   "--compose-project", "bizstruct-smoke", machine=machine, ideas=ideas)
    meta = read_meta(tmp_path)
    assert meta["config"] == "pipeline" and meta["started_at"].endswith("+00:00")
    assert meta["ideas"] == {"path": str(ideas), "sha256": hashlib.sha256(ideas.read_bytes()).hexdigest(), "count": 1}
    assert (meta["repeats"], meta["concurrency"], meta["max_tokens"], meta["max_runs"]) == (1, 2, None, 5)
    assert meta["git"]["bizstruct-domain"] == {"head": "1" * 40, "branch": "main", "dirty": False}
    assert meta["git"]["bizstruct-ml"]["dirty"] is True and set(meta["git"]) == set(run_meta_module.SIBLING_REPOS)
    assert meta["domain_version"] == bizstruct_domain.__version__
    assert meta["uv_lock_sha256"] == hashlib.sha256((ROOT / "uv.lock").read_bytes()).hexdigest()
    assert meta["docker"] == {"compose_project": "bizstruct-smoke", "api_image_id": "sha256:img-c-api", "ml_image_id": "sha256:img-c-ml"}
    assert meta["generator"] == {"deployment": "gen-deployment", "endpoint_host": "gen.openai.azure.com", "model": "gpt-x", "model_version": "2026-05-01"}
    assert meta["judge"]["provider"] == "azure_foundry_chat" and meta["judge"]["deployment"] == "judge-deployment"
    assert meta["judge"]["endpoint_host"] == "judge.services.ai.azure.com" and meta["judge"]["model_version"] == "2026-05-01"
    assert meta["meta_warnings"] == [] and meta["resumes"] == []
    az_calls = [c for c in machine.calls if c[0] == "az"]
    assert len(az_calls) == 2 and "gen-deployment" in az_calls[0] and "judge-deployment" in az_calls[1]


async def test_the_prompt_versions_are_the_constants_of_the_ml_source(tmp_path):
    await meta_run(tmp_path)
    versions = read_meta(tmp_path)["prompt_versions"]
    assert {"brief", "swot", "errc", "storytelling", "future_scenario", "pitch", "canvas", "patterns"} <= set(versions)
    for stem, version in versions.items():
        assert version == importlib.import_module(f"bizstruct_ml.llm.prompts.{stem}").PROMPT_VERSION


def test_a_module_without_a_prompt_version_is_a_warning_not_an_omission(tmp_path):
    prompts = tmp_path / "src" / "bizstruct_ml" / "llm" / "prompts"
    prompts.mkdir(parents=True)
    (prompts / "good.py").write_text('PROMPT_VERSION = "7"\n')
    (prompts / "bad.py").write_text("X = 1\n")
    (prompts / "_private.py").write_text('PROMPT_VERSION = "9"\n')
    warnings: list[str] = []
    assert run_meta_module.prompt_versions(tmp_path, warnings) == {"bad": None, "good": "7"}
    assert warnings == ["prompt_versions.bad: no PROMPT_VERSION constant"]


async def test_only_hosts_and_names_are_recorded_and_the_command_is_redacted(tmp_path):
    await meta_run(tmp_path, "--azure-account-name", "acct")
    text = (tmp_path / "out" / "run_meta.json").read_text()
    for leaked in ("hunter2", "key=abc", PASSWORD, "user:"):
        assert leaked not in text
    meta = json.loads(text)
    command = meta["command"]
    assert command[command.index("--password") + 1] == "<redacted>" and "--azure-account-name" in command


def test_the_redaction_of_the_command_line():
    assert run_meta_module.redact_command(["run", "--password", "p1", "--email", "a@b.c", "--api-key=k2", "--token", "t3", "--out", "runs/x"]) == [
        "run", "--password", "<redacted>", "--email", "a@b.c", "--api-key=<redacted>", "--token", "<redacted>", "--out", "runs/x"]
    assert run_meta_module.redact_command(["--max-tokens", "100", "--max-tokens=5"]) == ["--max-tokens", "100", "--max-tokens=5"]  # a budget, not a credential


async def test_what_cannot_be_determined_is_null_with_a_reason_never_omitted(tmp_path):
    machine = Machine(docker=False, az=None)
    repos = fake_repos(tmp_path, names=("bizstruct-domain", "bizstruct-be", "bizstruct-ml"))  # no bizstruct-fe checkout
    await meta_run(tmp_path, machine=machine, environ={}, repos=repos)
    meta = read_meta(tmp_path)
    assert meta["git"]["bizstruct-fe"] is None and "bizstruct-fe" in meta["git"]
    assert meta["docker"]["api_image_id"] is None and meta["docker"]["ml_image_id"] is None
    assert meta["generator"]["deployment"] is None and meta["judge"]["deployment"] is None and meta["judge"]["provider"] is None
    warnings = "\n".join(meta["meta_warnings"])
    for expected in ("git.bizstruct-fe: no checkout", "docker.api_image_id: docker unavailable", "docker.ml_image_id: docker unavailable",
                     "generator.deployment: not set", "judge.deployment: not set", "judge.provider: JUDGE_PROVIDER not set"):
        assert expected in warnings


async def test_a_deployment_without_an_account_name_says_why_the_version_is_missing(tmp_path):
    await meta_run(tmp_path)
    meta = read_meta(tmp_path)
    assert meta["generator"]["model_version"] is None
    assert any("generator.model_version: --azure-account-name" in w for w in meta["meta_warnings"])


async def test_a_failing_az_is_a_warning_and_the_run_goes_on(tmp_path):
    code, _ = await meta_run(tmp_path, "--azure-account-name", "acct", "--azure-resource-group", "rg", machine=Machine(az=None))
    meta = read_meta(tmp_path)
    assert code == 0 and meta["generator"]["model_version"] is None
    assert any(w.startswith("generator.model_version: az failed") for w in meta["meta_warnings"])


async def test_a_container_that_is_not_running_is_a_warning(tmp_path):
    class NoContainers(Machine):
        def __call__(self, argv):
            return "" if argv[:2] == ["docker", "ps"] else super().__call__(argv)

    await meta_run(tmp_path, machine=NoContainers(az=AZ))
    assert any("no running container of service 'api'" in w for w in read_meta(tmp_path)["meta_warnings"])


@pytest.mark.parametrize(
    ("where", "machine", "environ"),
    [
        ("a connection string in a source", Machine(az={"properties": {"model": {"name": "Endpoint=sb://x.servicebus.windows.net/;SharedAccessKey=k", "version": "1"}}}), ENV),
        ("a connection string in the environment", Machine(az=AZ), {**ENV, "AZURE_OPENAI_DEPLOYMENT": "SharedAccessKey=abc"}),
        ("the password in the environment", Machine(az=AZ), {**ENV, "JUDGE_DEPLOYMENT": PASSWORD}),
        ("the token in a source", Machine(az=AZ), {**ENV, "JUDGE_DEPLOYMENT": TOKEN}),
    ],
)
async def test_a_secret_in_any_source_makes_the_write_refuse_and_the_run_does_not_start(tmp_path, where, machine, environ):
    be = MultiBe(await base_project())
    code, lines = await run_cli(tmp_path, be, write_ideas(tmp_path / "i.jsonl", idea("a")), "--azure-account-name", "acct", "--azure-resource-group", "rg",
                                machine=machine, environ=environ)
    assert code == 1 and any("run_meta.json was not written" in line for line in lines), where
    assert not (tmp_path / "out" / "run_meta.json").exists() and be.created == []
    assert not (tmp_path / "out" / "results.jsonl").exists()


async def test_a_secret_in_a_resumed_meta_leaves_the_existing_file_untouched(tmp_path):
    await meta_run(tmp_path, "--repeats", "1")
    before = (tmp_path / "out" / "run_meta.json").read_text()
    be = MultiBe(await base_project())
    code, lines = await run_cli(tmp_path, be, tmp_path / "i.jsonl", "--repeats", "2", machine=Machine(az=AZ), environ={**ENV, "JUDGE_DEPLOYMENT": TOKEN})
    assert code == 1 and (tmp_path / "out" / "run_meta.json").read_text() == before


async def test_every_result_line_carries_the_meta_ref_of_its_meta(tmp_path):
    await meta_run(tmp_path)
    meta = read_meta(tmp_path)
    (record,) = read_results(tmp_path)
    identity = run_meta_module.identity_of(meta)
    assert record["meta_ref"] == meta["meta_ref"] == hashlib.sha256(json.dumps(identity, sort_keys=True).encode()).hexdigest()
    assert "started_at" not in identity and "command" not in identity and "concurrency" not in identity


async def test_the_meta_ref_changes_with_a_sha_and_not_with_the_time_or_the_command(tmp_path):
    base = run_meta_module.collect_meta(command_line=["a"], config="pipeline", ideas_path=SAMPLE, idea_count=2, repeats=1, concurrency=1, max_tokens=None,
                                        max_runs=None, enable_optional=[], environ={}, cmd=Machine(), repos_root=fake_repos(tmp_path))
    again = run_meta_module.collect_meta(command_line=["b", "--repeats", "9"], config="pipeline", ideas_path=SAMPLE, idea_count=2, repeats=9, concurrency=4,
                                         max_tokens=5, max_runs=1, enable_optional=[], environ={}, cmd=Machine(), repos_root=fake_repos(tmp_path),
                                         now=datetime(2030, 1, 1, tzinfo=timezone.utc))
    moved = run_meta_module.collect_meta(command_line=["a"], config="pipeline", ideas_path=SAMPLE, idea_count=2, repeats=1, concurrency=1, max_tokens=None,
                                         max_runs=None, enable_optional=[], environ={}, cmd=Machine(heads={r: "9" * 40 for r in run_meta_module.SIBLING_REPOS}),
                                         repos_root=fake_repos(tmp_path))
    assert base["meta_ref"] == again["meta_ref"] != moved["meta_ref"]
    other_ideas = tmp_path / "other.jsonl"
    write_ideas(other_ideas, idea("zzz"))
    changed_ideas = run_meta_module.collect_meta(command_line=["a"], config="pipeline", ideas_path=other_ideas, idea_count=2, repeats=1, concurrency=1,
                                                 max_tokens=None, max_runs=None, enable_optional=[], environ={}, cmd=Machine(), repos_root=fake_repos(tmp_path))
    assert changed_ideas["meta_ref"] != base["meta_ref"]
    dirty = run_meta_module.collect_meta(command_line=["a"], config="pipeline", ideas_path=SAMPLE, idea_count=2, repeats=1, concurrency=1, max_tokens=None,
                                         max_runs=None, enable_optional=[], environ={}, cmd=Machine(dirty={"bizstruct-be"}), repos_root=fake_repos(tmp_path))
    assert dirty["meta_ref"] != base["meta_ref"]
    from unittest import mock

    with mock.patch.object(run_meta_module, "prompt_versions", lambda root, warnings: {"pitch": "42"}):
        prompts = run_meta_module.collect_meta(command_line=["a"], config="pipeline", ideas_path=SAMPLE, idea_count=2, repeats=1, concurrency=1, max_tokens=None,
                                               max_runs=None, enable_optional=[], environ={}, cmd=Machine(), repos_root=fake_repos(tmp_path))
    assert prompts["meta_ref"] != base["meta_ref"]


async def test_a_git_that_fails_gives_null_and_a_reason(tmp_path):
    class BrokenGit(Machine):
        def __call__(self, argv):
            if argv[0] == "git" and "bizstruct-be" in argv[2]:
                raise RuntimeError("fatal: not a git repository")
            return super().__call__(argv)

    await meta_run(tmp_path, machine=BrokenGit(az=AZ))
    meta = read_meta(tmp_path)
    assert meta["git"]["bizstruct-be"] is None and any(w.startswith("git.bizstruct-be: RuntimeError: fatal") for w in meta["meta_warnings"])


async def test_every_resume_is_appended_and_none_replaces_another(tmp_path):
    await meta_run(tmp_path, "--repeats", "1")
    await two_invocations_tail(tmp_path)
    be = MultiBe(await base_project())
    await run_cli(tmp_path, be, tmp_path / "i.jsonl", "--repeats", "3", machine=Machine(az=AZ), environ=ENV)
    assert [r["repeats"] for r in read_meta(tmp_path)["resumes"]] == [2, 3]


# -- a resumed run

async def two_invocations(tmp_path, second_machine, *, second_environ=None):
    await meta_run(tmp_path, "--repeats", "1")
    be = MultiBe(await base_project())
    return await run_cli(tmp_path, be, tmp_path / "i.jsonl", "--repeats", "2", machine=second_machine, environ=second_environ if second_environ is not None else ENV)


async def test_a_resume_keeps_the_first_meta_and_appends_the_new_one(tmp_path):
    await meta_run(tmp_path, "--repeats", "1")
    first = read_meta(tmp_path)
    code, lines = await two_invocations_tail(tmp_path)
    meta = read_meta(tmp_path)
    assert {k: v for k, v in meta.items() if k != "resumes"} == {k: v for k, v in first.items() if k != "resumes"}
    assert len(meta["resumes"]) == 1 and meta["resumes"][0]["repeats"] == 2 and "resumes" not in meta["resumes"][0]
    assert not any(line.startswith("WARNING") for line in lines)  # nothing changed


async def two_invocations_tail(tmp_path, machine=None, environ=None):
    be = MultiBe(await base_project())
    return await run_cli(tmp_path, be, tmp_path / "i.jsonl", "--repeats", "2", machine=machine or Machine(az=AZ), environ=environ if environ is not None else ENV)


@pytest.mark.parametrize(
    ("machine", "expected"),
    [
        (Machine(heads={**{r: str(n) * 40 for n, r in enumerate(run_meta_module.SIBLING_REPOS, 1)}, "bizstruct-ml": "f" * 40}, az=AZ),
         "bizstruct-ml head changed"),
        (Machine(dirty={"bizstruct-be"}, az=AZ), "bizstruct-be dirty flag changed: False -> True"),
    ],
)
async def test_a_resume_warns_when_a_sha_or_a_dirty_flag_differs(tmp_path, machine, expected):
    await meta_run(tmp_path, "--repeats", "1")
    code, lines = await two_invocations_tail(tmp_path, machine=machine)
    warnings = [line for line in lines if line.startswith("WARNING: this run is not comparable")]
    assert code == 0 and len(warnings) == 1 and expected in warnings[0]
    first, second = (r["meta_ref"] for r in sorted(read_results(tmp_path), key=lambda r: r["repeat"]))
    assert first != second  # the line of the second invocation is tied to the second meta


async def test_a_resume_warns_on_a_changed_domain_version_and_prompt_version(tmp_path, monkeypatch):
    await meta_run(tmp_path, "--repeats", "1")
    monkeypatch.setattr(bizstruct_domain, "__version__", "99.0.0")
    real = run_meta_module.prompt_versions
    monkeypatch.setattr(run_meta_module, "prompt_versions", lambda root, warnings: {**real(root, warnings), "pitch": "42"})
    code, lines = await two_invocations_tail(tmp_path)
    text = "\n".join(lines)
    assert "domain_version changed" in text and "99.0.0" in text and "prompt version of pitch changed: '1' -> '42'" in text


async def test_a_resume_warns_when_the_ideas_file_or_the_deployment_changed(tmp_path):
    await meta_run(tmp_path, "--repeats", "1")
    write_ideas(tmp_path / "i.jsonl", idea("a"), idea("b", text=TEXT + " b"))
    code, lines = await two_invocations_tail(tmp_path, environ={**ENV, "AZURE_OPENAI_DEPLOYMENT": "other-deployment"})
    text = "\n".join(lines)
    assert "ideas file sha256 changed" in text and "generator deployment changed: 'gen-deployment' -> 'other-deployment'" in text


async def test_the_report_prints_the_resume_warning_at_the_top(tmp_path, capsys):
    await meta_run(tmp_path, "--repeats", "1")
    machine = Machine(heads={r: "e" * 40 for r in run_meta_module.SIBLING_REPOS}, az=AZ)
    await two_invocations_tail(tmp_path, machine=machine)
    assert cli.report_command(cli.build_parser().parse_args(["report", str(tmp_path / "out")])) == 0
    out = capsys.readouterr().out.splitlines()
    assert out[0].startswith("WARNING: resume 1 (") and "head changed" in out[0]
    assert any("scope" in line for line in out[1:])  # the tables follow the warnings


async def test_the_report_has_no_warning_for_comparable_resumes_and_notes_a_missing_meta(tmp_path, capsys):
    await meta_run(tmp_path, "--repeats", "1")
    await two_invocations_tail(tmp_path)
    cli.report_command(cli.build_parser().parse_args(["report", str(tmp_path / "out")]))
    assert "WARNING" not in capsys.readouterr().out
    (tmp_path / "out" / "run_meta.json").unlink()
    cli.report_command(cli.build_parser().parse_args(["report", str(tmp_path / "out")]))
    assert capsys.readouterr().out.startswith("WARNING: no run_meta.json")


async def test_a_dry_run_writes_no_meta_and_runs_no_subprocess(tmp_path):
    machine = Machine()
    args = parse("--ideas", str(SAMPLE), "--out", str(tmp_path / "out"), "--dry-run")
    await cli.run_command(args, log=lambda line: None, meta_cmd=machine)
    assert machine.calls == [] and not (tmp_path / "out").exists()
