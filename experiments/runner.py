"""Runs the dataset (or a slice of it) through the live system and writes
runs.jsonl incrementally. See README.md for the pilot/main/variance modes.
"""

from __future__ import annotations

import asyncio
import time
from pathlib import Path

from experiments.common import (
    BLOCK_JSON_KEYS,
    BLOCK_NAMES,
    RunRecord,
    RunTask,
    append_result,
    load_existing_results,
    utcnow_iso,
)
from experiments.http import BackendClient


async def run_one(
    client: BackendClient,
    task: RunTask,
    *,
    poll_interval: float,
    project_timeout: float,
) -> RunRecord:
    started_at = utcnow_iso()
    start_monotonic = time.monotonic()
    title = f"[experiment] {task.idea.id} run{task.run_index}"

    try:
        project_id = await client.create_project(task.idea.text, title)
    except Exception as e:  # noqa: BLE001 - a failed *launch* is still a recorded result, not a crash
        return RunRecord(
            idea_id=task.idea.id,
            run_index=task.run_index,
            project_id=None,
            started_at=started_at,
            finished_at=utcnow_iso(),
            expected_pattern=task.idea.expected_pattern,
            detail_level=task.idea.detail_level,
            market_type=task.idea.market_type,
            industry=task.idea.industry,
            status="failed",
            duration_seconds=time.monotonic() - start_monotonic,
            blocks_completed=0,
            blocks={},
            error=f"create_project failed: {e}",
        )

    status = "timeout"
    project: dict = {}
    error: str | None = None

    while True:
        elapsed = time.monotonic() - start_monotonic
        if elapsed > project_timeout:
            status = "timeout"
            break

        try:
            project = await client.get_project(project_id)
        except Exception as e:  # noqa: BLE001 - a flaky poll must not kill the run; just try again
            print(f"[warn] {task.idea.id} run{task.run_index}: poll failed ({e}), retrying")
            await asyncio.sleep(poll_interval)
            continue

        project_status = project.get("status")
        if project_status == "completed":
            status = "completed"
            break
        if project_status == "failed":
            status = "failed"
            break

        await asyncio.sleep(poll_interval)

    blocks = {
        name: project.get(BLOCK_JSON_KEYS[name])
        for name in BLOCK_NAMES
        if project.get(BLOCK_JSON_KEYS[name]) is not None
    }

    return RunRecord(
        idea_id=task.idea.id,
        run_index=task.run_index,
        project_id=project_id,
        started_at=started_at,
        finished_at=utcnow_iso(),
        expected_pattern=task.idea.expected_pattern,
        detail_level=task.idea.detail_level,
        market_type=task.idea.market_type,
        industry=task.idea.industry,
        status=status,
        duration_seconds=time.monotonic() - start_monotonic,
        blocks_completed=len(blocks),
        blocks=blocks,
        error=error,
    )


async def run_plan(
    tasks: list[RunTask],
    *,
    backend_base_url: str,
    backend_api_key: str | None,
    runs_path: Path,
    concurrency: int,
    poll_interval: float,
    project_timeout: float,
) -> list[RunRecord]:
    existing = load_existing_results(runs_path)
    pending = [t for t in tasks if t.key not in existing]
    skipped = len(tasks) - len(pending)
    if skipped:
        print(f"[resume] {skipped}/{len(tasks)} runs already recorded in {runs_path}, skipping them")

    if not pending:
        print("[resume] nothing left to run")
        return list(existing.values())

    client = BackendClient(backend_base_url, backend_api_key)
    semaphore = asyncio.Semaphore(concurrency)
    completed: list[RunRecord] = []
    lock = asyncio.Lock()

    async def worker(task: RunTask, index: int) -> None:
        async with semaphore:
            print(f"[start] ({index}/{len(pending)}) {task.idea.id} run{task.run_index}")
            record = await run_one(
                client, task, poll_interval=poll_interval, project_timeout=project_timeout
            )
            async with lock:
                append_result(runs_path, record)
                completed.append(record)
            print(
                f"[done]  ({index}/{len(pending)}) {task.idea.id} run{task.run_index}: "
                f"{record.status} in {record.duration_seconds:.0f}s, "
                f"{record.blocks_completed}/{len(BLOCK_NAMES)} blocks, project_id={record.project_id}"
            )

    try:
        await asyncio.gather(*(worker(t, i + 1) for i, t in enumerate(pending)))
    finally:
        await client.aclose()

    return list(existing.values()) + completed
