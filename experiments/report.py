"""Builds summary.md from runs.jsonl + metrics.csv + run_meta.json, the
shared cost calculation used by both `report` and the pilot's cost
projection, and the cross-run `compare` table (part A4)."""

from __future__ import annotations

import csv
import json
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

from experiments.common import RunRecord, load_existing_results


@dataclass
class TokenTotals:
    input_tokens: int = 0
    output_tokens: int = 0
    rows: int = 0
    total_retries: int = 0
    rows_with_retries: int = 0
    latencies_ms: list[int] = None  # type: ignore[assignment]

    def __post_init__(self) -> None:
        if self.latencies_ms is None:
            self.latencies_ms = []

    @property
    def avg_latency_ms(self) -> float:
        return sum(self.latencies_ms) / len(self.latencies_ms) if self.latencies_ms else 0.0

    @property
    def avg_retries_per_block(self) -> float:
        return self.total_retries / self.rows if self.rows else 0.0


def load_metrics_totals(csv_path: Path) -> TokenTotals:
    totals = TokenTotals()
    if not csv_path.exists():
        return totals
    with csv_path.open("r", encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            totals.rows += 1
            if row["input_tokens"]:
                totals.input_tokens += int(row["input_tokens"])
            if row["output_tokens"]:
                totals.output_tokens += int(row["output_tokens"])
            if row["latency_ms"]:
                totals.latencies_ms.append(int(row["latency_ms"]))
            retries = int(row["retries"]) if row["retries"] else 0
            totals.total_retries += retries
            if retries > 0:
                totals.rows_with_retries += 1
    return totals


def estimate_cost(
    input_tokens: int, output_tokens: int, input_price_per_1k: float, output_price_per_1k: float
) -> float:
    return (input_tokens / 1000) * input_price_per_1k + (output_tokens / 1000) * output_price_per_1k


def _distribution(records: list[RunRecord], field: str) -> Counter:
    return Counter(getattr(r, field) for r in records)


def load_run_meta(out_dir: Path) -> dict | None:
    path = out_dir / "run_meta.json"
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def _run_meta_md(meta: dict) -> list[str]:
    lines = ["## Run conditions", ""]
    lines.append(f"- run_id: `{meta.get('run_id')}`")
    lines.append(f"- configuration: **{meta.get('configuration')}**")
    lines.append(f"- deployment: **{meta.get('deployment')}** (model_version: {meta.get('model_version')})")
    lines.append(f"- endpoint: {meta.get('endpoint')}")
    lines.append(f"- guardrails: {meta.get('guardrails')}")
    lines.append(f"- domain_version: {meta.get('domain_version')}")
    lines.append(f"- dataset: {meta.get('dataset_path')} (sha256 {meta.get('dataset_sha256', '')[:12]}…, "
                 f"{meta.get('dataset_size')} bytes)")
    git_commits = meta.get("git_commits", {})
    git_dirty = meta.get("git_dirty", {})
    for repo, sha in git_commits.items():
        dirty = git_dirty.get(repo)
        dirty_str = " (dirty)" if dirty else ("" if dirty is False else " (unknown)")
        lines.append(f"- {repo}: `{sha}`{dirty_str}")
    lines.append(f"- concurrency: {meta.get('concurrency')}, project_timeout: {meta.get('project_timeout')}s, "
                 f"poll_interval: {meta.get('poll_interval')}s")
    lines.append(f"- worker_replicas: {meta.get('worker_replicas')}")
    lines.append(f"- mode: {meta.get('mode')}, started_at: {meta.get('started_at')}, "
                 f"finished_at: {meta.get('finished_at')}")
    warnings = meta.get("meta_warnings") or []
    if warnings:
        lines.append("")
        lines.append("**meta_warnings** (fields that couldn't be determined, and why):")
        for w in warnings:
            lines.append(f"- {w}")
    lines.append("")
    return lines


def build_summary_md(
    records: list[RunRecord],
    totals: TokenTotals,
    *,
    input_price_per_1k: float | None,
    output_price_per_1k: float | None,
    run_meta: dict | None = None,
) -> str:
    by_status = Counter(r.status for r in records)
    durations = [r.duration_seconds for r in records if r.duration_seconds is not None]
    avg_duration = sum(durations) / len(durations) if durations else 0.0

    lines = ["# Baseline experiment — summary", ""]
    if run_meta is not None:
        lines.extend(_run_meta_md(run_meta))
    else:
        lines.append("_(no run_meta.json found in this results directory — conditions unknown)_")
        lines.append("")

    lines.append(f"Total runs recorded: **{len(records)}**")
    lines.append("")
    lines.append("## Outcomes")
    lines.append("")
    lines.append("| status | count |")
    lines.append("|---|---|")
    for status in ("completed", "failed", "timeout"):
        lines.append(f"| {status} | {by_status.get(status, 0)} |")
    lines.append("")
    lines.append(f"Average duration: **{avg_duration:.0f}s** ({avg_duration / 60:.1f} min)")
    lines.append("")

    lines.append("## Tokens & retries (from metrics.csv / Langfuse)")
    lines.append("")
    lines.append(f"- Block rows exported: {totals.rows}")
    lines.append(f"- Input tokens: {totals.input_tokens:,}")
    lines.append(f"- Output tokens: {totals.output_tokens:,}")
    lines.append(f"- Total generation retries: {totals.total_retries} "
                 f"({totals.rows_with_retries}/{totals.rows} blocks needed at least one)")
    lines.append(f"- Average retries per block: {totals.avg_retries_per_block:.2f}")
    lines.append(f"- Average LLM call latency: {totals.avg_latency_ms:.0f}ms")
    if input_price_per_1k is not None and output_price_per_1k is not None:
        cost = estimate_cost(totals.input_tokens, totals.output_tokens, input_price_per_1k, output_price_per_1k)
        lines.append(
            f"- Estimated cost: **${cost:,.2f}** "
            f"(@ ${input_price_per_1k}/1k input, ${output_price_per_1k}/1k output)"
        )
    else:
        lines.append("- Estimated cost: n/a (no --input-price-per-1k/--output-price-per-1k given)")
    lines.append("")

    lines.append("## Dataset label distribution (all recorded runs)")
    for field in ("expected_pattern", "detail_level", "market_type", "industry"):
        lines.append("")
        lines.append(f"### {field}")
        lines.append("")
        lines.append("| value | count |")
        lines.append("|---|---|")
        for value, count in sorted(_distribution(records, field).items()):
            lines.append(f"| {value} | {count} |")

    return "\n".join(lines) + "\n"


def generate_report(
    runs_path: Path,
    metrics_path: Path,
    out_path: Path,
    *,
    input_price_per_1k: float | None,
    output_price_per_1k: float | None,
) -> None:
    records = list(load_existing_results(runs_path).values())
    totals = load_metrics_totals(metrics_path)
    run_meta = load_run_meta(runs_path.parent)
    md = build_summary_md(
        records, totals, input_price_per_1k=input_price_per_1k, output_price_per_1k=output_price_per_1k,
        run_meta=run_meta,
    )
    out_path.write_text(md, encoding="utf-8")
    print(f"[report] wrote {out_path}")


def build_compare_md(
    results_dirs: list[Path],
    *,
    input_price_per_1k: float | None,
    output_price_per_1k: float | None,
) -> str:
    lines = ["# Comparison across runs", ""]
    if input_price_per_1k is None or output_price_per_1k is None:
        lines.append("_(no --input-price-per-1k/--output-price-per-1k given — cost column omitted)_")
    lines.append("")
    header = [
        "results_dir", "configuration", "deployment", "model_version",
        "completed", "failed", "timeout", "avg_duration_s",
        "input_tokens", "output_tokens", "total_retries", "avg_retries_per_block",
        "avg_latency_ms",
    ]
    if input_price_per_1k is not None and output_price_per_1k is not None:
        header.append("cost_usd")
    lines.append("| " + " | ".join(header) + " |")
    lines.append("|" + "---|" * len(header))

    for results_dir in results_dirs:
        records = list(load_existing_results(results_dir / "runs.jsonl").values())
        totals = load_metrics_totals(results_dir / "metrics.csv")
        meta = load_run_meta(results_dir)
        by_status = Counter(r.status for r in records)
        durations = [r.duration_seconds for r in records if r.duration_seconds is not None]
        avg_duration = sum(durations) / len(durations) if durations else 0.0

        row = [
            results_dir.name,
            (meta or {}).get("configuration", "?"),
            (meta or {}).get("deployment", "?"),
            str((meta or {}).get("model_version", "?")),
            str(by_status.get("completed", 0)),
            str(by_status.get("failed", 0)),
            str(by_status.get("timeout", 0)),
            f"{avg_duration:.0f}",
            f"{totals.input_tokens:,}",
            f"{totals.output_tokens:,}",
            str(totals.total_retries),
            f"{totals.avg_retries_per_block:.2f}",
            f"{totals.avg_latency_ms:.0f}",
        ]
        if input_price_per_1k is not None and output_price_per_1k is not None:
            cost = estimate_cost(totals.input_tokens, totals.output_tokens, input_price_per_1k, output_price_per_1k)
            row.append(f"{cost:,.2f}")
        lines.append("| " + " | ".join(row) + " |")

    return "\n".join(lines) + "\n"


def generate_compare(
    results_dirs: list[Path],
    out_path: Path,
    *,
    input_price_per_1k: float | None,
    output_price_per_1k: float | None,
) -> None:
    md = build_compare_md(
        results_dirs, input_price_per_1k=input_price_per_1k, output_price_per_1k=output_price_per_1k
    )
    out_path.write_text(md, encoding="utf-8")
    print(f"[compare] wrote {out_path}")
