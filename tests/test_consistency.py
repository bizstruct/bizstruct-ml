"""Consistency: applicability, the score rule, report building."""
import pytest
from bizstruct_domain.schemas import (
    ConsistencyReport,
    ConsistencyRule,
    ConsistencyViolation,
    JudgeCheck,
    RuleInput,
    Stage,
    StageArity,
)

from bizstruct_ml.core.consistency import (
    applicable_checks,
    applicable_rules,
    build_report,
    deterministic_score,
    run_deterministic,
)
from bizstruct_ml.core.context import rows_by_id
from tests.support.fakes import brief_row, empathy_row


def violation(severity: str, rule_id: str = "r") -> ConsistencyViolation:
    return ConsistencyViolation(rule_id=rule_id, severity=severity, message=f"{rule_id} {severity}", artifact_ids=["a"])


@pytest.mark.parametrize(
    ("severities", "score"),
    [
        ([], 5),
        (["warning"], 5),
        (["warning", "warning", "warning"], 5),
        (["error"], 4),
        (["error", "warning"], 4),
        (["error", "error"], 3),
        (["error"] * 4, 1),
        (["error"] * 9, 1),  # clamped at 1, never below
    ],
)
def test_deterministic_score_rule(severities, score):
    assert deterministic_score([violation(s) for s in severities]) == score


def test_report_score_is_the_minimum_of_judge_and_deterministic():
    det = [violation("error")]  # deterministic score 4
    low = ConsistencyReport(score=2, violations=[violation("warning", "j")])
    high = ConsistencyReport(score=5)
    assert build_report(det, [high]).score == 4
    assert build_report(det, [low, high]).score == 2
    assert build_report([], [high]).score == 5
    assert build_report([], []).score == 5


def test_report_keeps_deterministic_then_judge_then_extra_violations_in_order():
    det = [violation("error", "det")]
    judge = ConsistencyReport(score=3, violations=[violation("warning", "judge")])
    extra = [violation("warning", "judge_unavailable:x")]
    report = build_report(det, [judge], extra)
    assert [v.rule_id for v in report.violations] == ["det", "judge", "judge_unavailable:x"]


def test_rules_apply_only_when_they_read_the_fresh_stage_and_are_checkable():
    fresh = empathy_row()
    rows = rows_by_id([brief_row(), fresh])
    reads_empathy = ConsistencyRule("a", (RuleInput(stage=Stage.EMPATHY_MAP, arity=StageArity.ONE),), lambda e: [])
    reads_brief_only = ConsistencyRule("b", (RuleInput(stage=Stage.BRIEF, arity=StageArity.ONE),), lambda b: [])
    needs_scenario = ConsistencyRule(
        "c",
        (RuleInput(stage=Stage.EMPATHY_MAP, arity=StageArity.ONE), RuleInput(stage=Stage.CUSTOMER_SCENARIO, arity=StageArity.ONE)),
        lambda e, s: [],
    )
    ids = [r.id for r in applicable_rules(fresh, rows, [reads_empathy, reads_brief_only, needs_scenario])]
    assert ids == ["a"]  # b is about upstream only; c's scenario is not done


def test_judge_checks_use_the_same_applicability():
    fresh = empathy_row()
    rows = rows_by_id([brief_row(), fresh])
    check = JudgeCheck(id="j", inputs=(RuleInput(stage=Stage.EMPATHY_MAP, arity=StageArity.ONE),), instruction="x")
    other = JudgeCheck(id="k", inputs=(RuleInput(stage=Stage.BRIEF, arity=StageArity.ONE),), instruction="x")
    assert [c.id for c in applicable_checks(fresh, rows, [check, other])] == ["j"]


def test_run_deterministic_passes_the_gathered_artifacts_to_the_rule():
    fresh = empathy_row()
    rows = rows_by_id([brief_row(), fresh])
    seen = []
    rule = ConsistencyRule(
        "r", (RuleInput(stage=Stage.EMPATHY_MAP, arity=StageArity.ONE),), lambda e: seen.append(e) or [violation("error")]
    )
    from tests.support.fakes import empathy_generated
    from bizstruct_domain.schemas import EmpathyMap

    model = EmpathyMap.from_generated(empathy_generated(), id="e1", project_id="p")
    result = run_deterministic(fresh, [model], rows, [rule])
    assert seen == [model]
    assert [v.severity for v in result] == ["error"]
