"""calibration-input / calibration-report: takes the human judge's raw
scores (file_id, round, criterion, score, rationale — three independent
rounds per file, each in its own fresh chat, see the calibration brief's
part D) and turns them into calibration_report.md.

Report content is numbers and tables only — no interpretation of what a
result "means" (see the brief: "Не інтерпретуй результати — сформуй
таблиці й наведи числа").
"""

from __future__ import annotations

import csv
import statistics
from dataclasses import dataclass
from pathlib import Path

from experiments.calibration.rubric import CRITERION_IDS

SCORE_INPUT_FIELDS = ["file_id", "round", "criterion", "score", "rationale"]
ROUNDS = (1, 2, 3)


# ── template ─────────────────────────────────────────────────────────────


def write_score_template(out_path: Path, file_ids: list[str]) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(SCORE_INPUT_FIELDS)
        for file_id in file_ids:
            for round_n in ROUNDS:
                for criterion in CRITERION_IDS:
                    writer.writerow([file_id, round_n, criterion, "", ""])


# ── validate + store ────────────────────────────────────────────────────


@dataclass
class ValidationResult:
    ok: bool
    errors: list[str]
    rows: list[dict[str, str]]


def validate_scores(in_path: Path, file_ids: list[str]) -> ValidationResult:
    errors: list[str] = []
    with in_path.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        missing_cols = set(SCORE_INPUT_FIELDS) - set(reader.fieldnames or [])
        if missing_cols:
            return ValidationResult(ok=False, errors=[f"missing column(s): {sorted(missing_cols)}"], rows=[])
        rows = list(reader)

    seen: dict[tuple[str, int, str], dict[str, str]] = {}
    for i, row in enumerate(rows, start=2):  # +1 header, +1 1-index
        file_id = row["file_id"].strip()
        criterion = row["criterion"].strip()
        round_raw = row["round"].strip()
        score_raw = row["score"].strip()

        if file_id not in file_ids:
            errors.append(f"row {i}: unknown file_id {file_id!r}")
            continue
        if criterion not in CRITERION_IDS:
            errors.append(f"row {i}: unknown criterion {criterion!r}")
            continue
        try:
            round_n = int(round_raw)
        except ValueError:
            errors.append(f"row {i}: round {round_raw!r} is not an integer")
            continue
        if round_n not in ROUNDS:
            errors.append(f"row {i}: round {round_n} not in {ROUNDS}")
            continue
        try:
            score = int(score_raw)
        except ValueError:
            errors.append(f"row {i}: score {score_raw!r} is not an integer (file_id={file_id}, round={round_n}, criterion={criterion})")
            continue
        if not (1 <= score <= 5):
            errors.append(f"row {i}: score {score} out of range 1-5 (file_id={file_id}, round={round_n}, criterion={criterion})")
            continue

        key = (file_id, round_n, criterion)
        if key in seen:
            errors.append(f"row {i}: duplicate entry for file_id={file_id}, round={round_n}, criterion={criterion}")
            continue
        seen[key] = {"file_id": file_id, "round": str(round_n), "criterion": criterion, "score": str(score), "rationale": row["rationale"]}

    # Completeness: every (file_id, round) must have all 5 criteria; every
    # file_id must have all 3 rounds present.
    for file_id in file_ids:
        for round_n in ROUNDS:
            present = {c for (f, r, c) in seen if f == file_id and r == round_n}
            missing = set(CRITERION_IDS) - present
            if missing:
                errors.append(f"{file_id} round {round_n}: missing criteria {sorted(missing)}")
        rounds_present = {r for (f, r, c) in seen if f == file_id}
        missing_rounds = set(ROUNDS) - rounds_present
        if missing_rounds:
            errors.append(f"{file_id}: missing round(s) {sorted(missing_rounds)}")

    return ValidationResult(ok=not errors, errors=errors, rows=list(seen.values()))


def store_scores(set_dir: Path, rows: list[dict[str, str]]) -> Path:
    out_path = set_dir / "scores" / "scores.csv"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=SCORE_INPUT_FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    return out_path


# ── report ───────────────────────────────────────────────────────────────


def _load_scores_csv(path: Path) -> list[dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def _load_key_csv(path: Path) -> dict[str, str]:
    """file_id -> idea_id"""
    with path.open(newline="", encoding="utf-8") as f:
        return {row["file_id"]: row["idea_id"] for row in csv.DictReader(f)}


def _load_token_counts_csv(path: Path) -> dict[str, int]:
    with path.open(newline="", encoding="utf-8") as f:
        return {row["file_id"]: int(row["tokens_estimated"]) for row in csv.DictReader(f)}


def _load_manifest_csv(path: Path) -> dict[str, dict[str, str]]:
    """idea_id -> {criterion, degraded_at, note}"""
    if not path.exists():
        return {}
    with path.open(newline="", encoding="utf-8") as f:
        return {row["idea_id"]: row for row in csv.DictReader(f)}


def _pearson(xs: list[float], ys: list[float]) -> float | None:
    n = len(xs)
    if n < 2:
        return None
    mean_x, mean_y = sum(xs) / n, sum(ys) / n
    cov = sum((x - mean_x) * (y - mean_y) for x, y in zip(xs, ys))
    var_x = sum((x - mean_x) ** 2 for x in xs)
    var_y = sum((y - mean_y) ** 2 for y in ys)
    if var_x == 0 or var_y == 0:
        return None
    return cov / (var_x * var_y) ** 0.5


def build_calibration_report(set_dir: Path, keys_dir: Path, out_path: Path) -> str:
    scores_path = set_dir / "scores" / "scores.csv"
    rows = _load_scores_csv(scores_path)
    key = _load_key_csv(keys_dir / "key.csv")
    token_counts = _load_token_counts_csv(keys_dir / "token_counts.csv")
    manifest = _load_manifest_csv(set_dir / "degraded" / "manifest.csv")

    file_ids = sorted(key.keys())

    # scores_by[file_id][criterion] = [score_round1, score_round2, score_round3]
    scores_by: dict[str, dict[str, list[int]]] = {f: {c: [] for c in CRITERION_IDS} for f in file_ids}
    for row in rows:
        scores_by[row["file_id"]][row["criterion"]].append(int(row["score"]))

    lines: list[str] = ["# Звіт калібрування рубрики", ""]

    # ── 1. score table: median + spread ──
    lines.append("## 1. Таблиця балів (медіана з 3 оцінювань, розкид = максимум − мінімум)")
    lines.append("")
    header = "| file_id | " + " | ".join(f"{c} (мед / розкид)" for c in CRITERION_IDS) + " |"
    lines.append(header)
    lines.append("|" + "---|" * (len(CRITERION_IDS) + 1))
    medians: dict[str, dict[str, float]] = {f: {} for f in file_ids}
    spreads: dict[str, dict[str, int]] = {f: {} for f in file_ids}
    for file_id in file_ids:
        cells = []
        for c in CRITERION_IDS:
            vals = scores_by[file_id][c]
            med = statistics.median(vals)
            spread = max(vals) - min(vals)
            medians[file_id][c] = med
            spreads[file_id][c] = spread
            cells.append(f"{med} / {spread}")
        lines.append(f"| {file_id} | " + " | ".join(cells) + " |")
    lines.append("")

    # ── 2. degraded check ──
    lines.append("## 2. Перевірка на дефектах")
    lines.append("")
    degraded_file_by_criterion: dict[str, str] = {}
    for file_id, idea_id in key.items():
        m = manifest.get(idea_id)
        if m:
            degraded_file_by_criterion[m["criterion"]] = file_id

    for criterion, degraded_file in degraded_file_by_criterion.items():
        others = [f for f in file_ids if f != degraded_file]
        other_medians = [medians[f][criterion] for f in others]
        degraded_median = medians[degraded_file][criterion]
        other_mean = sum(other_medians) / len(other_medians) if other_medians else float("nan")
        diff = degraded_median - other_mean
        lines.append(f"**{criterion}**, погіршений файл: `{degraded_file}`")
        lines.append("")
        lines.append(f"- Медіана на погіршеному: {degraded_median}")
        lines.append(f"- Медіани на решті: " + ", ".join(f"{f}={medians[f][criterion]}" for f in others))
        lines.append(f"- Середнє на решті: {other_mean:.2f}")
        lines.append(f"- Різниця (погіршений − середнє решти): {diff:+.2f}")
        lines.append("")
    if not degraded_file_by_criterion:
        lines.append("_Жодного запису в degraded/manifest.csv не знайдено._")
        lines.append("")

    # ── 3. repeat spread per criterion ──
    lines.append("## 3. Розкид між повторами (по кожному критерію, серед усіх 5 файлів)")
    lines.append("")
    lines.append("| criterion | max spread (по всіх файлах) | файли з розкидом ≥ 2 |")
    lines.append("|---|---|---|")
    for c in CRITERION_IDS:
        all_spreads = {f: spreads[f][c] for f in file_ids}
        max_spread = max(all_spreads.values())
        flagged = [f for f, s in all_spreads.items() if s >= 2]
        lines.append(f"| {c} | {max_spread} | {', '.join(flagged) if flagged else '—'} |")
    lines.append("")

    # ── 4. correlation with token length ──
    lines.append("## 4. Кореляція медіанного бала з довжиною матеріалу (Пірсон r)")
    lines.append("")
    lines.append("| criterion | r |")
    lines.append("|---|---|")
    lengths = [token_counts[f] for f in file_ids]
    for c in CRITERION_IDS:
        meds = [medians[f][c] for f in file_ids]
        r = _pearson(lengths, meds)
        lines.append(f"| {c} | {r:.3f} |" if r is not None else f"| {c} | н/д |")
    lines.append("")
    lines.append("Довжина файлів (оцінено в токенах): " + ", ".join(f"{f}={token_counts[f]}" for f in file_ids))
    lines.append("")

    # ── 5. score distribution ──
    lines.append("## 5. Розподіл балів")
    lines.append("")
    lines.append("### Загальний розподіл (усі критерії, усі раунди, усі файли)")
    lines.append("")
    all_scores = [int(r["score"]) for r in rows]
    lines.append("| бал | кількість |")
    lines.append("|---|---|")
    for v in range(1, 6):
        lines.append(f"| {v} | {all_scores.count(v)} |")
    lines.append("")

    lines.append("### Розподіл по кожному критерію")
    lines.append("")
    lines.append("| criterion | 1 | 2 | 3 | 4 | 5 |")
    lines.append("|---|---|---|---|---|---|")
    for c in CRITERION_IDS:
        vals = [int(r["score"]) for r in rows if r["criterion"] == c]
        counts = [vals.count(v) for v in range(1, 6)]
        lines.append(f"| {c} | " + " | ".join(str(n) for n in counts) + " |")
    lines.append("")

    report = "\n".join(lines)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(report, encoding="utf-8")
    return report
