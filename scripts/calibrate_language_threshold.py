"""Calibration for the language-mismatch threshold change (follow-up brief,
part A): compares violation counts from the *old* language check (flat 0.55
ratio, no neutral-token exclusion) against the *new* one (neutral-token
exclusion for embedded brand names/acronyms/units, plus a looser 0.30
threshold for short fields) — per series, so the effect on real vs false
positives is visible side by side.

Read (never writes) two kinds of results directories:

  - experiments/results/language_comparison__gpt-5.6-terra__{uk,en}/ — the
    part F mini-experiment, real recorded language per run (RunRecord.language),
    the only data where language_mismatch is meaningful post-part-E.
  - experiments/results/A_pipeline__gpt-5.4-{nano,mini}/ and
    A_pipeline__gpt-5.6-{sol,terra}/ — the older 4-model comparison, predates
    per-project language (every run used "en" as a placeholder — see
    calibrate_degenerate_text.py's historical note). Used here only as a
    *sensitivity* check: nano's real degeneration (disallowed_script,
    repeated_sequence — script/character-level, unaffected by the language
    threshold change) must still be caught identically before and after.

Run manually:

    uv run python scripts/calibrate_language_threshold.py
"""

from __future__ import annotations

import json
import re
import sys
from collections import Counter
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))
sys.path.insert(0, str(REPO_ROOT))

from bizstruct_ml.generators.registry import GENERATORS  # noqa: E402
from bizstruct_ml.validation import degenerate_text as dt  # noqa: E402

LANGUAGE_COMPARISON_DIRS = {
    "uk": REPO_ROOT / "experiments" / "results" / "language_comparison__gpt-5.6-terra__uk",
    "en": REPO_ROOT / "experiments" / "results" / "language_comparison__gpt-5.6-terra__en",
}
MODEL_COMPARISON_DIRS = [
    REPO_ROOT / "experiments" / "results" / "A_pipeline__gpt-5.4-nano",
    REPO_ROOT / "experiments" / "results" / "A_pipeline__gpt-5.4-mini",
    REPO_ROOT / "experiments" / "results" / "A_pipeline__gpt-5.6-sol",
    REPO_ROOT / "experiments" / "results" / "A_pipeline__gpt-5.6-terra",
]


def _old_check_language(field_path: str, text: str, expected_language: str) -> dt.TextViolation | None:
    """Pre-fix logic: flat 0.55 threshold, no neutral-token exclusion, no
    short-field tier — reimplemented inline (not imported) so this stays a
    faithful "before" snapshot even as the module itself changes further."""
    name = dt._leaf_name(field_path)
    if name in dt._LANGUAGE_CHECK_EXEMPT_FIELDS:
        return None
    if expected_language not in ("uk", "en"):
        return None
    letters = [c for c in text if c.isalpha()]
    if len(letters) < dt._MIN_LETTERS_FOR_LANGUAGE_CHECK:
        return None
    cyrillic = sum(1 for c in letters if "Ѐ" <= c <= "ӿ")
    latin = sum(1 for c in letters if "a" <= c.lower() <= "z")
    ratio = (cyrillic if expected_language == "uk" else latin) / len(letters)
    threshold = 0.55
    if ratio < threshold:
        return dt.TextViolation(
            field_path=field_path, kind="language_mismatch",
            detail=f"expected mostly {expected_language} script, got {ratio:.0%} (threshold {threshold:.0%})",
            retry_worthy=True,
        )
    return None


def _old_validate_language_only(schema, data: dict, expected_language: str) -> list[dt.TextViolation]:
    """Walks the same field structure as validate_block_text, but only runs
    the old language check (the other three checks — disallowed_script,
    repeated_sequence, truncation — are untouched by this fix, so they're
    read straight from the current module for the 'after' pass and not
    duplicated here)."""
    out: list[dt.TextViolation] = []

    def walk_model(model_cls, d, path):
        for name, field_info in model_cls.model_fields.items():
            if name not in d:
                continue
            child_path = f"{path}.{name}" if path else name
            walk_field(field_info.annotation, d[name], child_path)

    def walk_field(annotation, value, path):
        if value is None:
            return
        annotation = dt._unwrap_optional(annotation)
        if annotation is str:
            if isinstance(value, str):
                v = _old_check_language(path, value, expected_language)
                if v is not None:
                    out.append(v)
            return
        origin = dt.get_origin(annotation)
        if origin in (list, tuple) and isinstance(value, (list, tuple)):
            args = dt.get_args(annotation)
            item_type = args[0] if args else None
            for i, item in enumerate(value):
                walk_field(item_type, item, f"{path}[{i}]")
            return
        import inspect as _inspect
        from pydantic import BaseModel as _BaseModel
        if _inspect.isclass(annotation) and issubclass(annotation, _BaseModel) and isinstance(value, dict):
            walk_model(annotation, value, path)

    walk_model(schema, data, "")
    return out


def _load_runs(results_dir: Path) -> list[dict]:
    runs_path = results_dir / "runs.jsonl"
    if not runs_path.exists():
        return []
    return [json.loads(line) for line in runs_path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _report_language_comparison() -> None:
    print("=" * 78)
    print("language_comparison__gpt-5.6-terra — real per-run language, part F data")
    print("=" * 78)
    for label, results_dir in LANGUAGE_COMPARISON_DIRS.items():
        records = _load_runs(results_dir)
        if not records:
            print(f"\n{label}: no runs.jsonl at {results_dir}, skipping")
            continue

        old_count = 0
        new_count = 0
        old_examples: list[str] = []
        new_examples: list[str] = []
        n_blocks = 0

        for record in records:
            language = record.get("language", "en")
            for block, data in record["blocks"].items():
                if block not in GENERATORS:
                    continue
                n_blocks += 1
                schema = GENERATORS[block].schema

                old_v = _old_validate_language_only(schema, data, language)
                old_count += len(old_v)
                for v in old_v:
                    if len(old_examples) < 6:
                        old_examples.append(f"  [{record['idea_id']}/{block}] {v.field_path}: {v.detail}")

                new_v = [v for v in dt.validate_block_text(schema, data, language) if v.kind == "language_mismatch"]
                new_count += len(new_v)
                for v in new_v:
                    if len(new_examples) < 6:
                        new_examples.append(f"  [{record['idea_id']}/{block}] {v.field_path}: {v.detail}")

        print(f"\n--- {label} series ({n_blocks} blocks) ---")
        print(f"  language_mismatch — before: {old_count}, after: {new_count}")
        if old_examples:
            print("  before, examples:")
            for ex in old_examples:
                print(ex)
        if new_examples:
            print("  after, examples:")
            for ex in new_examples:
                print(ex)


def _report_model_comparison() -> None:
    print()
    print("=" * 78)
    print("A_pipeline__* — 4-model comparison, sensitivity check (nano must still")
    print("catch real degeneration; language="+'"en"'+" placeholder, see module docstring)")
    print("=" * 78)
    for results_dir in MODEL_COMPARISON_DIRS:
        records = _load_runs(results_dir)
        if not records:
            print(f"\n{results_dir.name}: no runs.jsonl, skipping")
            continue

        by_kind_old: Counter[str] = Counter()
        by_kind_new: Counter[str] = Counter()
        n_blocks = 0

        for record in records:
            for block, data in record["blocks"].items():
                if block not in GENERATORS:
                    continue
                n_blocks += 1
                schema = GENERATORS[block].schema

                by_kind_old["language_mismatch"] += len(_old_validate_language_only(schema, data, "en"))
                for v in dt.validate_block_text(schema, data, "en"):
                    by_kind_new[v.kind] += 1

        print(f"\n--- {results_dir.name} ({n_blocks} blocks) ---")
        print(f"  language_mismatch — before: {by_kind_old['language_mismatch']}, "
              f"after: {by_kind_new['language_mismatch']}")
        other_kinds = sorted(k for k in by_kind_new if k != "language_mismatch")
        for k in other_kinds:
            print(f"  {k} (unaffected by this fix): {by_kind_new[k]}")


if __name__ == "__main__":
    _report_language_comparison()
    _report_model_comparison()
