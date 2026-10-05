"""Context gathering from a snapshot closure."""
import pytest
from bizstruct_domain.schemas import (
    ArtifactRecord,
    ArtifactType,
    EmpathyMap,
    RuleInput,
    Stage,
    StageArity,
    StageRow,
    StageStatus,
    derive_artifact_id,
)

from bizstruct_ml.core.context import ContextError, expected_types_of, gather_context, gather_inputs, rows_by_id
from tests.support.fakes import brief_row, empathy_generated, empathy_row

ONE_EM = RuleInput(stage=Stage.EMPATHY_MAP, arity=StageArity.ONE)
MANY_EM = RuleInput(stage=Stage.EMPATHY_MAP, arity=StageArity.MANY)
ONE_BRIEF = RuleInput(stage=Stage.BRIEF, arity=StageArity.ONE)
ONE_TEAM_OPT = RuleInput(stage=Stage.TEAM_INFO, arity=StageArity.ONE, optional=True)
MANY_TEAM_OPT = RuleInput(stage=Stage.TEAM_INFO, arity=StageArity.MANY, optional=True)


def empathy_model(row_id: str, name: str = "Olena") -> EmpathyMap:
    return EmpathyMap.from_generated(
        empathy_generated(name), id=derive_artifact_id(row_id, ArtifactType.EMPATHY_MAP), project_id="p"
    )


def done_empathy_row(row_id: str, name: str = "Olena") -> StageRow:
    model = empathy_model(row_id, name)
    return StageRow(
        id=row_id,
        stage=Stage.EMPATHY_MAP,
        status=StageStatus.DONE,
        attempt_id="a",
        refs={Stage.BRIEF: ["row_brief"]},
        artifacts=[ArtifactRecord(id=model.id, type=ArtifactType.EMPATHY_MAP, data=model.model_dump(mode="json"))],
    )


def scenario_row(row_id: str, em_row_id: str) -> StageRow:
    return StageRow(id=row_id, stage=Stage.CUSTOMER_SCENARIO, status=StageStatus.RUNNING, attempt_id="a",
                    refs={Stage.EMPATHY_MAP: [em_row_id]})


def test_gather_context_labels_by_stage_and_parses_models():
    rows = rows_by_id([brief_row(), empathy_row()])
    ctx = gather_context(empathy_row(), rows)
    assert list(ctx) == [Stage.BRIEF]
    assert ctx[Stage.BRIEF][0].industry == "Food"


def test_gather_context_errors_on_a_missing_ref():
    with pytest.raises(ContextError, match="not in the snapshot"):
        gather_context(empathy_row(), rows_by_id([empathy_row()]))


def test_gather_context_errors_on_a_ref_of_the_wrong_stage():
    rows = rows_by_id([brief_row("row_brief"), empathy_row()])
    bad = empathy_row()
    bad.refs = {Stage.EMPATHY_MAP: ["row_brief"]}
    with pytest.raises(ContextError, match="is a brief row"):
        gather_context(bad, rows)


def test_one_input_is_found_via_the_direct_ref():
    em = done_empathy_row("row_em_0")
    fresh = scenario_row("row_cs_0", "row_em_0")
    rows = rows_by_id([brief_row(), em, fresh])
    (found,) = gather_inputs([ONE_EM], fresh_row=fresh, fresh_artifacts=[], rows=rows)
    assert found.id == empathy_model("row_em_0").id


def test_one_input_prefers_the_fresh_artifacts_over_stored_ones():
    stored = done_empathy_row("row_em_0", "Old")
    fresh_model = empathy_model("row_em_0", "New")
    fresh = stored.model_copy(update={"status": StageStatus.RUNNING})
    rows = rows_by_id([brief_row(), fresh])
    (found,) = gather_inputs([ONE_EM], fresh_row=fresh, fresh_artifacts=[fresh_model], rows=rows)
    assert found.persona_name == "New"


def test_one_input_is_ambiguous_when_two_direct_refs_match():
    fresh = scenario_row("row_cs_0", "row_em_0")
    fresh.refs = {Stage.EMPATHY_MAP: ["row_em_0", "row_em_1"]}
    rows = rows_by_id([done_empathy_row("row_em_0"), done_empathy_row("row_em_1"), fresh])
    with pytest.raises(ContextError, match="ambiguous"):
        gather_inputs([ONE_EM], fresh_row=fresh, fresh_artifacts=[], rows=rows)


def test_one_input_ignores_artifacts_that_are_not_directly_reachable():
    # empathy_map is in the closure but not a direct ref of the fresh row
    fresh = scenario_row("row_cs_0", "row_em_other")
    rows = rows_by_id([brief_row(), done_empathy_row("row_em_0"), fresh])
    with pytest.raises(ContextError, match="no empathy_map artifact"):
        gather_inputs([ONE_EM], fresh_row=fresh, fresh_artifacts=[], rows=rows)


def test_many_input_collects_every_done_artifact_in_the_closure():
    fresh = scenario_row("row_cs_0", "row_em_0")
    rows = rows_by_id([done_empathy_row("row_em_0"), done_empathy_row("row_em_1", "Taras"), fresh])
    (found,) = gather_inputs([MANY_EM], fresh_row=fresh, fresh_artifacts=[], rows=rows)
    assert sorted(a.persona_name for a in found) == ["Olena", "Taras"]


def test_many_input_skips_rows_that_are_not_done():
    fresh = scenario_row("row_cs_0", "row_em_0")
    running = done_empathy_row("row_em_1").model_copy(update={"status": StageStatus.RUNNING})
    rows = rows_by_id([done_empathy_row("row_em_0"), running, fresh])
    (found,) = gather_inputs([MANY_EM], fresh_row=fresh, fresh_artifacts=[], rows=rows)
    assert len(found) == 1


def test_absent_optional_inputs_are_none_and_empty_list():
    fresh = empathy_row()
    rows = rows_by_id([brief_row(), fresh])
    one, many = gather_inputs([ONE_TEAM_OPT, MANY_TEAM_OPT], fresh_row=fresh, fresh_artifacts=[], rows=rows)
    assert one is None and many == []


def test_absent_required_inputs_raise():
    fresh = empathy_row()
    rows = rows_by_id([fresh])
    with pytest.raises(ContextError):
        gather_inputs([MANY_EM], fresh_row=fresh, fresh_artifacts=[], rows=rows)


def test_expected_types_follow_the_rule_signature():
    from bizstruct_domain.schemas import CONSISTENCY_RULES, Errc, Patterns, CustomerScenario

    by_id = {r.id: r for r in CONSISTENCY_RULES}
    assert expected_types_of(by_id["multi_sided_requires_signal"]) == [(CustomerScenario,), (Patterns,)]
    errc_rule = by_id["errc_move_targets_correct_canvas_version"]
    assert expected_types_of(errc_rule)[1] == (Errc,)
