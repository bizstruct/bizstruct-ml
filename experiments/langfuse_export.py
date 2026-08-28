"""Exports per-block LLM metrics (tokens, latency, retries) from Langfuse
into metrics.csv, keyed off the project_ids already recorded in runs.jsonl.

Why a separate step from the runner (see README.md for the full rationale):
bizstruct-ml already traces every generation via Langfuse — session_id on
every trace equals project_id (see observability/tracing.py,
trace_block_generation()), so no extra cross-cutting id needs to be threaded
through the system for this to work. We just read it back out here instead
of duplicating token/latency capture with our own interceptor in the worker.

Two observation shapes per block, both queried by session_id=project_id:
  - SPAN, name="generate_block": one root span per block-processing attempt.
    metadata.block identifies the block; metadata.llm_retry_count (set by
    bizstruct_ml.generators.base.BaseGenerator.generate in its `finally`) is
    the authoritative retry count — not re-derived by counting spans here.
  - GENERATION, name="llm_call": one per LLM call attempt within a block.
    usage_details has {"input", "output", "total"} token counts; latency is
    in seconds. metadata.attempt distinguishes retries of the same block;
    the highest-attempt one is the call whose output actually got persisted.

Idempotent: existing (project_id, block) rows in metrics.csv are left
alone; only missing ones are appended. Safe to rerun while Langfuse's
batcher is still catching up.
"""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Any

from experiments.common import BLOCK_NAMES, RunRecord

BLOCK_SET = set(BLOCK_NAMES)

CSV_FIELDS = [
    "idea_id",
    "run_index",
    "project_id",
    "block",
    "input_tokens",
    "output_tokens",
    "latency_ms",
    "retries",
]


def _block_from_tags(tags: list[str] | None) -> str | None:
    if not tags:
        return None
    for t in tags:
        if t in BLOCK_SET:
            return t
    return None


def _paginate(get_many_fn, **kwargs) -> list[Any]:
    items: list[Any] = []
    cursor = None
    while True:
        resp = get_many_fn(cursor=cursor, limit=200, **kwargs)
        items.extend(resp.data)
        cursor = resp.meta.cursor
        if not cursor:
            break
    return items


def fetch_project_block_metrics(langfuse_client, project_id: str) -> dict[str, dict[str, Any]]:
    """Returns {block: {"input_tokens", "output_tokens", "latency_ms", "retries"}}
    for one project, or {} if nothing is in Langfuse yet for it."""
    api = langfuse_client.api

    spans = _paginate(
        api.observations.get_many,
        session_id=project_id,
        type="SPAN",
        name="generate_block",
        fields="basic,metadata,trace_context",
    )
    generations = _paginate(
        api.observations.get_many,
        session_id=project_id,
        type="GENERATION",
        name="llm_call",
        fields="basic,usage,metadata,metrics,trace_context",
    )

    retries_by_block: dict[str, int] = {}
    for s in spans:
        meta = s.metadata if isinstance(s.metadata, dict) else {}
        block = meta.get("block") or _block_from_tags(s.tags)
        if block is None:
            continue
        retries = meta.get("llm_retry_count")
        if isinstance(retries, int):
            retries_by_block[block] = retries

    best_by_block: dict[str, tuple[int, Any]] = {}
    for g in generations:
        block = _block_from_tags(g.tags)
        if block is None:
            continue
        meta = g.metadata if isinstance(g.metadata, dict) else {}
        attempt = meta.get("attempt", 1) if isinstance(meta.get("attempt", 1), int) else 1
        current = best_by_block.get(block)
        if current is None or attempt >= current[0]:
            best_by_block[block] = (attempt, g)

    result: dict[str, dict[str, Any]] = {}
    for block, (attempt, g) in best_by_block.items():
        usage = g.usage_details or {}
        retries = retries_by_block.get(block, max(attempt - 1, 0))
        result[block] = {
            "input_tokens": usage.get("input"),
            "output_tokens": usage.get("output"),
            "latency_ms": round(g.latency * 1000) if g.latency is not None else None,
            "retries": retries,
        }
    return result


def load_existing_metrics_keys(csv_path: Path) -> set[tuple[str, str]]:
    if not csv_path.exists():
        return set()
    keys = set()
    with csv_path.open("r", encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            keys.add((row["project_id"], row["block"]))
    return keys


def append_metrics_rows(csv_path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        return
    file_exists = csv_path.exists()
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    with csv_path.open("a", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_FIELDS)
        if not file_exists:
            writer.writeheader()
        writer.writerows(rows)


def export_metrics(
    langfuse_client,
    records: list[RunRecord],
    csv_path: Path,
) -> list[tuple[RunRecord, int, int]]:
    """Fetches Langfuse metrics for every project_id in `records` and appends
    missing rows to metrics.csv. Returns a list of (record, found_blocks,
    expected_blocks) for projects with incomplete Langfuse data — the
    caller reports these as "incomplete", per the experiment brief's
    completeness check."""
    existing_keys = load_existing_metrics_keys(csv_path)
    incomplete: list[tuple[RunRecord, int, int]] = []

    for record in records:
        if record.project_id is None:
            continue  # create_project itself failed — nothing was ever traced

        expected_blocks = record.blocks_completed
        if expected_blocks == 0:
            continue  # nothing generated for this project at all — nothing to export

        block_metrics = fetch_project_block_metrics(langfuse_client, record.project_id)

        rows = []
        for block, m in block_metrics.items():
            key = (record.project_id, block)
            if key in existing_keys:
                continue
            rows.append(
                {
                    "idea_id": record.idea_id,
                    "run_index": record.run_index,
                    "project_id": record.project_id,
                    "block": block,
                    "input_tokens": m["input_tokens"],
                    "output_tokens": m["output_tokens"],
                    "latency_ms": m["latency_ms"],
                    "retries": m["retries"],
                }
            )
            existing_keys.add(key)

        append_metrics_rows(csv_path, rows)

        # existing_keys already includes both what was in the CSV before
        # this call and what we just appended (updated above as rows were
        # built) — so this is the total distinct blocks now known for this
        # project, from Langfuse across this run and any prior export.
        found_blocks = len({b for (pid, b) in existing_keys if pid == record.project_id})

        if found_blocks < expected_blocks:
            incomplete.append((record, found_blocks, expected_blocks))

    return incomplete
