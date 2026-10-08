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


def test_many_input_falls_back_to_the_closure_when_the_direct_refs_do_not_name_the_stage():
    # a patterns-like row: refs name the scenarios only, so the empathy maps come from the closure
    scenarios = [scenario_row(f"row_cs_{k}", f"row_em_{k}") for k in range(2)]
    fresh = StageRow(id="row_patterns", stage=Stage.PATTERNS, status=StageStatus.RUNNING, attempt_id="a",
                     refs={Stage.CUSTOMER_SCENARIO: [r.id for r in scenarios]})
    ems = [done_empathy_row("row_em_0"), done_empathy_row("row_em_1", "Taras")]
    rows = rows_by_id([*ems, *scenarios, fresh])
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


# -- MANY scoped by the row's refs: the group is defined by the refs -------------------------------


def done_scenario_row(row_id: str, em_row_id: str) -> StageRow:
    from bizstruct_domain.schemas import CustomerScenario
    from tests.test_slice1_stages import SCENARIO

    em_id = derive_artifact_id(em_row_id, ArtifactType.EMPATHY_MAP)
    model = CustomerScenario.from_generated(SCENARIO, id=derive_artifact_id(row_id, ArtifactType.CUSTOMER_SCENARIO), empathy_map_id=em_id)
    return StageRow(id=row_id, stage=Stage.CUSTOMER_SCENARIO, status=StageStatus.DONE, attempt_id="a",
                    refs={Stage.EMPATHY_MAP: [em_row_id]},
                    artifacts=[ArtifactRecord(id=model.id, type=ArtifactType.CUSTOMER_SCENARIO, data=model.model_dump(mode="json"))])


MANY_CS = RuleInput(stage=Stage.CUSTOMER_SCENARIO, arity=StageArity.MANY)


def project(groups: list[list[int]]):
    """A project with sum(len(g)) segments, a patterns row over all of them and one canvas row per group.
    Returns (rows by id, canvas rows, patterns row). Like be builds them (ADR-0011)."""
    n = sum(len(g) for g in groups)
    ems = [done_empathy_row(f"row_em_{k}", f"Persona {k}") for k in range(n)]
    scs = [done_scenario_row(f"row_cs_{k}", f"row_em_{k}") for k in range(n)]
    patterns = StageRow(id="row_patterns", stage=Stage.PATTERNS, status=StageStatus.RUNNING, attempt_id="a",
                        refs={Stage.CUSTOMER_SCENARIO: [r.id for r in scs]})
    canvases = [
        StageRow(id=f"row_canvas_{i}", stage=Stage.CANVAS, instance_index=i, status=StageStatus.RUNNING, attempt_id="a",
                 refs={Stage.EMPATHY_MAP: [f"row_em_{k}" for k in g], Stage.CUSTOMER_SCENARIO: [f"row_cs_{k}" for k in g],
                       Stage.PATTERNS: ["row_patterns"]})
        for i, g in enumerate(groups)
    ]
    return rows_by_id([brief_row(), *ems, *scs, patterns, *canvases]), canvases, patterns


def personas(found) -> list[str]:
    return sorted(a.persona_name for a in found)


@pytest.mark.parametrize(
    "groups",
    [
        [[0]],                       # N = 1, unified
        [[0, 1, 2]],                 # one group of three, unified
        [[0, 1], [2]],               # split into 2
        [[0], [1], [2]],             # split into 3
    ],
)
def test_a_canvas_row_gets_only_its_groups_maps_and_scenarios(groups):
    rows, canvases, _ = project(groups)
    for canvas, group in zip(canvases, groups):
        found_em, found_cs = gather_inputs([MANY_EM, MANY_CS], fresh_row=canvas, fresh_artifacts=[], rows=rows)
        assert personas(found_em) == sorted(f"Persona {k}" for k in group)
        assert sorted(s.id for s in found_cs) == sorted(derive_artifact_id(f"row_cs_{k}", ArtifactType.CUSTOMER_SCENARIO) for k in group)


def test_a_split_projects_closure_really_holds_every_group_so_scoping_is_what_separates_them():
    from bizstruct_ml.core.context import gather_closure

    rows, canvases, _ = project([[0], [1], [2]])
    closure = gather_closure(canvases[1], rows)
    assert personas(closure[Stage.EMPATHY_MAP]) == ["Persona 0", "Persona 1", "Persona 2"]


@pytest.mark.parametrize("groups", [[[0]], [[0, 1, 2]], [[0, 1], [2]], [[0], [1], [2]]])
def test_the_patterns_row_gets_all_maps_from_the_closure_and_all_scenarios_directly(groups):
    rows, _, patterns = project(groups)
    n = sum(len(g) for g in groups)
    found_em, found_cs = gather_inputs([MANY_EM, MANY_CS], fresh_row=patterns, fresh_artifacts=[], rows=rows)
    assert personas(found_em) == sorted(f"Persona {k}" for k in range(n))
    assert len(found_cs) == n


def test_the_fresh_rows_own_artifacts_of_the_stage_are_included_next_to_the_referenced_ones():
    rows, canvases, _ = project([[0, 1]])
    own = empathy_model("row_canvas_0", "Own version")  # e.g. canvas versions 2..5 held by the cycle row
    (found,) = gather_inputs([MANY_EM], fresh_row=canvases[0], fresh_artifacts=[own], rows=rows)
    assert personas(found) == ["Own version", "Persona 0", "Persona 1"]


def test_the_fresh_rows_stored_artifacts_are_stale_and_ignored():
    rows, canvases, _ = project([[0]])
    stale = empathy_model("row_canvas_0", "Stale")
    canvases[0].artifacts = [ArtifactRecord(id=stale.id, type=ArtifactType.EMPATHY_MAP, data=stale.model_dump(mode="json"))]
    (found,) = gather_inputs([MANY_EM], fresh_row=canvases[0], fresh_artifacts=[], rows=rows)
    assert personas(found) == ["Persona 0"]


def test_a_directly_referenced_row_that_is_not_done_is_an_error():
    rows, canvases, _ = project([[0, 1]])
    rows["row_em_1"] = rows["row_em_1"].model_copy(update={"status": StageStatus.RUNNING})
    with pytest.raises(ContextError, match="row_em_1.*running, not done"):
        gather_inputs([MANY_EM], fresh_row=canvases[0], fresh_artifacts=[], rows=rows)


def test_a_directly_referenced_row_without_artifacts_is_an_error():
    rows, canvases, _ = project([[0, 1]])
    rows["row_em_1"] = rows["row_em_1"].model_copy(update={"artifacts": []})
    with pytest.raises(ContextError, match="row_em_1.*no artifacts"):
        gather_inputs([MANY_EM], fresh_row=canvases[0], fresh_artifacts=[], rows=rows)


def test_a_directly_referenced_row_missing_from_the_snapshot_is_an_error():
    rows, canvases, _ = project([[0, 1]])
    del rows["row_em_1"]
    with pytest.raises(ContextError, match="row_em_1.*not in the snapshot"):
        gather_inputs([MANY_EM], fresh_row=canvases[0], fresh_artifacts=[], rows=rows)


def test_on_regeneration_the_done_fresh_rows_stale_artifacts_do_not_count_on_the_closure_path():
    # the fresh row is DONE with an old empathy map (a regeneration); only the new one may be seen
    stale = done_empathy_row("row_em_0", "Stale")
    fresh = stale.model_copy(update={"refs": {Stage.BRIEF: ["row_brief"]}})
    rows = rows_by_id([brief_row(), fresh])
    (found,) = gather_inputs([MANY_EM], fresh_row=fresh, fresh_artifacts=[empathy_model("row_em_0", "New")], rows=rows)
    assert personas(found) == ["New"]
