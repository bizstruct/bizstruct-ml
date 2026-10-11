"""Summaries of a finished (or interrupted) experiment from its results.jsonl: standard library only.

The latest line per (idea, repeat) counts. Per idea and overall: n, completion rate, median and IQR of wall-clock
and tokens, the distribution of cycle iterations and final version, violation counts per rule id and severity,
and the reasons runs failed."""

import csv
import json
import statistics
from collections import Counter
from pathlib import Path
from typing import Any

ALL = "ALL"
SUMMARY_COLUMNS = (
    "scope", "n", "completed", "completion_rate",
    "wall_median_s", "wall_q1_s", "wall_q3_s",
    "tokens_n", "tokens_median", "tokens_q1", "tokens_q3",
)


def load_latest(path: Path) -> list[dict[str, Any]]:
    latest: dict[tuple[str, int], dict[str, Any]] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        try:
            record = json.loads(line)
            latest[(record["idea_id"], int(record["repeat"]))] = record
        except (json.JSONDecodeError, KeyError, TypeError, ValueError):
            continue
    return list(latest.values())


def quartiles(values: list[float]) -> tuple[float, float, float] | None:
    """(q1, median, q3) with the inclusive method; None for no values."""
    if not values:
        return None
    if len(values) == 1:
        return values[0], values[0], values[0]
    q1, median, q3 = statistics.quantiles(values, n=4, method="inclusive")
    return q1, median, q3


def failure_reason(record: dict[str, Any]) -> str | None:
    """Why a run counts as a failure: its status and first error, or the first problem of a completed project's checks."""
    if record["status"] != "completed":
        error = (record.get("errors") or [""])[0]
        return f"{record['status']}: {error[:120]}".rstrip(": ")
    checks = record.get("checks") or {}
    if not checks.get("ok", True):
        return f"checks: {checks['problems'][0][:120]}"
    return None


def summarize(records: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """One block of numbers per idea id plus "ALL"."""
    groups: dict[str, list[dict[str, Any]]] = {ALL: records}
    for record in records:
        groups.setdefault(record["idea_id"], []).append(record)
    summary: dict[str, dict[str, Any]] = {}
    for scope, group in groups.items():
        completed = [r for r in group if r["status"] == "completed"]
        walls = [r["wall_clock_s"] for r in group if r.get("wall_clock_s") is not None]
        tokens = [r["tokens"]["total"] for r in group if r.get("tokens")]
        cycles = [c for r in group if r.get("shape") for c in r["shape"]["cycles"]]
        violations: Counter[tuple[str, str]] = Counter()
        for r in group:
            for row in r.get("rows", []):
                for v in row["violations"]:
                    violations[(v["rule_id"], v["severity"])] += v["count"]
        summary[scope] = {
            "n": len(group),
            "completed": len(completed),
            "completion_rate": len(completed) / len(group),
            "wall": quartiles(walls),
            "tokens": quartiles(tokens),
            "tokens_n": len(tokens),
            "iterations": Counter(c["iterations"] for c in cycles),
            "final_version": Counter(c["final_version"] for c in cycles if c["final_version"] is not None),
            "violations": violations,
            "failures": Counter(reason for r in group if (reason := failure_reason(r))),
        }
    return summary


def _fmt(quartile: tuple[float, float, float] | None, pick: int, digits: int = 1) -> str:
    return "-" if quartile is None else f"{quartile[pick]:,.{digits}f}"


def _dist(counter: Counter) -> str:
    return " ".join(f"{k}:{v}" for k, v in sorted(counter.items())) or "-"


def render(summary: dict[str, dict[str, Any]]) -> str:
    scopes = [s for s in summary if s != ALL] + [ALL]
    rows = [("scope", "n", "completed", "rate", "wall median [IQR] s", "tokens median [IQR]", "iterations", "final version")]
    for scope in scopes:
        s = summary[scope]
        rows.append((
            scope, str(s["n"]), str(s["completed"]), f"{s['completion_rate']:.0%}",
            f"{_fmt(s['wall'], 1)} [{_fmt(s['wall'], 0)}-{_fmt(s['wall'], 2)}]",
            f"{_fmt(s['tokens'], 1, 0)} [{_fmt(s['tokens'], 0, 0)}-{_fmt(s['tokens'], 2, 0)}] (n={s['tokens_n']})" if s["tokens"] else "- (no token data)",
            _dist(s["iterations"]), _dist(s["final_version"]),
        ))
    widths = [max(len(r[i]) for r in rows) for i in range(len(rows[0]))]
    lines = ["  ".join(cell.ljust(widths[i]) for i, cell in enumerate(r)).rstrip() for r in rows]
    overall = summary[ALL]
    lines.append("\nviolations per rule id (all runs):")
    lines += [f"  {n:>5}  {rule}  [{severity}]" for (rule, severity), n in overall["violations"].most_common()] or ["  none"]
    lines.append("\nfailure reasons (all runs):")
    lines += [f"  {n:>5}  {reason}" for reason, n in overall["failures"].most_common()] or ["  none"]
    return "\n".join(lines)


def write_csv(summary: dict[str, dict[str, Any]], out_dir: Path) -> list[Path]:
    """summary.csv, distributions.csv, violations.csv and failures.csv next to the results."""
    out_dir.mkdir(parents=True, exist_ok=True)
    paths = []

    def write(name: str, header: tuple[str, ...], rows: list[tuple]) -> None:
        path = out_dir / name
        with path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.writer(handle)
            writer.writerow(header)
            writer.writerows(rows)
        paths.append(path)

    def cells(q: tuple[float, float, float] | None, digits: int) -> tuple:
        return ("", "", "") if q is None else tuple(round(v, digits) for v in (q[1], q[0], q[2]))

    write("summary.csv", SUMMARY_COLUMNS, [
        (scope, s["n"], s["completed"], round(s["completion_rate"], 4), *cells(s["wall"], 2), s["tokens_n"], *cells(s["tokens"], 0))
        for scope, s in summary.items()
    ])
    write("distributions.csv", ("scope", "metric", "value", "count"), [
        (scope, metric, value, count)
        for scope, s in summary.items() for metric in ("iterations", "final_version") for value, count in sorted(s[metric].items())
    ])
    write("violations.csv", ("scope", "rule_id", "severity", "count"), [
        (scope, rule, severity, count) for scope, s in summary.items() for (rule, severity), count in sorted(s["violations"].items())
    ])
    write("failures.csv", ("scope", "reason", "count"), [
        (scope, reason, count) for scope, s in summary.items() for reason, count in s["failures"].most_common()
    ])
    return paths
