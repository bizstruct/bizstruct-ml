"""End-to-end smoke of bizstruct-be + bizstruct-ml through be's PUBLIC API only.

Creates a user (an existing one is fine), logs in, starts a generation with
autoApprove on, polls the project until it is completed or failed (or the timeout
hits), then prints the rows and checks the outcome: the project completed, every
row done, the row counts match the project's shape, no duplicated rows, and every
artifact parses with the domain's `parse_artifact` (the final canvas of each canvas
row is derived with `final_canvas`). Exit code 0 only if every check passes.

Pure HTTP (httpx) plus the domain package; it imports no ml worker code, so it
exercises the same surface the future experiment runner will.

    uv run python scripts/e2e_smoke.py --base-url http://localhost:18000 \\
        --email smoke@example.com --idea "An app that delivers boxes of fresh produce ..." \\
        --language en --timeout 1800

The password comes from --password or the SMOKE_PASSWORD environment variable.
The project JSON is dumped to --dump-dir/<timestamp>.json (git-ignored); the dump is
checked for tokens, passwords and connection strings before it is written.
"""

import argparse
import asyncio
import json
import os
import re
import sys
import time
from collections import Counter
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

import httpx
from bizstruct_domain import (
    ArtifactRecord,
    ArtifactType,
    Brief,
    Canvas,
    Patterns,
    Stage,
    Swot,
    final_canvas,
    parse_artifact,
)

OPTIONAL_STAGES = ("business_case", "environment_scan")
POLL_TRANSIENT_LIMIT = 5

# What must never appear in a dump.
SECRET_PATTERNS = (re.compile(r"SharedAccessKey", re.I), re.compile(r"Endpoint=sb://", re.I), re.compile(r"sb://[\w.-]+\.servicebus", re.I))


@dataclass
class Outcome:
    """The result of one smoke run."""

    project: dict[str, Any] | None = None
    reason: str | None = None  # why the run failed before the checks (failed project, timeout, unreachable)
    problems: list[str] = field(default_factory=list)
    wall_clock: float = 0.0
    dump_path: Path | None = None
    table: str = ""
    summary: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return self.reason is None and not self.problems


class SmokeError(Exception):
    """The run cannot continue (login failed, generation refused)."""


# --------------------------------------------------------------------------- session


class Session:
    """An authenticated httpx client that logs in again if the access token expires mid-run."""

    def __init__(self, client: httpx.AsyncClient, email: str, password: str) -> None:
        self.client = client
        self.email = email
        self.password = password
        self.token: str | None = None

    async def ensure_user(self) -> None:
        response = await self.client.post("/api/users/", json={"email": self.email, "password": self.password})
        if response.status_code not in (201, 409):  # 409: the user already exists, which is fine
            raise SmokeError(f"creating the user failed: HTTP {response.status_code}: {response.text[:300]}")

    async def login(self) -> None:
        response = await self.client.post("/api/auth/login", data={"username": self.email, "password": self.password})
        if response.status_code != 200:
            raise SmokeError(f"login failed: HTTP {response.status_code}: {response.text[:300]}")
        self.token = response.json()["access_token"]

    async def request(self, method: str, url: str, **kwargs: Any) -> httpx.Response:
        for attempt in (1, 2):
            headers = {"Authorization": f"Bearer {self.token}"}
            response = await self.client.request(method, url, headers=headers, **kwargs)
            if response.status_code == 401 and attempt == 1:
                await self.login()
                continue
            return response
        raise AssertionError("unreachable")


# --------------------------------------------------------------------------- run


async def create_project(session: Session, *, idea: str, language: str, enabled_optional: list[str]) -> dict[str, Any]:
    body = {"idea": idea, "language": language, "enabledOptional": enabled_optional, "autoApprove": True}
    response = await session.request("POST", "/api/generation", json=body)
    if response.status_code != 201:
        raise SmokeError(f"POST /api/generation was refused: HTTP {response.status_code}: {response.text[:500]}")
    return response.json()


async def poll(
    session: Session,
    project_id: str,
    *,
    timeout: float,
    interval: float,
    sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
    clock: Callable[[], float] = time.monotonic,
    on_progress: Callable[[dict[str, Any]], None] | None = None,
) -> tuple[dict[str, Any] | None, str | None]:
    """Polls until the project is completed or failed. Returns (last project JSON, failure reason or None)."""
    deadline = clock() + timeout
    last: dict[str, Any] | None = None
    transient = 0
    while True:
        try:
            response = await session.request("GET", f"/api/projects/{project_id}")
        except httpx.HTTPError as error:
            response = None
            problem = f"{type(error).__name__}: {error}"
        else:
            problem = f"HTTP {response.status_code}"
        if response is not None and response.status_code == 200:
            transient = 0
            last = response.json()
            if on_progress is not None:
                on_progress(last)
            if last["status"] == "completed":
                return last, None
            if last["status"] == "failed":
                return last, "the project failed: " + _failure_summary(last)
        elif response is not None and response.status_code < 500:
            return last, f"GET /api/projects/{project_id} answered {problem}: {response.text[:300]}"
        else:
            transient += 1
            if transient >= POLL_TRANSIENT_LIMIT:
                return last, f"be unreachable: {POLL_TRANSIENT_LIMIT} polls in a row failed ({problem})"
        if clock() >= deadline:
            return last, f"timeout after {timeout:g} s; status {last['status'] if last else 'unknown'}"
        await sleep(interval)


def _failure_summary(project: dict[str, Any]) -> str:
    failed = [r for r in project["rows"] if r["status"] == "error"]
    return "; ".join(
        f"{r['stage']}[{r['instanceIndex']}] {r['error']['code'] if r['error'] else '?'}: "
        f"{(r['error'] or {}).get('message', '')[:200]}"
        for r in failed
    ) or "no row in error"


# --------------------------------------------------------------------------- report


def _seconds(row: dict[str, Any]) -> float | None:
    if not row.get("startedAt") or not row.get("finishedAt"):
        return None
    return (datetime.fromisoformat(row["finishedAt"]) - datetime.fromisoformat(row["startedAt"])).total_seconds()


def _violations(row: dict[str, Any]) -> str:
    counts = Counter(v["severity"] for v in ((row.get("consistency") or {}).get("violations") or []))
    return f"{counts['error']}e/{counts['warning']}w"


def rows_table(project: dict[str, Any]) -> str:
    header = ("stage", "idx", "status", "retries", "duration", "error", "violations")
    lines = [header]
    for row in project["rows"]:
        seconds = _seconds(row)
        lines.append(
            (
                row["stage"],
                str(row["instanceIndex"]),
                row["status"],
                str(row["retryCount"]),
                f"{seconds:.1f}s" if seconds is not None else "-",
                (row["error"] or {}).get("code", "-") if row["error"] else "-",
                _violations(row),
            )
        )
    widths = [max(len(line[i]) for line in lines) for i in range(len(header))]
    return "\n".join("  ".join(cell.ljust(widths[i]) for i, cell in enumerate(line)).rstrip() for line in lines)


# --------------------------------------------------------------------------- checks


def _artifacts(project: dict[str, Any]) -> list[tuple[dict[str, Any], dict[str, Any]]]:
    return [(row, artifact) for row in project["rows"] for artifact in row["artifacts"]]


def check_parse(project: dict[str, Any]) -> tuple[list[str], dict[str, Any]]:
    """Parses every artifact; returns the problems and the parsed models by artifact id."""
    problems: list[str] = []
    parsed: dict[str, Any] = {}
    for row, artifact in _artifacts(project):
        label = f"{row['stage']}[{row['instanceIndex']}] {artifact['type']} {artifact['id']}"
        try:
            parsed[artifact["id"]] = parse_artifact(
                ArtifactRecord(id=artifact["id"], type=ArtifactType(artifact["type"]), data=artifact["data"])
            )
        except Exception as error:  # a pydantic ValidationError, a ValueError or an unknown type
            problems.append(f"does not parse: {label}: {str(error).splitlines()[0][:200]}")
    return problems, parsed


def check_final_canvases(project: dict[str, Any], parsed: dict[str, Any]) -> tuple[list[str], list[str]]:
    """Derives the final canvas of every canvas row from its v1 and its cycle row's Swots and later canvases."""
    problems: list[str] = []
    lines: list[str] = []
    rows = project["rows"]
    for canvas_row in (r for r in rows if r["stage"] == "canvas"):
        cycles = [r for r in rows if r["stage"] == "swot_errc_cycle" and r["refs"].get("canvas") == [canvas_row["id"]]]
        label = f"canvas[{canvas_row['instanceIndex']}]"
        if len(cycles) != 1:
            problems.append(f"{label}: expected one swot_errc_cycle row, found {len(cycles)}")
            continue
        models = [parsed[a["id"]] for r in (canvas_row, cycles[0]) for a in r["artifacts"] if a["id"] in parsed]
        canvases = [m for m in models if isinstance(m, Canvas)]
        swots = [m for m in models if isinstance(m, Swot)]
        try:
            final = final_canvas(canvases, swots)
        except ValueError as error:
            problems.append(f"{label}: cannot derive the final canvas: {error}")
            continue
        lines.append(f"{label}: {len(canvases)} canvas versions, {len(swots)} swots, final version {final.version}")
    return problems, lines


def check_shape(project: dict[str, Any], parsed: dict[str, Any], expected_optional: list[str]) -> list[str]:
    problems: list[str] = []
    rows = project["rows"]
    counts = Counter(r["stage"] for r in rows)

    brief = next((a for r in rows if r["stage"] == "brief" for a in r["artifacts"] if a["id"] in parsed), None)
    segments = counts["empathy_map"]
    if brief is not None and isinstance(parsed[brief["id"]], Brief):
        candidates = len(parsed[brief["id"]].customer_segment_candidates)
        if segments != candidates:
            problems.append(f"empathy_map rows ({segments}) differ from the brief's segment candidates ({candidates})")

    patterns = next((parsed[a["id"]] for r in rows if r["stage"] == "patterns" for a in r["artifacts"] if isinstance(parsed.get(a["id"]), Patterns)), None)
    canvases = counts["canvas"]
    if patterns is not None and canvases != len(patterns.groups):
        problems.append(f"canvas rows ({canvases}) differ from the Patterns groups ({len(patterns.groups)})")

    expected = {
        "brief": 1,
        "patterns": 1,
        "empathy_map": segments,
        "customer_scenario": segments,
        "ideation": segments,
        "canvas": canvases,
        "swot_errc_cycle": canvases,
        "storytelling": canvases,
        "future_scenario": canvases,
        "pitch": canvases,
    }
    for stage in OPTIONAL_STAGES:
        expected[stage] = 1 if stage in expected_optional else 0
    expected["team_info"] = 0
    if segments < 1 or canvases < 1:
        problems.append(f"a project needs at least one empathy_map and one canvas row, found {segments} and {canvases}")
    for stage, want in expected.items():
        if counts[stage] != want:
            problems.append(f"{stage}: expected {want} rows, found {counts[stage]}")
    for stage in counts.keys() - expected.keys():
        problems.append(f"unexpected stage {stage}: {counts[stage]} rows")
    return problems


def check_duplicates(project: dict[str, Any]) -> list[str]:
    problems: list[str] = []
    rows = project["rows"]
    for row_id, n in Counter(r["id"] for r in rows).items():
        if n > 1:
            problems.append(f"row id {row_id} appears {n} times")
    keys = Counter((r["stage"], r["instanceIndex"], json.dumps(r["refs"], sort_keys=True)) for r in rows)
    for (stage, index, _), n in keys.items():
        if n > 1:
            problems.append(f"duplicated row: {stage}[{index}] with the same refs appears {n} times")
    for artifact_id, n in Counter(a["id"] for _, a in _artifacts(project)).items():
        if n > 1:
            problems.append(f"artifact id {artifact_id} appears {n} times")
    return problems


def run_checks(project: dict[str, Any], expected_optional: list[str]) -> tuple[list[str], list[str]]:
    """All checks on a finished project. Returns (problems, informational lines)."""
    problems: list[str] = []
    if project["status"] != "completed":
        problems.append(f"project status is {project['status']}, not completed")
    for row in project["rows"]:
        if row["status"] != "done":
            problems.append(f"row {row['stage']}[{row['instanceIndex']}] is {row['status']}, not done")
    parse_problems, parsed = check_parse(project)
    problems += parse_problems
    problems += check_shape(project, parsed, expected_optional)
    problems += check_duplicates(project)
    canvas_problems, lines = check_final_canvases(project, parsed)
    return problems + canvas_problems, lines


def assert_no_secrets(text: str, secrets: list[str]) -> None:
    """Raises if the text holds a known secret value or a connection-string marker."""
    for secret in (s for s in secrets if s):
        if secret in text:
            raise SmokeError("refusing to write the dump: it contains a token or password")
    for pattern in SECRET_PATTERNS:
        if pattern.search(text):
            raise SmokeError(f"refusing to write the dump: it matches {pattern.pattern!r}")


def write_dump(project: dict[str, Any], dump_dir: Path, secrets: list[str], now: datetime | None = None) -> Path:
    text = json.dumps(project, indent=2, ensure_ascii=False)
    assert_no_secrets(text, secrets)
    dump_dir.mkdir(parents=True, exist_ok=True)
    path = dump_dir / f"{(now or datetime.now()).strftime('%Y%m%d-%H%M%S')}.json"
    path.write_text(text, encoding="utf-8")
    return path


# --------------------------------------------------------------------------- orchestration


async def run_smoke(
    client: httpx.AsyncClient,
    *,
    email: str,
    password: str,
    idea: str,
    language: str,
    timeout: float,
    enabled_optional: list[str],
    dump_dir: Path,
    interval: float = 5.0,
    sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
    clock: Callable[[], float] = time.monotonic,
    log: Callable[[str], None] = print,
) -> Outcome:
    started = clock()
    outcome = Outcome()
    session = Session(client, email, password)
    await session.ensure_user()
    await session.login()
    created = await create_project(session, idea=idea, language=language, enabled_optional=enabled_optional)
    project_id = created["id"]
    log(f"project {project_id} created; polling every {interval:g} s (timeout {timeout:g} s)")

    last_line = ""

    def progress(project: dict[str, Any]) -> None:
        nonlocal last_line
        counts = Counter(r["status"] for r in project["rows"])
        line = f"[{clock() - started:6.0f}s] {project['status']}: {len(project['rows'])} rows, " + ", ".join(f"{n} {s}" for s, n in sorted(counts.items()))
        if line != last_line:
            log(line)
            last_line = line

    project, reason = await poll(session, project_id, timeout=timeout, interval=interval, sleep=sleep, clock=clock, on_progress=progress)
    outcome.project = project
    outcome.reason = reason
    if project is not None:
        outcome.table = rows_table(project)
        problems, lines = run_checks(project, enabled_optional)
        outcome.problems = problems
        outcome.summary = lines
        outcome.dump_path = write_dump(project, dump_dir, [password, session.token or ""])
    outcome.wall_clock = clock() - started
    return outcome


def report(outcome: Outcome, log: Callable[[str], None] = print) -> None:
    if outcome.table:
        log("\n" + outcome.table)
    for line in outcome.summary:
        log(line)
    if outcome.dump_path:
        log(f"\ndump: {outcome.dump_path}")
    log(f"total wall-clock: {outcome.wall_clock:.1f} s")
    if outcome.reason:
        log(f"FAIL: {outcome.reason}")
    for problem in outcome.problems:
        log(f"FAIL: {problem}")
    log("OK: every check passed" if outcome.ok else "RESULT: FAILED")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--base-url", required=True)
    parser.add_argument("--email", required=True)
    parser.add_argument("--password", default=os.environ.get("SMOKE_PASSWORD"), help="default: $SMOKE_PASSWORD")
    parser.add_argument("--idea", required=True, help="50-2000 characters (be enforces it)")
    parser.add_argument("--language", choices=("en", "uk"), default="en")
    parser.add_argument("--timeout", type=float, default=1800)
    parser.add_argument("--enable-optional", nargs="*", default=[], choices=OPTIONAL_STAGES)
    parser.add_argument("--dump-dir", type=Path, default=Path("smoke-dumps"))
    parser.add_argument("--poll-interval", type=float, default=5.0)
    args = parser.parse_args(argv)
    if not args.password:
        parser.error("--password or $SMOKE_PASSWORD is required")
    if not 50 <= len(args.idea.strip()) <= 2000:
        parser.error("--idea must be 50-2000 characters")
    return args


async def amain(args: argparse.Namespace) -> int:
    async with httpx.AsyncClient(base_url=args.base_url, timeout=30.0) as client:
        try:
            outcome = await run_smoke(
                client,
                email=args.email,
                password=args.password,
                idea=args.idea,
                language=args.language,
                timeout=args.timeout,
                enabled_optional=args.enable_optional,
                dump_dir=args.dump_dir,
                interval=args.poll_interval,
            )
        except SmokeError as error:
            print(f"FAIL: {error}")
            return 1
    report(outcome)
    return 0 if outcome.ok else 1


def main() -> None:
    sys.exit(asyncio.run(amain(parse_args())))


if __name__ == "__main__":
    main()
