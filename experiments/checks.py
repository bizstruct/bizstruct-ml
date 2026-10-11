"""The row table and the checks on a finished project (shared by the smoke script and the experiment runner)."""

import json
from collections import Counter
from datetime import datetime
from typing import Any

from bizstruct_domain import (
    ArtifactRecord,
    ArtifactType,
    Brief,
    Canvas,
    Patterns,
    Swot,
    final_canvas,
    parse_artifact,
)

OPTIONAL_STAGES = ("business_case", "environment_scan")


def _seconds(row: dict[str, Any]) -> float | None:
    if not row.get("startedAt") or not row.get("finishedAt"):
        return None
    return (datetime.fromisoformat(row["finishedAt"]) - datetime.fromisoformat(row["startedAt"])).total_seconds()


def _violations(row: dict[str, Any]) -> str:
    counts = Counter(v["severity"] for v in ((row.get("consistency") or {}).get("violations") or []))
    return f"{counts['error']}e/{counts['warning']}w"


def rows_table(project: dict[str, Any]) -> str:
    header = ("stage", "idx", "status", "retries", "duration", "error", "violations")
    lines = [header]
    for row in project["rows"]:
        seconds = _seconds(row)
        lines.append(
            (
                row["stage"],
                str(row["instanceIndex"]),
                row["status"],
                str(row["retryCount"]),
                f"{seconds:.1f}s" if seconds is not None else "-",
                (row["error"] or {}).get("code", "-") if row["error"] else "-",
                _violations(row),
            )
        )
    widths = [max(len(line[i]) for line in lines) for i in range(len(header))]
    return "\n".join("  ".join(cell.ljust(widths[i]) for i, cell in enumerate(line)).rstrip() for line in lines)


# --------------------------------------------------------------------------- checks


def _artifacts(project: dict[str, Any]) -> list[tuple[dict[str, Any], dict[str, Any]]]:
    return [(row, artifact) for row in project["rows"] for artifact in row["artifacts"]]


def check_parse(project: dict[str, Any]) -> tuple[list[str], dict[str, Any]]:
    """Parses every artifact; returns the problems and the parsed models by artifact id."""
    problems: list[str] = []
    parsed: dict[str, Any] = {}
    for row, artifact in _artifacts(project):
        label = f"{row['stage']}[{row['instanceIndex']}] {artifact['type']} {artifact['id']}"
        try:
            parsed[artifact["id"]] = parse_artifact(
                ArtifactRecord(id=artifact["id"], type=ArtifactType(artifact["type"]), data=artifact["data"])
            )
        except Exception as error:  # a pydantic ValidationError, a ValueError or an unknown type
            problems.append(f"does not parse: {label}: {str(error).splitlines()[0][:200]}")
    return problems, parsed


def check_final_canvases(project: dict[str, Any], parsed: dict[str, Any]) -> tuple[list[str], list[str]]:
    """Derives the final canvas of every canvas row from its v1 and its cycle row's Swots and later canvases."""
    problems: list[str] = []
    lines: list[str] = []
    rows = project["rows"]
    for canvas_row in (r for r in rows if r["stage"] == "canvas"):
        cycles = [r for r in rows if r["stage"] == "swot_errc_cycle" and r["refs"].get("canvas") == [canvas_row["id"]]]
        label = f"canvas[{canvas_row['instanceIndex']}]"
        if len(cycles) != 1:
            problems.append(f"{label}: expected one swot_errc_cycle row, found {len(cycles)}")
            continue
        models = [parsed[a["id"]] for r in (canvas_row, cycles[0]) for a in r["artifacts"] if a["id"] in parsed]
        canvases = [m for m in models if isinstance(m, Canvas)]
        swots = [m for m in models if isinstance(m, Swot)]
        try:
            final = final_canvas(canvases, swots)
        except ValueError as error:
            problems.append(f"{label}: cannot derive the final canvas: {error}")
            continue
        lines.append(f"{label}: {len(canvases)} canvas versions, {len(swots)} swots, final version {final.version}")
    return problems, lines


def check_shape(project: dict[str, Any], parsed: dict[str, Any], expected_optional: list[str]) -> list[str]:
    problems: list[str] = []
    rows = project["rows"]
    counts = Counter(r["stage"] for r in rows)

    brief = next((a for r in rows if r["stage"] == "brief" for a in r["artifacts"] if a["id"] in parsed), None)
    segments = counts["empathy_map"]
    if brief is not None and isinstance(parsed[brief["id"]], Brief):
        candidates = len(parsed[brief["id"]].customer_segment_candidates)
        if segments != candidates:
            problems.append(f"empathy_map rows ({segments}) differ from the brief's segment candidates ({candidates})")

    patterns = next((parsed[a["id"]] for r in rows if r["stage"] == "patterns" for a in r["artifacts"] if isinstance(parsed.get(a["id"]), Patterns)), None)
    canvases = counts["canvas"]
    if patterns is not None and canvases != len(patterns.groups):
        problems.append(f"canvas rows ({canvases}) differ from the Patterns groups ({len(patterns.groups)})")

    expected = {
        "brief": 1,
        "patterns": 1,
        "empathy_map": segments,
        "customer_scenario": segments,
        "ideation": segments,
        "canvas": canvases,
        "swot_errc_cycle": canvases,
        "storytelling": canvases,
        "future_scenario": canvases,
        "pitch": canvases,
    }
    for stage in OPTIONAL_STAGES:
        expected[stage] = 1 if stage in expected_optional else 0
    expected["team_info"] = 0
    if segments < 1 or canvases < 1:
        problems.append(f"a project needs at least one empathy_map and one canvas row, found {segments} and {canvases}")
    for stage, want in expected.items():
        if counts[stage] != want:
            problems.append(f"{stage}: expected {want} rows, found {counts[stage]}")
    for stage in counts.keys() - expected.keys():
        problems.append(f"unexpected stage {stage}: {counts[stage]} rows")
    return problems


def check_duplicates(project: dict[str, Any]) -> list[str]:
    problems: list[str] = []
    rows = project["rows"]
    for row_id, n in Counter(r["id"] for r in rows).items():
        if n > 1:
            problems.append(f"row id {row_id} appears {n} times")
    keys = Counter((r["stage"], r["instanceIndex"], json.dumps(r["refs"], sort_keys=True)) for r in rows)
    for (stage, index, _), n in keys.items():
        if n > 1:
            problems.append(f"duplicated row: {stage}[{index}] with the same refs appears {n} times")
    for artifact_id, n in Counter(a["id"] for _, a in _artifacts(project)).items():
        if n > 1:
            problems.append(f"artifact id {artifact_id} appears {n} times")
    return problems


def run_checks(project: dict[str, Any], expected_optional: list[str]) -> tuple[list[str], list[str]]:
    """All checks on a finished project. Returns (problems, informational lines)."""
    problems: list[str] = []
    if project["status"] != "completed":
        problems.append(f"project status is {project['status']}, not completed")
    for row in project["rows"]:
        if row["status"] != "done":
            problems.append(f"row {row['stage']}[{row['instanceIndex']}] is {row['status']}, not done")
    parse_problems, parsed = check_parse(project)
    problems += parse_problems
    problems += check_shape(project, parsed, expected_optional)
    problems += check_duplicates(project)
    canvas_problems, lines = check_final_canvases(project, parsed)
    return problems + canvas_problems, lines
