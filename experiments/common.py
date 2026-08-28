"""Shared types, dataset loading, and config for the baseline-experiment
tooling in this directory.

Nothing here is imported by `bizstruct_ml` — see `__init__.py`.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, Field

# The 8 blocks bizstruct-ml generates, in the domain chain order given in
# the experiment brief. Used only to count "how many blocks did this
# project finish" and to know which ProjectResponse fields hold generated
# content — NOT to reimplement or assume ordering logic that belongs to
# bizstruct-be/bizstruct-domain.
BLOCK_NAMES: tuple[str, ...] = (
    "empathy_map",
    "models_options",
    "canvas",
    "architecture",
    "what_if",
    "hypotheses",
    "scenario",
    "pitch",
)

# GET /api/projects/{id} returns ProjectResponse, which aliases every field
# to camelCase (CamelModel's alias_generator=to_camel — see bizstruct-be's
# app/schemas.py). BLOCK_NAMES above are the snake_case block ids used
# everywhere else in this system (QueueMessage.block, Langfuse trace
# metadata, bizstruct_ml's generator registry) — this is only for reading
# the HTTP response body.
BLOCK_JSON_KEYS: dict[str, str] = {
    "empathy_map": "empathyMap",
    "models_options": "modelsOptions",
    "canvas": "canvas",
    "architecture": "architecture",
    "what_if": "whatIf",
    "hypotheses": "hypotheses",
    "scenario": "scenario",
    "pitch": "pitch",
}

TERMINAL_STATUSES = {"completed", "failed"}

RunStatus = Literal["completed", "failed", "timeout"]


def utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class Idea(BaseModel):
    id: str
    text: str
    expected_pattern: str
    detail_level: str
    market_type: str
    industry: str
    variance_subset: bool = False


class RunTask(BaseModel):
    """One (idea, run_index, language) unit of work — what the runner schedules."""

    idea: Idea
    run_index: int  # 0 for the single main-coverage run, 1-4 for variance reruns
    language: str = "en"  # generation language ("uk"/"en") — part E's per-project parameter

    @property
    def key(self) -> tuple[str, int, str]:
        return (self.idea.id, self.run_index, self.language)


class RunRecord(BaseModel):
    """One row of runs.jsonl — the full result of one (idea, run_index)."""

    idea_id: str
    run_index: int
    language: str = "en"
    project_id: str | None = None
    started_at: str
    finished_at: str | None = None
    expected_pattern: str
    detail_level: str
    market_type: str
    industry: str
    status: RunStatus
    duration_seconds: float | None = None
    blocks_completed: int = 0
    blocks: dict[str, Any] = Field(default_factory=dict)
    error: str | None = None


def load_dataset(path: Path) -> list[Idea]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    ideas = [Idea.model_validate(item) for item in raw]

    ids = [i.id for i in ideas]
    if len(ids) != len(set(ids)):
        dupes = {x for x in ids if ids.count(x) > 1}
        raise ValueError(f"Duplicate idea ids in dataset: {sorted(dupes)}")

    variance_ids = [i.id for i in ideas if i.variance_subset]
    if len(variance_ids) != 10:
        raise ValueError(
            f"Expected exactly 10 ideas with variance_subset=true, found {len(variance_ids)}: "
            f"{variance_ids}"
        )

    return ideas


def build_plan(ideas: list[Idea], mode: str, language: str = "en") -> list[RunTask]:
    """mode: 'main' -> one run per idea (run_index=0) for all 100.
    'variance' -> 4 extra reruns (run_index 1-4) for the 10 variance_subset ideas.
    'pilot' -> handled by the caller (it's just build_plan('main', ...)[:n]).
    'language_comparison' -> one run (run_index=0) for each of the 10
    variance_subset ideas, at the given `language` — the CLI runs this once
    per language ('uk' then 'en') into separate results directories (part F
    of the data-quality-fixes brief).
    'calibration' -> the first 5 ideas in dataset.json's own order
    (idea-001..idea-005), run_index=0, at the given language — the rubric-
    calibration set (see experiments/calibration/)."""
    if mode in ("main", "pilot"):
        return [RunTask(idea=i, run_index=0, language=language) for i in ideas]
    if mode == "variance":
        tasks = []
        for i in ideas:
            if i.variance_subset:
                tasks.extend(RunTask(idea=i, run_index=r, language=language) for r in range(1, 5))
        return tasks
    if mode == "language_comparison":
        return [RunTask(idea=i, run_index=0, language=language) for i in ideas if i.variance_subset]
    if mode == "calibration":
        return [RunTask(idea=i, run_index=0, language=language) for i in ideas[:5]]
    raise ValueError(f"Unknown mode: {mode}")


def load_existing_results(runs_path: Path) -> dict[tuple[str, int, str], RunRecord]:
    """Read runs.jsonl and return {(idea_id, run_index, language): RunRecord}
    for every row already resolved to a terminal status — used to skip
    already-done work on restart. Corrupt trailing lines (process killed
    mid-write) are skipped with a warning, not fatal."""
    results: dict[tuple[str, int, str], RunRecord] = {}
    if not runs_path.exists():
        return results

    with runs_path.open("r", encoding="utf-8") as f:
        for line_no, line in enumerate(f, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                record = RunRecord.model_validate_json(line)
            except Exception as e:  # noqa: BLE001 - genuinely tolerate any bad line
                print(f"[warn] runs.jsonl:{line_no}: skipping unparseable line ({e})")
                continue
            results[(record.idea_id, record.run_index, record.language)] = record
    return results


def append_result(runs_path: Path, record: RunRecord) -> None:
    """Append one JSON line and flush+fsync immediately, so a killed process
    never leaves a half-written or lost result."""
    runs_path.parent.mkdir(parents=True, exist_ok=True)
    with runs_path.open("a", encoding="utf-8") as f:
        f.write(record.model_dump_json())
        f.write("\n")
        f.flush()
        os.fsync(f.fileno())


def require_env(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise SystemExit(
            f"Missing required environment variable {name}. "
            "This script does not fall back to localhost or any other default — "
            "set it explicitly (see experiments/README.md)."
        )
    return value
