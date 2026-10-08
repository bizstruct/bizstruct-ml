"""Rule inputs by artifact type (domain 0.16.0, ADR-0012): ONE / MANY / EACH / FINAL as the core gathers them."""
import json

import pytest
from bizstruct_domain.schemas import (
    Arity,
    ArtifactType,
    ConsistencyRule,
    ConsistencyViolation,
    JudgeCheck,
    RuleInput,
    Stage,
    StageRow,
    StageStatus,
)

from bizstruct_ml.core.consistency import run_deterministic, run_judge
from bizstruct_ml.core.context import ContextError, gather_inputs, rows_by_id
from bizstruct_ml.judge.base import ConsistencyJudge
from bizstruct_ml.judge.fake import FakeJudgeModel
from tests.support.cycle_builders import finished_cycle, swot_scoring, canvas_model
from tests.support.projects import NO_FINDINGS

A = ArtifactType
CANVAS_FINAL = RuleInput(artifact=A.CANVAS, arity=Arity.FINAL)
SWOT_FINAL = RuleInput(artifact=A.SWOT, arity=Arity.FINAL)
CANVAS_MANY = RuleInput(artifact=A.CANVAS, arity=Arity.MANY)
ERRC_EACH = RuleInput(artifact=A.ERRC, arity=Arity.EACH)
SWOT_EACH = RuleInput(artifact=A.SWOT, arity=Arity.EACH)


def downstream_row(cycle_row_id: str = "row_cycle_0") -> StageRow:
    """A storytelling-like row: it refs only the cycle row (ADR-0011 Q2)."""
    return StageRow(id="row_story_0", stage=Stage.STORYTELLING, status=StageStatus.RUNNING, attempt_id="a", refs={Stage.SWOT_ERRC_CYCLE: [cycle_row_id]})


# -- FINAL ------------------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("totals", "final"),
    [
        ((60, 70), 1),                    # no improvement: v1 is final, and v1 lives in the canvas row, not in the cycle row
        ((90, 80, 70, 60, 50), 5),        # steady improvement to v5
        ((90, 80, 70, 75), 3),            # stop at k = 3
        ((90, 80, 80), 2),                # equal scores
        ((50,), 1),
    ],
)
def test_final_canvas_and_swot_follow_the_scores(totals, final):
    canvas_row, cycle_row, canvases, swots, _ = finished_cycle(totals)
    fresh = downstream_row()
    rows = rows_by_id([canvas_row, cycle_row, fresh])
    ((canvas, swot),) = gather_inputs([CANVAS_FINAL, SWOT_FINAL], fresh_row=fresh, fresh_artifacts=[], rows=rows)
    assert canvas.version == final and swot.canvas_version == final
    assert canvas.id == canvases[final - 1].id and swot.canvas_id == canvas.id


def test_final_reads_the_cycle_rows_own_fresh_artifacts_when_the_cycle_row_is_the_fresh_row():
    canvas_row, cycle_row, canvases, swots, errcs = finished_cycle((90, 80, 85))
    fresh = cycle_row.model_copy(update={"status": StageStatus.RUNNING, "artifacts": []})
    rows = rows_by_id([canvas_row, fresh])
    fresh_artifacts = [*swots, *errcs, *canvases[1:]]
    ((canvas,),) = gather_inputs([CANVAS_FINAL], fresh_row=fresh, fresh_artifacts=fresh_artifacts, rows=rows)
    assert canvas.version == 2


def test_final_with_a_swot_gap_is_a_context_error():
    canvas_row, cycle_row, canvases, swots, errcs = finished_cycle((90, 80, 70))
    cycle_row.artifacts = [a for a in cycle_row.artifacts if a.id != swots[1].id]
    fresh = downstream_row()
    with pytest.raises(ContextError, match="1..n"):
        gather_inputs([SWOT_FINAL], fresh_row=fresh, fresh_artifacts=[], rows=rows_by_id([canvas_row, cycle_row, fresh]))


# -- ONE: ambiguity and type-based addressing ----------------------------------------------------------------


def test_one_with_several_candidates_is_an_ambiguity_error():
    canvas_row, cycle_row, *_ = finished_cycle((90, 80, 70))
    fresh = downstream_row()
    rows = rows_by_id([canvas_row, cycle_row, fresh])
    with pytest.raises(ContextError, match="ambiguous input: 3 swot instances"):
        gather_inputs([RuleInput(artifact=A.SWOT, arity=Arity.ONE)], fresh_row=fresh, fresh_artifacts=[], rows=rows)


def test_one_addresses_the_artifact_type_not_the_stage():
    # the cycle row holds Swots, Errcs and canvases: asking for ONE errc finds the single Errc, ONE swot the single Swot
    canvas_row, cycle_row, *_ = finished_cycle((90, 80))
    fresh = downstream_row()
    rows = rows_by_id([canvas_row, cycle_row, fresh])
    ((errc,),) = gather_inputs([RuleInput(artifact=A.ERRC, arity=Arity.ONE)], fresh_row=fresh, fresh_artifacts=[], rows=rows)
    assert errc.from_version == 1
    with pytest.raises(ContextError, match="ambiguous input: 2 swot"):
        gather_inputs([RuleInput(artifact=A.SWOT, arity=Arity.ONE)], fresh_row=fresh, fresh_artifacts=[], rows=rows)


def test_one_does_not_consult_the_closure():
    # v1 lives in the canvas row, which is in the closure of a downstream row but not among its direct refs:
    # ONE sees only the cycle row's canvas (v2), exactly as before domain 0.16.0
    canvas_row, cycle_row, *_ = finished_cycle((90, 80))
    fresh = downstream_row()
    rows = rows_by_id([canvas_row, cycle_row, fresh])
    ((canvas,),) = gather_inputs([RuleInput(artifact=A.CANVAS, arity=Arity.ONE)], fresh_row=fresh, fresh_artifacts=[], rows=rows)
    assert canvas.version == 2


# -- EACH --------------------------------------------------------------------------------------------------


def cycle_in_progress(totals):
    canvas_row, cycle_row, canvases, swots, errcs = finished_cycle(totals)
    fresh = cycle_row.model_copy(update={"status": StageStatus.RUNNING, "artifacts": []})
    return fresh, rows_by_id([canvas_row, fresh]), [*swots, *errcs, *canvases[1:]], canvases, swots, errcs


@pytest.mark.parametrize("n_errc", [1, 2, 3, 4])
def test_each_gives_one_argument_tuple_per_errc_and_the_canvas_versions_once(n_errc):
    fresh, rows, artifacts, canvases, swots, errcs = cycle_in_progress(tuple(range(100, 100 - 5 * (n_errc + 1), -5)))
    bound = gather_inputs([CANVAS_MANY, ERRC_EACH], fresh_row=fresh, fresh_artifacts=artifacts, rows=rows)
    assert [e.from_version for _, e in bound] == list(range(1, n_errc + 1))
    assert all(sorted(c.version for c in versions) == list(range(1, n_errc + 2)) for versions, _ in bound)  # v1 from the canvas row, v2.. own


@pytest.mark.parametrize("n_swot", [1, 3, 5])
def test_each_runs_once_per_swot_up_to_five(n_swot):
    fresh, rows, artifacts, *_ = cycle_in_progress(tuple(range(100, 100 - 5 * n_swot, -5)))
    bound = gather_inputs([SWOT_EACH], fresh_row=fresh, fresh_artifacts=artifacts, rows=rows)
    assert [s.canvas_version for (s,) in bound] == list(range(1, n_swot + 1))


def test_run_deterministic_calls_the_rule_once_per_instance_and_concatenates():
    fresh, rows, artifacts, canvases, swots, errcs = cycle_in_progress((90, 80, 70, 60))
    seen: list[str] = []

    def check(versions, errc):
        seen.append(errc.id)
        return [ConsistencyViolation(rule_id="spy", severity="warning", message=errc.id, artifact_ids=[errc.id])]

    rule = ConsistencyRule("spy", (CANVAS_MANY, ERRC_EACH), check)
    violations = run_deterministic(fresh, artifacts, rows, [rule])
    assert seen == [e.id for e in errcs] and [v.message for v in violations] == seen


async def test_run_judge_calls_the_judge_once_per_instance_of_an_each_input():
    fresh, rows, artifacts, *_ = cycle_in_progress((90, 80, 70))
    check = JudgeCheck(id="per_errc", inputs=(CANVAS_MANY, ERRC_EACH), instruction="Check.")
    model = FakeJudgeModel([NO_FINDINGS])
    reports, unavailable = await run_judge(fresh, artifacts, rows, ConsistencyJudge(model, retry_wait=0), [check], artifact_ids=["x"])
    assert len(reports) == 2 and unavailable == [] and len(model.calls) == 2
    assert [json.loads(c["user"])["errc"]["from_version"] for c in model.calls] == [1, 2]


def test_the_judge_payload_is_labelled_by_artifact_type():
    from bizstruct_ml.judge.base import ConsistencyJudge as J

    canvas_row, cycle_row, canvases, swots, _ = finished_cycle((90, 80))
    _, user = J.build_prompts(JudgeCheck(id="x", inputs=(SWOT_FINAL,), instruction="i"), [swots[1]])
    assert list(json.loads(user)) == ["swot"]


# -- the domain's own checks, through the gatherer ----------------------------------------------------------------


def test_every_registered_check_is_gatherable_on_a_finished_cycle_for_the_rows_that_come_after_it():
    """pitch_risk_analysis_grounded_in_swot reads a FINAL swot: with a pitch-like row after the cycle it is gatherable."""
    from bizstruct_domain.schemas import JUDGE_CHECKS

    canvas_row, cycle_row, _, swots, _ = finished_cycle((90, 80, 85))
    fresh = StageRow(id="row_pitch_0", stage=Stage.PITCH, status=StageStatus.RUNNING, attempt_id="a", refs={Stage.SWOT_ERRC_CYCLE: [cycle_row.id]})
    check = next(c for c in JUDGE_CHECKS if c.id == "pitch_risk_analysis_grounded_in_swot")
    swot_input = (check.inputs[0],)
    ((swot,),) = gather_inputs(swot_input, fresh_row=fresh, fresh_artifacts=[], rows=rows_by_id([canvas_row, cycle_row, fresh]))
    assert swot.canvas_version == 2  # the best version, not the last one


# -- ONE falls back to the closure (ADR-0001, same holder rule as the other kinds) ------------------------------------


def cycle_row_of_a_finished_project(shape=None):
    """A fake backend run through canvas, plus a RUNNING cycle row that refs only its canvas row."""
    import asyncio

    from tests.support.fake_backend import FakeBackend
    from tests.support.projects import SPLIT_IN_TWO, scripted_llm, stage_runner

    backend = FakeBackend(through=Stage.CANVAS)
    asyncio.run(backend.run_to_completion(stage_runner(scripted_llm(shape or SPLIT_IN_TWO))))
    canvas_row = backend.rows_of(Stage.CANVAS)[0]
    cycle = StageRow(id="row_cycle_0", stage=Stage.SWOT_ERRC_CYCLE, status=StageStatus.RUNNING, attempt_id="a", refs={Stage.CANVAS: [canvas_row.id]})
    backend.rows[cycle.id] = cycle
    return backend, cycle


PATTERNS_ONE = RuleInput(artifact=A.PATTERNS, arity=Arity.ONE)


def test_patterns_on_a_cycle_row_binds_through_the_closure():
    backend, cycle = cycle_row_of_a_finished_project()
    rows = rows_by_id(backend.closure_of(cycle.id))
    ((patterns,),) = gather_inputs([PATTERNS_ONE], fresh_row=cycle, fresh_artifacts=[], rows=rows)
    assert len(patterns.groups) == 2


def test_the_cycle_rows_consistency_rules_run_instead_of_crashing():
    from bizstruct_domain.schemas import CONSISTENCY_RULES

    backend, cycle = cycle_row_of_a_finished_project()
    rows = rows_by_id(backend.closure_of(cycle.id))
    rule = next(r for r in CONSISTENCY_RULES if r.id == "canvas_group_id_is_known")
    canvas = swotless_canvas_of(backend)
    bad = canvas.model_copy(update={"id": "v2", "version": 2, "group_id": "dangling"})
    violations = run_deterministic(cycle, [bad], rows, [rule])
    assert [v.artifact_ids[0] for v in violations] == ["v2"]


def swotless_canvas_of(backend):
    from bizstruct_domain.schemas import parse_artifact

    return parse_artifact(backend.rows_of(Stage.CANVAS)[0].artifacts[0])


def test_several_patterns_candidates_in_the_closure_are_an_error():
    backend, cycle = cycle_row_of_a_finished_project()
    (patterns_row,) = backend.rows_of(Stage.PATTERNS)
    twin = patterns_row.model_copy(update={"id": "row_patterns_twin"})
    canvas_row = backend.rows_of(Stage.CANVAS)[0]
    canvas_row.refs = {**canvas_row.refs, Stage.PATTERNS: [patterns_row.id]}  # the twin is only in the snapshot
    rows = {**rows_by_id(backend.closure_of(cycle.id)), twin.id: twin}
    with pytest.raises(ContextError, match="ambiguous input: 2 patterns instances"):
        gather_inputs([PATTERNS_ONE], fresh_row=cycle, fresh_artifacts=[], rows=rows)


@pytest.mark.parametrize("damage", ["unfinished", "no_artifacts", "missing"])
def test_a_named_holder_row_that_is_not_usable_keeps_raising(damage):
    backend, cycle = cycle_row_of_a_finished_project()
    (patterns_row,) = backend.rows_of(Stage.PATTERNS)
    cycle.refs = {**cycle.refs, Stage.PATTERNS: [patterns_row.id]}  # now the row names a holder stage of patterns
    rows = rows_by_id(backend.closure_of(cycle.id))
    if damage == "unfinished":
        rows[patterns_row.id] = patterns_row.model_copy(update={"status": StageStatus.RUNNING, "artifacts": []})  # a row still being generated holds nothing yet
    elif damage == "no_artifacts":
        rows[patterns_row.id] = patterns_row.model_copy(update={"artifacts": []})
    else:
        del rows[patterns_row.id]
    with pytest.raises(ContextError, match=patterns_row.id):
        gather_inputs([PATTERNS_ONE], fresh_row=cycle, fresh_artifacts=[], rows=rows)


def test_a_usable_named_holder_row_is_read_directly_not_from_the_closure():
    backend, cycle = cycle_row_of_a_finished_project()
    (patterns_row,) = backend.rows_of(Stage.PATTERNS)
    cycle.refs = {**cycle.refs, Stage.PATTERNS: [patterns_row.id]}
    rows = rows_by_id(backend.closure_of(cycle.id))
    ((patterns,),) = gather_inputs([PATTERNS_ONE], fresh_row=cycle, fresh_artifacts=[], rows=rows)
    assert len(patterns.groups) == 2


def test_a_one_input_found_directly_never_consults_the_closure():
    # patterns found directly is not duplicated by the closure's copy (that would be an ambiguity error)
    test_a_usable_named_holder_row_is_read_directly_not_from_the_closure()
