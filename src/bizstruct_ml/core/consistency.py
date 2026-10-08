"""Consistency after generation: deterministic rules, judge checks, one report.

ml runs both kinds (ADR-0010 D6). A check applies to a fresh row when it reads
the row's stage and is checkable given the stages DONE in the closure. The
fresh row is always the one blamed; nothing here looks at higher stages.
"""

from collections.abc import Mapping, Sequence

from bizstruct_domain.schemas import (
    CONSISTENCY_RULES,
    JUDGE_CHECKS,
    ConsistencyReport,
    ConsistencyRule,
    ConsistencyViolation,
    JudgeCheck,
    Stage,
    StageRow,
    StageStatus,
)
from pydantic import BaseModel

from bizstruct_ml.core.context import gather_inputs
from bizstruct_ml.judge.base import ConsistencyJudge, JudgeUnavailable
from bizstruct_ml.observability import tracing


def completed_stages(fresh_row: StageRow, rows: Mapping[str, StageRow]) -> set[Stage]:
    """Stages DONE in the closure, plus the fresh row's own stage."""
    done = {r.stage for r in rows.values() if r.status == StageStatus.DONE and r.id != fresh_row.id}
    return done | {fresh_row.stage}


def applicable_rules(
    fresh_row: StageRow, rows: Mapping[str, StageRow], rules: Sequence[ConsistencyRule] = CONSISTENCY_RULES
) -> list[ConsistencyRule]:
    completed = completed_stages(fresh_row, rows)
    return [r for r in rules if fresh_row.stage in r.applies_to and r.is_checkable(completed)]


def applicable_checks(
    fresh_row: StageRow, rows: Mapping[str, StageRow], checks: Sequence[JudgeCheck] = JUDGE_CHECKS
) -> list[JudgeCheck]:
    completed = completed_stages(fresh_row, rows)
    return [c for c in checks if fresh_row.stage in c.applies_to and c.is_checkable(completed)]


def run_deterministic(
    fresh_row: StageRow,
    fresh_artifacts: Sequence[BaseModel],
    rows: Mapping[str, StageRow],
    rules: Sequence[ConsistencyRule] = CONSISTENCY_RULES,
) -> list[ConsistencyViolation]:
    """Violations of every deterministic rule that applies to the fresh row."""
    violations: list[ConsistencyViolation] = []
    for rule in applicable_rules(fresh_row, rows, rules):
        for args in gather_inputs(rule.inputs, fresh_row=fresh_row, fresh_artifacts=fresh_artifacts, rows=rows):
            violations.extend(rule.check(*args))
    return violations


async def run_judge(
    fresh_row: StageRow,
    fresh_artifacts: Sequence[BaseModel],
    rows: Mapping[str, StageRow],
    judge: ConsistencyJudge,
    checks: Sequence[JudgeCheck] = JUDGE_CHECKS,
    *,
    artifact_ids: Sequence[str],
) -> tuple[list[ConsistencyReport], list[ConsistencyViolation]]:
    """Run every applicable judge check.

    Returns the judge's reports and, for each check whose judge was
    unavailable, a warning violation `judge_unavailable:<check_id>` citing
    `artifact_ids` (the fresh artifacts' record ids): the stage still succeeds,
    the gap is visible in the report.
    """
    reports: list[ConsistencyReport] = []
    unavailable: list[ConsistencyViolation] = []
    for check in applicable_checks(fresh_row, rows, checks):
        bound = gather_inputs(check.inputs, fresh_row=fresh_row, fresh_artifacts=fresh_artifacts, rows=rows)
        for inputs in bound:  # several only for an EACH input: one judge call per instance
            with tracing.span(f"judge:{check.id}"):
                try:
                    reports.append(await judge.evaluate(check, inputs))
                except JudgeUnavailable as e:
                    unavailable.append(
                        ConsistencyViolation(
                            rule_id=f"judge_unavailable:{check.id}",
                            severity="warning",
                            message=f"Judge check could not run: {e}",
                            artifact_ids=list(artifact_ids),
                        )
                    )
    return reports, unavailable


def deterministic_score(violations: Sequence[ConsistencyViolation]) -> int:
    """5 if there are no violations, else 5 minus the number of errors, within 1..5."""
    if not violations:
        return 5
    errors = sum(1 for v in violations if v.severity == "error")
    return max(1, min(5, 5 - errors))


def build_report(
    deterministic: Sequence[ConsistencyViolation],
    judge_reports: Sequence[ConsistencyReport] = (),
    extra: Sequence[ConsistencyViolation] = (),
) -> ConsistencyReport:
    """The final report. Score: the deterministic score, lowered to the lowest
    judge score if there is one. Violations: deterministic, then judge, then `extra`."""
    score = min([deterministic_score(deterministic), *(r.score for r in judge_reports)])
    violations = [*deterministic, *(v for r in judge_reports for v in r.violations), *extra]
    return ConsistencyReport(score=score, violations=violations)
