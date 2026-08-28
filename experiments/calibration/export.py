"""calibration-export: turns a calibration set (5 projects, possibly with
some degraded via calibration/degrade.py) into 5 self-contained Markdown
files for a human judge to paste into a model's web chat — see the
calibration brief's part B for the exact required content and ordering.

No project identifier, model name, or degraded/clean marker appears in
the exported files themselves — the file_id <-> idea_id correspondence
(and which idea_id was degraded, on which criterion) lives in
<out_dir's sibling> keys/, not in export/ itself, so the export/
directory alone is safe to hand to a judge.
"""

from __future__ import annotations

import csv
import json
import random
import string
from dataclasses import dataclass
from pathlib import Path

from experiments.calibration.blocks_render import render_all_blocks_md
from experiments.calibration.rubric import CRITERION_IDS, RESPONSE_FORMAT_MD, render_rubric_md
from experiments.calibration.tokens import estimate_tokens

FILE_LETTERS = list(string.ascii_uppercase[:5])  # A..E


@dataclass
class ExportedFile:
    file_id: str  # "project-A" etc.
    idea_id: str
    project_id: str | None
    degraded: bool
    tokens_estimated: int
    criteria_order: list[str]


def _load_records(set_dir: Path) -> list[dict]:
    runs_path = set_dir / "runs.jsonl"
    records = []
    for line in runs_path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            records.append(json.loads(line))
    # calibration-set is exactly 5 ideas, run_index=0 each — sorted by
    # idea_id for a deterministic base order before the random file-letter
    # shuffle below.
    records = [r for r in records if r["run_index"] == 0]
    records.sort(key=lambda r: r["idea_id"])
    if len(records) != 5:
        raise ValueError(f"Expected exactly 5 run_index=0 records in {runs_path}, found {len(records)}")
    return records


def _resolve_blocks(set_dir: Path, idea_id: str, pristine_blocks: dict) -> tuple[dict, bool]:
    degraded_path = set_dir / "degraded" / f"{idea_id}.json"
    if degraded_path.exists():
        return json.loads(degraded_path.read_text(encoding="utf-8"))["blocks"], True
    return pristine_blocks, False


def build_calibration_export(
    set_dir: Path, out_dir: Path, keys_dir: Path, idea_texts: dict[str, str], seed: int | None = None,
) -> list[ExportedFile]:
    """`idea_texts` maps idea_id -> the original idea text from
    dataset.json — RunRecord doesn't carry the idea text itself (only
    idea_id and the derived labels), so the caller loads it from the
    dataset (see cli.py's calibration-export handler)."""
    rng = random.Random(seed)
    records = _load_records(set_dir)

    order = records[:]
    rng.shuffle(order)  # which idea_id becomes project-A / B / C / D / E

    out_dir.mkdir(parents=True, exist_ok=True)
    keys_dir.mkdir(parents=True, exist_ok=True)

    exported: list[ExportedFile] = []
    for letter, record in zip(FILE_LETTERS, order):
        file_id = f"project-{letter}"
        idea_id = record["idea_id"]
        blocks, degraded = _resolve_blocks(set_dir, idea_id, record["blocks"])

        criteria_order = CRITERION_IDS[:]
        rng.shuffle(criteria_order)

        md_parts = [
            render_rubric_md(criteria_order),
            RESPONSE_FORMAT_MD,
            "## Вихідна ідея",
            "",
            idea_texts.get(idea_id, ""),
            "",
            render_all_blocks_md(blocks),
        ]
        md = "\n".join(md_parts)
        tokens_estimated = estimate_tokens(md)

        (out_dir / f"{file_id}.md").write_text(md, encoding="utf-8")

        exported.append(ExportedFile(
            file_id=file_id,
            idea_id=idea_id,
            project_id=record.get("project_id"),
            degraded=degraded,
            tokens_estimated=tokens_estimated,
            criteria_order=criteria_order,
        ))

    _write_key_csv(keys_dir / "key.csv", exported)
    _write_token_counts_csv(keys_dir / "token_counts.csv", exported)
    _write_criteria_order_csv(keys_dir / "criteria_order.csv", exported)
    return exported


def _write_key_csv(path: Path, exported: list[ExportedFile]) -> None:
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["file_id", "idea_id", "project_id"])
        for e in exported:
            writer.writerow([e.file_id, e.idea_id, e.project_id or ""])


def _write_token_counts_csv(path: Path, exported: list[ExportedFile]) -> None:
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["file_id", "tokens_estimated"])
        for e in exported:
            writer.writerow([e.file_id, e.tokens_estimated])


def _write_criteria_order_csv(path: Path, exported: list[ExportedFile]) -> None:
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["file_id", "criteria_order"])
        for e in exported:
            writer.writerow([e.file_id, ";".join(e.criteria_order)])
