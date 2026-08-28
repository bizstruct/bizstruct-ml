"""Builds quality_sample.md (part B5): for a handful of shared ideas, lays
the generated blocks from each model's results directory side by side for
a human to read. Deliberately does not score or judge anything — that's
for the reader, per the brief ("не оцінюй якість сам").
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from experiments.common import BLOCK_NAMES, load_existing_results


def _model_label(results_dir: Path) -> str:
    return results_dir.name


def build_quality_sample_md(
    results_dirs: list[Path], idea_ids: list[str], run_index: int = 0
) -> str:
    per_dir_records = {
        d: {r.idea_id: r for r in load_existing_results(d / "runs.jsonl").values() if r.run_index == run_index}
        for d in results_dirs
    }

    lines = ["# Quality sample — side-by-side model comparison", ""]
    lines.append(
        "Raw generated content only, no scoring. Read `expected_pattern` in dataset.json "
        "alongside this to judge fit, not just fluency."
    )

    for idea_id in idea_ids:
        lines.append("")
        lines.append(f"## {idea_id}")

        any_record = next(
            (recs[idea_id] for recs in per_dir_records.values() if idea_id in recs), None
        )
        if any_record is not None:
            lines.append("")
            lines.append(f"> {any_record.expected_pattern} / {any_record.detail_level} / "
                         f"{any_record.market_type} / {any_record.industry}")

        for block in BLOCK_NAMES:
            lines.append("")
            lines.append(f"### {idea_id} — {block}")
            for results_dir in results_dirs:
                label = _model_label(results_dir)
                record = per_dir_records.get(results_dir, {}).get(idea_id)
                lines.append("")
                lines.append(f"**{label}**")
                lines.append("")
                if record is None:
                    lines.append("_(no run recorded for this idea in this results dir)_")
                    continue
                content = record.blocks.get(block)
                if content is None:
                    lines.append(f"_(block not generated — run status: {record.status})_")
                    continue
                lines.append("```json")
                lines.append(json.dumps(content, ensure_ascii=False, indent=2))
                lines.append("```")

    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description="Build quality_sample.md across model results dirs")
    parser.add_argument("--results-dir", action="append", required=True, dest="results_dirs",
                         help="Repeat for each model's results directory")
    parser.add_argument("--idea-id", action="append", required=True, dest="idea_ids",
                         help="Repeat for each idea to include (2-3 recommended)")
    parser.add_argument("--run-index", type=int, default=0)
    parser.add_argument("--out", type=Path, default=Path(__file__).parent / "quality_sample.md")
    args = parser.parse_args()

    md = build_quality_sample_md(
        [Path(d) for d in args.results_dirs], args.idea_ids, run_index=args.run_index
    )
    args.out.write_text(md, encoding="utf-8")
    print(f"[quality_sample] wrote {args.out}")


if __name__ == "__main__":
    main()
