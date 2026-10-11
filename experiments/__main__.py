"""python -m experiments run|report ... (see README.md, "Running experiments")."""

import argparse
import asyncio
import os
import sys
import time
from collections.abc import Awaitable, Callable
from pathlib import Path

import httpx

from experiments import report as report_module
from experiments.checks import OPTIONAL_STAGES
from experiments.client import Session, SmokeError
from experiments.configs import CONFIGS, RunOptions, get_config
from experiments.ideaset import IdeasFileError, load_ideas
from experiments.runner import (
    Budget,
    Context,
    default_ledger,
    dry_run_lines,
    langfuse_options,
    load_results,
    plan_runs,
    run_experiment,
    select_runs,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m experiments", description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)

    run = commands.add_parser("run", help="run ideas through a config")
    run.add_argument("--config", default="pipeline", choices=sorted(CONFIGS))
    run.add_argument("--ideas", type=Path, required=True, help="JSONL file, one idea per line")
    run.add_argument("--repeats", type=int, default=1)
    run.add_argument("--concurrency", type=int, default=1, help="projects running at once")
    run.add_argument("--out", type=Path, required=True, help="output directory, e.g. runs/first")
    run.add_argument("--max-tokens", type=int, help="stop launching runs once the Langfuse-measured total exceeds this")
    run.add_argument("--max-runs", type=int, help="launch at most this many runs in this invocation")
    run.add_argument("--retry-failed", action="store_true", help="run again the pairs recorded as not completed")
    run.add_argument("--dry-run", action="store_true", help="print the plan and the token estimate; call nothing")
    run.add_argument("--enable-optional", nargs="*", default=[], choices=OPTIONAL_STAGES)
    run.add_argument("--langfuse", action="store_true", help="measure tokens per stage through Langfuse (implied by --max-tokens)")
    run.add_argument("--langfuse-wait", type=float, default=90.0, help="seconds to wait for Langfuse to ingest a project's traces")
    run.add_argument("--base-url", help="be's base URL (required unless --dry-run)")
    run.add_argument("--email", help="the experiment user (required unless --dry-run)")
    run.add_argument("--password", default=os.environ.get("SMOKE_PASSWORD"), help="default: $SMOKE_PASSWORD")
    run.add_argument("--timeout", type=float, default=1800, help="seconds per project")
    run.add_argument("--poll-interval", type=float, default=5.0)

    report = commands.add_parser("report", help="summarise a run directory")
    report.add_argument("directory", type=Path)
    return parser


def validate_run_args(parser: argparse.ArgumentParser, args: argparse.Namespace) -> None:
    for name in ("repeats", "concurrency"):
        if getattr(args, name) < 1:
            parser.error(f"--{name} must be at least 1")
    if not args.dry_run:
        for name in ("base_url", "email", "password"):
            if not getattr(args, name):
                parser.error(f"--{name.replace('_', '-')} is required (the password may come from $SMOKE_PASSWORD) unless --dry-run")


async def run_command(
    args: argparse.Namespace,
    *,
    transport: httpx.AsyncBaseTransport | None = None,
    langfuse_transport: httpx.AsyncBaseTransport | None = None,
    environ=os.environ,
    log=print,
    sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
    clock: Callable[[], float] = time.monotonic,
) -> int:
    """`transport`, `langfuse_transport`, `environ`, `sleep` and `clock` are for the offline tests."""
    try:
        ideas = load_ideas(args.ideas)
    except IdeasFileError as error:
        log(f"FAIL: {error}")
        return 2
    options = RunOptions(enabled_optional=tuple(args.enable_optional))
    config = get_config(args.config, options)
    plan = plan_runs(ideas, args.repeats)
    results_path = args.out / "results.jsonl"
    selection = select_runs(plan, load_results(results_path), retry_failed=args.retry_failed)

    if args.dry_run:
        for line in dry_run_lines(plan, selection, config.name, default_ledger()):
            log(line)
        return 0

    langfuse = langfuse_options(environ, wait=args.langfuse_wait) if (args.langfuse or args.max_tokens) else None
    if (args.langfuse or args.max_tokens) and langfuse is None:
        log("Langfuse is not configured (LANGFUSE_PUBLIC_KEY / LANGFUSE_SECRET_KEY not both set): tokens are not measured"
            + ("; --max-tokens cannot be enforced, counting runs only (use --max-runs)" if args.max_tokens else ""))
    if langfuse is not None:
        langfuse.transport = langfuse_transport
    budget = Budget(max_runs=args.max_runs, max_tokens=args.max_tokens)
    log(f"{len(selection.to_run)} to run, {len(selection.skipped)} already recorded; concurrency {args.concurrency}; out {args.out}")
    if not selection.to_run:
        return 0

    async with httpx.AsyncClient(base_url=args.base_url, timeout=30.0, transport=transport) as client:
        session = Session(client, args.email, args.password)
        try:
            await session.ensure_user()
            await session.login()
        except SmokeError as error:
            log(f"FAIL: {error}")
            return 1
        secrets = lambda: [args.password, session.token or "", *(([langfuse.public_key, langfuse.secret_key]) if langfuse else [])]  # noqa: E731
        ctx = Context(session=session, config=config, out_dir=args.out, timeout=args.timeout, poll_interval=args.poll_interval,
                      langfuse=langfuse, secrets=secrets, sleep=sleep, clock=clock, log=log)
        result = await run_experiment(ctx, selection.to_run, concurrency=args.concurrency, budget=budget)
    completed = sum(r["status"] == "completed" for r in result.records)
    log(f"done: {len(result.records)} runs, {completed} completed" + (f"; stopped: {result.stopped} ({result.not_launched} not launched)" if result.stopped else ""))
    if langfuse is not None:
        log(f"tokens measured this invocation: {budget.tokens_used:,}")
    return 0


def report_command(args: argparse.Namespace, log=print) -> int:
    path = args.directory / "results.jsonl"
    if not path.exists():
        log(f"FAIL: {path} does not exist")
        return 2
    records = report_module.load_latest(path)
    if not records:
        log(f"FAIL: {path} holds no runs")
        return 2
    summary = report_module.summarize(records)
    log(report_module.render(summary))
    for written in report_module.write_csv(summary, args.directory):
        log(f"wrote {written}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.command == "report":
        return report_command(args)
    validate_run_args(parser, args)
    return asyncio.run(run_command(args))


if __name__ == "__main__":
    sys.exit(main())
