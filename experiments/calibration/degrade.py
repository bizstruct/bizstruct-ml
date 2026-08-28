"""calibration-degrade: export one calibration-set project's blocks to a
human-editable JSON file, and import it back with a structural check —
the actual content edit (making it worse in a specific, plausible way) is
done by a person in an editor, not by this tool (see the calibration
brief: "Погіршення виконує людина, не ти").

Import writes the edited blocks to <set_dir>/degraded/<idea_id>.json (an
overlay — the pristine runs.jsonl from calibration-set is never
overwritten, so the calibration set stays the "versioned artifact" the
brief asks for) plus an entry in <set_dir>/degraded/manifest.csv (idea_id,
criterion, degraded_at, note) — the "окремий файл, який не потрапляє в
матеріали для оцінювача": it lives under degraded/, a sibling of export/,
never copied into export/.
"""

from __future__ import annotations

import csv
import json
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "src"))

from bizstruct_ml.generators.registry import GENERATORS  # noqa: E402

MANIFEST_FIELDS = ["idea_id", "criterion", "degraded_at", "note"]


def _load_pristine_record(set_dir: Path, idea_id: str) -> dict[str, Any]:
    runs_path = set_dir / "runs.jsonl"
    for line in runs_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        record = json.loads(line)
        if record["idea_id"] == idea_id and record["run_index"] == 0:
            return record
    raise ValueError(f"idea_id={idea_id!r} not found in {runs_path}")


def _degraded_path(set_dir: Path, idea_id: str) -> Path:
    return set_dir / "degraded" / f"{idea_id}.json"


def export_for_editing(set_dir: Path, idea_id: str, out_path: Path) -> None:
    """Writes <out_path> for a human to edit — resumes from an existing
    degraded/<idea_id>.json if one exists (so re-running export after an
    earlier edit continues from that state instead of resetting to
    pristine), otherwise starts from the pristine generated blocks."""
    degraded_path = _degraded_path(set_dir, idea_id)
    if degraded_path.exists():
        blocks = json.loads(degraded_path.read_text(encoding="utf-8"))["blocks"]
        source = f"degraded/{idea_id}.json (resuming a previous edit)"
    else:
        record = _load_pristine_record(set_dir, idea_id)
        blocks = record["blocks"]
        source = "pristine calibration-set output"

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        json.dumps({"idea_id": idea_id, "_source": source, "blocks": blocks}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


@dataclass
class StructuralCheckResult:
    ok: bool
    errors: list[str] = field(default_factory=list)


def _list_length_map(data: Any, path: str = "") -> dict[str, int]:
    """Recursively finds every list in `data` and records its length,
    keyed by JSON-path-ish string — used to compare "shape" between the
    pristine and edited versions of a block without hand-coding a check
    per block (canvas sections, empathy items, timeline steps, pitch
    slides, what_if moves, hypotheses — all just lists at some path)."""
    out: dict[str, int] = {}
    if isinstance(data, dict):
        for k, v in data.items():
            out.update(_list_length_map(v, f"{path}.{k}" if path else k))
    elif isinstance(data, list):
        out[path] = len(data)
        for i, item in enumerate(data):
            out.update(_list_length_map(item, f"{path}[{i}]"))
    return out


def check_structure(pristine_blocks: dict[str, Any], edited_blocks: dict[str, Any]) -> StructuralCheckResult:
    errors: list[str] = []

    missing = set(pristine_blocks) - set(edited_blocks)
    extra = set(edited_blocks) - set(pristine_blocks)
    if missing:
        errors.append(f"missing block(s): {sorted(missing)}")
    if extra:
        errors.append(f"unexpected extra block(s): {sorted(extra)}")

    for block in sorted(set(pristine_blocks) & set(edited_blocks)):
        schema = GENERATORS[block].schema
        try:
            schema.model_validate(edited_blocks[block])
        except Exception as e:  # noqa: BLE001 — surfaced verbatim to the caller
            errors.append(f"{block}: schema validation failed: {e}")

        pristine_lengths = _list_length_map(pristine_blocks[block])
        edited_lengths = _list_length_map(edited_blocks[block])
        for list_path, n in pristine_lengths.items():
            edited_n = edited_lengths.get(list_path)
            if edited_n is None:
                errors.append(f"{block}: list at {list_path!r} is missing in the edited version")
            elif edited_n != n:
                errors.append(f"{block}: list at {list_path!r} has {edited_n} items, pristine had {n}")

    return StructuralCheckResult(ok=not errors, errors=errors)


def import_edited(
    set_dir: Path, idea_id: str, in_path: Path, criterion: str, note: str = "",
) -> StructuralCheckResult:
    """Validates the edited file against the pristine project's structure
    and, if it passes, writes it to degraded/<idea_id>.json and records
    the manifest entry. Writes nothing on failure."""
    record = _load_pristine_record(set_dir, idea_id)
    edited = json.loads(in_path.read_text(encoding="utf-8"))
    edited_blocks = edited["blocks"]

    result = check_structure(record["blocks"], edited_blocks)
    if not result.ok:
        return result

    degraded_dir = set_dir / "degraded"
    degraded_dir.mkdir(parents=True, exist_ok=True)
    degraded_path = _degraded_path(set_dir, idea_id)
    degraded_path.write_text(
        json.dumps({"idea_id": idea_id, "blocks": edited_blocks}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    manifest_path = degraded_dir / "manifest.csv"
    existing_rows: list[dict[str, str]] = []
    if manifest_path.exists():
        with manifest_path.open(newline="", encoding="utf-8") as f:
            existing_rows = [row for row in csv.DictReader(f) if row["idea_id"] != idea_id]

    existing_rows.append({
        "idea_id": idea_id,
        "criterion": criterion,
        "degraded_at": datetime.now(timezone.utc).isoformat(),
        "note": note,
    })
    with manifest_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=MANIFEST_FIELDS)
        writer.writeheader()
        writer.writerows(existing_rows)

    return result
