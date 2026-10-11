"""Plan, resume and run an experiment: every (idea, repeat) pair through one config, K projects at a time, one
JSONL line per run. Uses be's public API (via `experiments.client`) and the domain package only."""

import asyncio
import json
import statistics
import time
from collections import Counter
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx
from bizstruct_domain import Swot, select_final_version

from experiments.checks import check_parse, run_checks
from experiments.client import Session, SmokeError, poll
from experiments.configs import Config
from experiments.guard import append_guarded, write_guarded
from experiments.ideaset import Idea
from experiments.langfuse import LEDGER_PATH, fetch_langfuse_usage, langfuse_settings, load_ledger

COMPLETED = "completed"
Key = tuple[str, int]


@dataclass(frozen=True)
class RunSpec:
    idea: Idea
    repeat: int

    @property
    def key(self) -> Key:
        return (self.idea.id, self.repeat)


def plan_runs(ideas: list[Idea], repeats: int) -> list[RunSpec]:
    """Repeat-major order (every idea once, then every idea again), so an interrupted experiment covers all ideas."""
    return [RunSpec(idea, repeat) for repeat in range(1, repeats + 1) for idea in ideas]


def load_results(path: Path) -> dict[Key, dict[str, Any]]:
    """The latest recorded line per (idea, repeat). A line that does not parse (a write cut short) is ignored."""
    latest: dict[Key, dict[str, Any]] = {}
    if not path.exists():
        return latest
    for line in path.read_text(encoding="utf-8").splitlines():
        try:
            record = json.loads(line)
            latest[(record["idea_id"], int(record["repeat"]))] = record
        except (json.JSONDecodeError, KeyError, TypeError, ValueError):
            continue
    return latest


@dataclass
class Selection:
    to_run: list[RunSpec]
    skipped: list[RunSpec] = field(default_factory=list)  # already recorded and not to be repeated
    retried: list[RunSpec] = field(default_factory=list)  # recorded as not completed, run again (--retry-failed)


def select_runs(plan: list[RunSpec], previous: dict[Key, dict[str, Any]], *, retry_failed: bool) -> Selection:
    """A pair that is recorded is skipped; with --retry-failed a pair recorded as anything but completed runs again."""
    selection = Selection(to_run=[])
    for spec in plan:
        record = previous.get(spec.key)
        if record is None:
            selection.to_run.append(spec)
        elif retry_failed and record.get("status") != COMPLETED:
            selection.to_run.append(spec)
            selection.retried.append(spec)
        else:
            selection.skipped.append(spec)
    return selection


def estimate_tokens(runs: int, ledger: dict[str, list[int]]) -> tuple[int, int, int] | None:
    """(low, median, high) token estimate for `runs` whole runs, from the whole-run totals in docs/token-ledger.md."""
    totals = ledger.get("ALL")
    if not totals:
        return None
    return runs * min(totals), int(runs * statistics.median(totals)), runs * max(totals)


def dry_run_lines(plan: list[RunSpec], selection: Selection, config: str, ledger: dict[str, list[int]]) -> list[str]:
    per_idea = Counter(spec.idea.id for spec in selection.to_run)
    lines = [
        f"plan: config {config}, {len(plan)} runs ({len({s.idea.id for s in plan})} ideas), "
        f"{len(selection.skipped)} already recorded, {len(selection.to_run)} to run ({len(selection.retried)} of them retried)"
    ]
    lines += [f"  {idea_id}: {n} run(s)" for idea_id, n in per_idea.items()]
    estimate = estimate_tokens(len(selection.to_run), ledger)
    if estimate is None:
        lines.append("estimated tokens: unknown (no whole-run totals in docs/token-ledger.md)")
    else:
        low, median, high = estimate
        lines.append(f"estimated tokens: about {median:,} (range {low:,} - {high:,}; whole-run totals of docs/token-ledger.md, judge not counted)")
    lines.append("dry run: nothing was called")
    return lines


# --------------------------------------------------------------------------- one run


def _utc(moment: datetime | None = None) -> str:
    return (moment or datetime.now(timezone.utc)).isoformat(timespec="seconds")


def _row_record(row: dict[str, Any]) -> dict[str, Any]:
    started, finished = row.get("startedAt"), row.get("finishedAt")
    duration = (datetime.fromisoformat(finished) - datetime.fromisoformat(started)).total_seconds() if started and finished else None
    violations = Counter((v.get("rule_id") or v.get("ruleId") or "?", v.get("severity", "?")) for v in ((row.get("consistency") or {}).get("violations") or []))
    return {
        "stage": row["stage"],
        "instance": row["instanceIndex"],
        "status": row["status"],
        "retries": row["retryCount"],
        "duration_s": duration,
        "violations": [{"rule_id": rule, "severity": severity, "count": n} for (rule, severity), n in sorted(violations.items())],
    }


def shape_of(project: dict[str, Any], parsed: dict[str, Any]) -> dict[str, Any]:
    """Segments, canvases and, per cycle row, the iterations, the score series and the derived final version."""
    rows = project["rows"]
    cycles = []
    for row in (r for r in rows if r["stage"] == "swot_errc_cycle"):
        swots = sorted((parsed[a["id"]] for a in row["artifacts"] if isinstance(parsed.get(a["id"]), Swot)), key=lambda w: w.canvas_version)
        scores = [w.weighted_weakness_threat_score for w in swots]
        cycles.append({"iterations": len(swots), "scores": scores, "final_version": select_final_version(scores) if scores else None})
    return {
        "segments": sum(r["stage"] == "empathy_map" for r in rows),
        "canvases": sum(r["stage"] == "canvas" for r in rows),
        "cycles": cycles,
    }


def _status_of(project: dict[str, Any] | None, reason: str | None) -> str:
    if project is not None and project["status"] == "completed":
        return COMPLETED
    if project is not None and project["status"] == "failed":
        return "failed"
    if reason and reason.startswith("timeout"):
        return "timeout"
    return "error"


@dataclass
class LangfuseOptions:
    public_key: str
    secret_key: str
    host: str
    wait: float = 90.0
    transport: httpx.AsyncBaseTransport | None = None


@dataclass
class Context:
    """What every run shares."""

    session: Session
    config: Config
    out_dir: Path
    timeout: float
    poll_interval: float
    langfuse: LangfuseOptions | None
    secrets: Callable[[], list[str]]
    meta_ref: str | None = None
    sleep: Callable[[float], Awaitable[None]] = asyncio.sleep
    clock: Callable[[], float] = time.monotonic
    now: Callable[[], datetime] = lambda: datetime.now(timezone.utc)
    log: Callable[[str], None] = print


async def execute_run(ctx: Context, spec: RunSpec) -> dict[str, Any]:
    """Run one pair to its end and return the record that goes to results.jsonl (the project file is written here)."""
    record: dict[str, Any] = {
        "idea_id": spec.idea.id, "repeat": spec.repeat, "config": ctx.config.name, "project_id": None,
        "started_at": _utc(ctx.now()), "finished_at": None, "status": "error", "wall_clock_s": None,
        "rows": [], "shape": None, "checks": None, "tokens": None, "errors": [], "meta_ref": ctx.meta_ref,
    }
    started = ctx.clock()
    project: dict[str, Any] | None = None
    reason: str | None = None
    try:
        record["project_id"] = await ctx.config.start(ctx.session, spec.idea.for_system())
        project, reason = await poll(
            ctx.session, record["project_id"], timeout=ctx.timeout, interval=ctx.poll_interval, sleep=ctx.sleep, clock=ctx.clock
        )
    except (SmokeError, httpx.HTTPError) as error:
        reason = f"{type(error).__name__}: {str(error)[:300]}"
    finally:
        if record["project_id"]:
            try:
                await ctx.config.teardown(ctx.session, record["project_id"])
            except Exception as error:  # a failing teardown must not lose the run
                record["errors"].append(f"teardown: {type(error).__name__}: {str(error)[:200]}")
    record["wall_clock_s"] = round(ctx.clock() - started, 2)
    record["finished_at"] = _utc(ctx.now())
    record["status"] = _status_of(project, reason)
    if reason:
        record["errors"].append(reason)

    if project is not None:
        record["rows"] = [_row_record(r) for r in project["rows"]]
        problems, _ = run_checks(project, list(ctx.config.options.enabled_optional))
        _, parsed = check_parse(project)
        record["shape"] = shape_of(project, parsed)
        record["checks"] = {"ok": not problems, "problems": problems}
        try:
            write_guarded(ctx.out_dir / "projects" / f"{spec.idea.id}-{spec.repeat}.json", json.dumps(project, indent=2, ensure_ascii=False), ctx.secrets())
        except SmokeError:  # the guard's own message names the pattern it matched, which would trip the guard again
            record["errors"].append("project file not written: the secret guard refused it")
        if ctx.langfuse is not None:
            try:
                usage = await fetch_langfuse_usage(
                    record["project_id"], host=ctx.langfuse.host, public_key=ctx.langfuse.public_key, secret_key=ctx.langfuse.secret_key,
                    expected_traces=len(project["rows"]), wait=ctx.langfuse.wait, sleep=ctx.sleep, transport=ctx.langfuse.transport,
                )
                record["tokens"] = {
                    "per_stage": {stage: {"calls": u.calls, "input": u.input, "output": u.output, "total": u.total} for stage, u in sorted(usage.per_stage.items())},
                    "total": usage.total, "traces": usage.traces, "rows_traced": usage.rows_traced,
                }
            except (SmokeError, httpx.HTTPError, KeyError, ValueError) as error:
                record["errors"].append(f"langfuse: {type(error).__name__}: {str(error)[:200]}")
    return record


# --------------------------------------------------------------------------- the experiment


@dataclass
class Budget:
    max_runs: int | None = None
    max_tokens: int | None = None
    tokens_used: int = 0
    launched: int = 0

    def stop_reason(self) -> str | None:
        if self.max_runs is not None and self.launched >= self.max_runs:
            return f"--max-runs {self.max_runs} reached"
        if self.max_tokens is not None and self.tokens_used > self.max_tokens:
            return f"--max-tokens {self.max_tokens:,} exceeded ({self.tokens_used:,} measured)"
        return None


@dataclass
class ExperimentResult:
    records: list[dict[str, Any]] = field(default_factory=list)
    stopped: str | None = None
    not_launched: int = 0


async def run_experiment(ctx: Context, specs: list[RunSpec], *, concurrency: int, budget: Budget) -> ExperimentResult:
    """Run the specs, at most `concurrency` projects at once; the budget is checked before every launch."""
    result = ExperimentResult()
    results_path = ctx.out_dir / "results.jsonl"
    semaphore = asyncio.Semaphore(concurrency)

    async def one(spec: RunSpec) -> None:
        try:
            record = await execute_run(ctx, spec)
            try:
                append_guarded(results_path, json.dumps(record, ensure_ascii=False), ctx.secrets())
            except SmokeError:  # keep a line, without the content that tripped the guard
                record = {k: record[k] for k in ("idea_id", "repeat", "config", "project_id", "started_at", "finished_at", "wall_clock_s", "meta_ref")}
                record |= {"status": "error", "rows": [], "shape": None, "checks": None, "tokens": None, "errors": ["result refused by the secret guard"]}
                append_guarded(results_path, json.dumps(record, ensure_ascii=False), ctx.secrets())
            result.records.append(record)
            if record.get("tokens"):
                budget.tokens_used += record["tokens"]["total"]
            ctx.log(f"[{len(result.records)}/{len(specs)}] {spec.idea.id}#{spec.repeat}: {record['status']} in {record['wall_clock_s']} s"
                    + (f", {record['tokens']['total']:,} tokens" if record.get("tokens") else ""))
        finally:
            semaphore.release()

    tasks: list[asyncio.Task[None]] = []
    for index, spec in enumerate(specs):
        await semaphore.acquire()  # a free slot first, so the budget sees every finished run
        reason = budget.stop_reason()
        if reason:
            result.stopped = reason
            result.not_launched = len(specs) - index
            break
        budget.launched += 1
        tasks.append(asyncio.create_task(one(spec)))
    await asyncio.gather(*tasks)
    return result


def langfuse_options(environ: Any, *, wait: float) -> LangfuseOptions | None:
    settings = langfuse_settings(environ)
    return None if settings is None else LangfuseOptions(*settings, wait=wait)


def default_ledger() -> dict[str, list[int]]:
    return load_ledger(LEDGER_PATH)
