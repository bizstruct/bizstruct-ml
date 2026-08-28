"""One-off calibration tool for validation.degenerate_text's thresholds —
reads (never writes) experiments/results/*/runs.jsonl and reports how many
fields the validator flags per model, per violation kind.

Not part of the worker or the experiment tooling proper; run manually
when tuning thresholds:

    python scripts/calibrate_degenerate_text.py

Historical note (part E): the runs this was originally calibrated against
(experiments/results/A_pipeline__*) predate the _uk/_en field removal —
every text field was a bilingual pair back then, and `language_mismatch`
was judged per-field from the `_uk`/`_en` suffix rather than from an
explicit project language. Those field names no longer exist on the
current schema, so re-running this against that historical data only
exercises disallowed_script/repeated_sequence/truncation (whichever
fields still share a name with the old bilingual ones) — language_mismatch
won't fire on it. Kept as-is for the record; a fresh calibration run
against new single-language data would need the project's actual
`language` per run (see runs.jsonl / run_meta.json) instead of the "en"
placeholder below.
"""

from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))
sys.path.insert(0, str(REPO_ROOT))

from bizstruct_ml.generators.registry import GENERATORS  # noqa: E402
from bizstruct_ml.validation.degenerate_text import validate_block_text  # noqa: E402

RESULTS_DIRS = [
    REPO_ROOT / "experiments" / "results" / "A_pipeline__gpt-5.6-sol",
    REPO_ROOT / "experiments" / "results" / "A_pipeline__gpt-5.6-terra",
    REPO_ROOT / "experiments" / "results" / "A_pipeline__gpt-5.4-mini",
    REPO_ROOT / "experiments" / "results" / "A_pipeline__gpt-5.4-nano",
]


def main() -> None:
    for results_dir in RESULTS_DIRS:
        runs_path = results_dir / "runs.jsonl"
        if not runs_path.exists():
            print(f"{results_dir.name}: no runs.jsonl, skipping")
            continue

        by_kind: Counter[str] = Counter()
        by_kind_retry: Counter[str] = Counter()
        examples: list[str] = []
        n_blocks = 0

        for line in runs_path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            record = json.loads(line)
            for block, data in record["blocks"].items():
                if block not in GENERATORS:
                    continue
                n_blocks += 1
                schema = GENERATORS[block].schema
                # "en" placeholder — see the historical note above; these
                # runs predate per-project language as an explicit value.
                violations = validate_block_text(schema, data, "en")
                for v in violations:
                    by_kind[v.kind] += 1
                    if v.retry_worthy:
                        by_kind_retry[v.kind] += 1
                    if len(examples) < 8:
                        examples.append(
                            f"  [{record['idea_id']}/{block}] {v.field_path}: {v.kind} — {v.detail}"
                        )

        total_retry_worthy = sum(by_kind_retry.values())
        print(f"\n=== {results_dir.name} ({n_blocks} blocks) ===")
        print(f"  retry-worthy violations: {total_retry_worthy}")
        for kind, count in by_kind.most_common():
            retry_note = f" ({by_kind_retry[kind]} retry-worthy)" if by_kind_retry[kind] != count else ""
            print(f"    {kind}: {count}{retry_note}")
        if examples:
            print("  examples:")
            for ex in examples:
                print(ex)


if __name__ == "__main__":
    main()
