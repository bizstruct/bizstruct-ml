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

With --langfuse, after the project has finished the script reads the project's traces through the
Langfuse public API (LANGFUSE_PUBLIC_KEY, LANGFUSE_SECRET_KEY, LANGFUSE_HOST from the environment;
never printed) and prints the generator tokens per stage and in total next to the ranges recorded in
docs/token-ledger.md. The ml workers must be run with the same Langfuse keys. Without the keys the
script says so and carries on; the smoke checks do not depend on Langfuse.
"""


import argparse
import asyncio
import os
import sys
import time
from collections import Counter
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))  # the shared modules live in experiments/

from experiments.checks import OPTIONAL_STAGES, rows_table, run_checks  # noqa: E402
from experiments.client import Session, SmokeError, create_project, poll  # noqa: E402
from experiments.guard import write_dump  # noqa: E402
from experiments.langfuse import langfuse_section  # noqa: E402


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
    usage_lines: list[str] = field(default_factory=list)  # --langfuse: tokens per stage and in total

    @property
    def ok(self) -> bool:
        return self.reason is None and not self.problems


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
    langfuse: bool = False,
    langfuse_kwargs: dict[str, Any] | None = None,
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
        if langfuse:
            outcome.usage_lines = await langfuse_section(project, **(langfuse_kwargs or {}))
    outcome.wall_clock = clock() - started
    return outcome


def report(outcome: Outcome, log: Callable[[str], None] = print) -> None:
    if outcome.table:
        log("\n" + outcome.table)
    for line in outcome.summary:
        log(line)
    if outcome.dump_path:
        log(f"\ndump: {outcome.dump_path}")
    for line in outcome.usage_lines:
        log(line)
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
    parser.add_argument("--langfuse", action="store_true", help="after the run, print the generator tokens per stage read from Langfuse")
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
                langfuse=args.langfuse,
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
