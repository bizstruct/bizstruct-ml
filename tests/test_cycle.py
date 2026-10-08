"""The swot_errc_cycle stage: the Canvas -> SWOT -> ERRC loop of one canvas, inside one message."""
import uuid

import pytest
from bizstruct_domain.schemas import (
    ARTIFACT_ID_NAMESPACE,
    ArtifactType,
    Canvas,
    CanvasSections,
    ERRCActionType,
    CanvasSection,
    Errc,
    ErrcGenerated,
    ErrcMove,
    Swot,
    Stage,
    StageStatus,
    derive_artifact_id,
    final_canvas,
    final_swot,
    parse_artifact,
    project_status,
    select_final_version,
)

from bizstruct_ml.core.stage_runner import StageRunner
from bizstruct_ml.judge.base import ConsistencyJudge
from bizstruct_ml.judge.fake import FakeJudgeModel
from bizstruct_ml.llm.client import LLMError
from bizstruct_ml.observability import tracing
from bizstruct_ml.stages import SLICE_3_GENERATORS
from bizstruct_ml.stages.errc_apply import apply_moves
from bizstruct_ml.strategies.pipeline import Action
from tests.support.cycle_builders import canvas_model, errc_model
from tests.support.fake_backend import FakeBackend, all_done
from tests.support.fakes import FakeLLM
from tests.support.projects import ONE, SPLIT_IN_TWO, NO_FINDINGS, default_moves, scripted_llm, stage_runner
from tests.test_tracing import _FakeClient

CYCLE = Stage.SWOT_ERRC_CYCLE


async def run_cycle(scores, shape=ONE, errc=None, llm=None, runner=None):
    backend = FakeBackend(through=CYCLE)
    llm = llm or scripted_llm(shape, scores=scores, errc=errc)
    dispositions = await backend.run_to_completion(runner or stage_runner(llm))
    return backend, llm, dispositions


def artifacts_of(row, kind):
    return [parse_artifact(a) for a in row.artifacts if a.type == kind]


def cycle_of(backend, index=0):
    return backend.rows_of(CYCLE)[index]


# -- the loop: iterations, artifacts, the derived final version ---------------------------------------------------


@pytest.mark.parametrize(
    ("scores", "n_swot", "final"),
    [
        ((60, 70), 2, 1),                       # no improvement: v1 final (the loop always tries one step, ADR-0012)
        ((100, 95, 90, 85, 80), 5, 5),          # steady improvement up to the limit
        ((100, 90, 95), 3, 2),                  # improvement, then worsening: final in between
        ((100, 90, 80, 85, 70), 4, 3),          # worsening at v4 ends it
        ((100, 100), 2, 1),                     # equal scores stop it
        ((100, 90, 90), 3, 2),                  # equal after an improvement
    ],
)
async def test_the_loop_stops_by_the_rules_and_the_domain_derives_the_final_version(scores, n_swot, final):
    backend, llm, _ = await run_cycle(scores)
    row = cycle_of(backend)
    swots, errcs = artifacts_of(row, ArtifactType.SWOT), artifacts_of(row, ArtifactType.ERRC)
    canvases = artifacts_of(row, ArtifactType.CANVAS)
    assert (len(swots), len(errcs), len(canvases)) == (n_swot, n_swot - 1, n_swot - 1)
    assert [s.canvas_version for s in swots] == list(range(1, n_swot + 1))
    assert [c.version for c in canvases] == list(range(2, n_swot + 1))
    assert select_final_version([s.weighted_weakness_threat_score for s in swots]) == final
    assert final_swot(swots).canvas_version == final
    (canvas_row,) = backend.rows_of(Stage.CANVAS)
    v1 = parse_artifact(canvas_row.artifacts[0])
    assert final_canvas([v1, *canvases], swots).version == final
    assert all_done(backend) and row.status == StageStatus.DONE
    assert project_status(list(backend.rows.values())) == "running"  # later stages do not exist yet


async def test_nothing_in_the_returned_artifacts_marks_the_final_version():
    backend, *_ = await run_cycle((100, 90, 95))
    for record in cycle_of(backend).artifacts:
        assert "is_final" not in record.data


async def test_the_loop_makes_two_llm_calls_per_step_plus_the_last_swot():
    backend, llm, _ = await run_cycle((100, 95, 97))
    cycle_calls = [c["schema"].__name__ for c in llm.calls if c["schema"].__name__ in ("SwotGenerated", "ErrcGenerated")]
    assert cycle_calls == ["SwotGenerated", "ErrcGenerated", "SwotGenerated", "ErrcGenerated", "SwotGenerated"]


async def test_the_row_refs_are_its_canvas_row_only_and_it_has_instance_index_zero():
    backend, *_ = await run_cycle((60, 70), shape=SPLIT_IN_TWO)
    rows = backend.rows_of(CYCLE)
    assert len(rows) == 2 and {r.instance_index for r in rows} == {0}
    for canvas_row, cycle_row in zip(backend.rows_of(Stage.CANVAS), rows):
        assert cycle_row.refs == {Stage.CANVAS: [canvas_row.id]}


# -- ids, versions, the chain -------------------------------------------------------------------------------------


async def test_ids_follow_the_documented_derivation_and_the_version_chain_is_linked():
    backend, *_ = await run_cycle((100, 90, 95))
    row = cycle_of(backend)
    swots, errcs = artifacts_of(row, ArtifactType.SWOT), artifacts_of(row, ArtifactType.ERRC)
    canvases = artifacts_of(row, ArtifactType.CANVAS)
    v1 = parse_artifact(backend.rows_of(Stage.CANVAS)[0].artifacts[0])
    chain = [v1, *canvases]
    assert [s.id for s in swots] == [derive_artifact_id(row.id, ArtifactType.SWOT, k) for k in (1, 2, 3)]
    assert [e.id for e in errcs] == [derive_artifact_id(row.id, ArtifactType.ERRC, k) for k in (1, 2)]
    assert [c.id for c in canvases] == [derive_artifact_id(row.id, ArtifactType.CANVAS, k) for k in (2, 3)]
    assert [c.version for c in chain] == [1, 2, 3]
    assert [c.previous_version_id for c in chain] == [None, chain[0].id, chain[1].id]
    for k, swot in enumerate(swots, start=1):
        assert swot.canvas_id == chain[k - 1].id and swot.canvas_version == k and swot.environment_scan_id is None
    for k, errc in enumerate(errcs, start=1):
        assert (errc.from_version, errc.to_version) == (k, k + 1)
        assert errc.canvas_id == chain[k - 1].id and errc.swot_id == swots[k - 1].id and errc.result_canvas_id == chain[k].id
    assert all(c.group_id == v1.group_id and c.empathy_map_ids == v1.empathy_map_ids and c.is_generated is False for c in canvases)


async def test_regeneration_gives_the_same_ids_including_cards_that_were_not_changed():
    backend, *_ = await run_cycle((100, 90, 95))
    row = cycle_of(backend)
    before = {a.id for a in row.artifacts}
    cards_before = [c.id for canvas in artifacts_of(row, ArtifactType.CANVAS) for name in CanvasSections.model_fields for c in getattr(canvas.sections, name)]
    # regenerate the same row with different scores (still 3 versions) and a different new-card text
    def other_moves(version, messages):
        moves = default_moves(version)
        return ErrcGenerated(moves=[moves.moves[0], moves.moves[1].model_copy(update={"new_text": f"a different idea {version}"})])

    row.status, row.attempt_id = StageStatus.RUNNING, "again"
    from tests.support.fakes import brief_row  # noqa: F401  (snapshot only needs the closure)
    from bizstruct_domain.schemas import ProjectSnapshot

    snapshot = ProjectSnapshot(project_id="project_001", idea="x", language="en", rows=backend.closure_of(row.id))
    outcome = await stage_runner(scripted_llm(ONE, scores=(105, 95, 100), errc=other_moves)).run(row, snapshot, "en")
    assert outcome.success
    assert {r.id for r in outcome.artifacts} == before
    again = [parse_artifact(r) for r in outcome.artifacts if r.type == ArtifactType.CANVAS]
    cards_after = [c.id for canvas in again for name in CanvasSections.model_fields for c in getattr(canvas.sections, name)]
    assert cards_after == cards_before
    texts_before = {c.text for canvas in artifacts_of(row, ArtifactType.CANVAS) for c in canvas.sections.channels}
    texts_after = {c.text for canvas in again for c in canvas.sections.channels}
    assert any("a different idea" in t for t in texts_after) and texts_before != texts_after


async def test_unchanged_cards_keep_their_ids_from_version_one_and_new_cards_get_derived_ids():
    backend, *_ = await run_cycle((100, 90, 95))
    row = cycle_of(backend)
    v1 = parse_artifact(backend.rows_of(Stage.CANVAS)[0].artifacts[0])
    v2, v3 = artifacts_of(row, ArtifactType.CANVAS)
    v1_ids = {c.id for name in CanvasSections.model_fields for c in getattr(v1.sections, name)}
    v2_new = {c.id for name in CanvasSections.model_fields for c in getattr(v2.sections, name) if c.errc_marker == ERRCActionType.CREATE}
    carried2 = [c for name in CanvasSections.model_fields for c in getattr(v2.sections, name) if c.errc_marker != ERRCActionType.CREATE]
    assert {c.id for c in carried2} == v1_ids  # every v1 card is still there with its id
    carried3 = {c.id for name in CanvasSections.model_fields for c in getattr(v3.sections, name) if c.errc_marker != ERRCActionType.CREATE}
    assert carried3 == v1_ids | v2_new  # and v3 keeps the cards v2 created, under the ids v2 gave them
    new = [c for c in v2.sections.channels if c.errc_marker == ERRCActionType.CREATE]
    assert [c.id for c in new] == [str(uuid.uuid5(ARTIFACT_ID_NAMESPACE, f"{v2.id}:card:0"))]


# -- retries and failures ------------------------------------------------------------------------------------------


async def test_a_move_with_an_unknown_target_retries_the_errc_call_with_the_message():
    def errc(version, messages):
        if version == 1 and sum("Never target the same card twice" in m["content"] for m in messages[:1]) and not any("could not be used" in m["content"] for m in messages):
            return ErrcGenerated(moves=[ErrcMove(action=ERRCActionType.ELIMINATE, target_section=CanvasSection.CHANNELS,
                                                 target_card_text="a card that does not exist", opposite_side_impact="i", rationale="r")])
        return default_moves(version)

    backend, llm, _ = await run_cycle((90, 100), errc=errc)
    errc_calls = [c for c in llm.calls if c["schema"] is ErrcGenerated]
    assert len(errc_calls) == 2
    feedback = errc_calls[1]["messages"][-1]["content"]
    assert "could not be used" in feedback and "'a card that does not exist'" in feedback and "Move 1 (eliminate)" in feedback
    assert cycle_of(backend).status == StageStatus.DONE


async def test_a_failure_in_iteration_three_fails_the_whole_row_and_names_the_iteration():
    base = scripted_llm(ONE, scores=(100, 90, 80, 70))
    from bizstruct_domain.schemas import SwotGenerated
    from tests.support.projects import canvas_version

    inner = base._replies[0]

    def reply(messages, schema):
        if schema is SwotGenerated and canvas_version(messages) == 3:
            raise LLMError("provider is down")
        return inner(messages, schema)

    backend, llm, _ = await run_cycle(None, llm=FakeLLM([reply]))
    row = cycle_of(backend)
    assert row.status == StageStatus.ERROR
    assert "cycle iteration 3" in row.error and "provider is down" in row.error
    assert row.artifacts == []  # no partial results
    failed = [r for r in backend.posted if r.stage_row_id == row.id]
    assert failed[-1].status == "failed" and failed[-1].artifacts == []


async def test_a_swot_that_breaks_the_catalog_retries_with_the_validator_message():
    from bizstruct_domain.schemas import SwotGenerated, SwotCluster
    from tests.support.cycle_builders import swot_generated

    inner = scripted_llm(ONE, scores=(100, 90, 95))._replies[0]
    state = {"bad": True}

    def reply(messages, schema):
        if schema is SwotGenerated and state["bad"]:
            state["bad"] = False
            good = swot_generated(100)
            broken = good.model_copy(deep=True)
            broken.clusters[0].threats.pop()
            return SwotGenerated.model_construct(clusters=broken.clusters)
        return inner(messages, schema)

    backend, llm, _ = await run_cycle(None, llm=FakeLLM([reply]))
    swot_calls = [c for c in llm.calls if c["schema"] is SwotGenerated]
    assert len(swot_calls) == 4 and "validation error for Swot" in swot_calls[1]["messages"][-1]["content"]
    assert cycle_of(backend).status == StageStatus.DONE


async def test_a_deterministic_error_on_an_errc_retries_that_call_and_a_remaining_error_is_reported():
    from bizstruct_domain.schemas import ConsistencyRule, ConsistencyViolation, RuleInput, Arity

    def no_idea_two(errc: Errc):
        return [ConsistencyViolation(rule_id="no_idea_two", severity="error", message="Do not propose idea two.", artifact_ids=[errc.id])
                for move in errc.moves if (move.new_text or "").endswith("idea 1")]

    rule = ConsistencyRule("no_idea_two", (RuleInput(artifact=ArtifactType.ERRC, arity=Arity.EACH),), no_idea_two)

    def errc(version, messages):
        feedback = messages[-1]["content"]
        moves = default_moves(version)
        if "Do not propose idea two." not in feedback:
            return moves
        return ErrcGenerated(moves=[moves.moves[0], moves.moves[1].model_copy(update={"new_text": "a fresh channel"})])

    llm = scripted_llm(ONE, scores=(90, 100), errc=errc)
    runner = StageRunner(SLICE_3_GENERATORS, llm, ConsistencyJudge(FakeJudgeModel([NO_FINDINGS]), retry_wait=0), rules=[rule], retry_wait=0)
    backend, llm, _ = await run_cycle(None, llm=llm, runner=runner)
    errc_calls = [c for c in llm.calls if c["schema"] is ErrcGenerated]
    assert len(errc_calls) == 2  # one regeneration of the Errc call only, not of the whole row
    assert len([c for c in llm.calls if c["schema"].__name__ == "SwotGenerated"]) == 2
    assert not cycle_of(backend).consistency.has_errors

    stubborn = scripted_llm(ONE, scores=(90, 100))  # default moves always contain "idea 1": the error cannot be fixed
    runner = StageRunner(SLICE_3_GENERATORS, stubborn, ConsistencyJudge(FakeJudgeModel([NO_FINDINGS]), retry_wait=0), rules=[rule], retry_wait=0)
    backend, llm, _ = await run_cycle(None, llm=stubborn, runner=runner)
    assert len([c for c in llm.calls if c["schema"] is ErrcGenerated]) == 3  # 1 + MAX_CONSISTENCY_RETRIES
    report = cycle_of(backend).consistency
    assert report.has_errors and [v.rule_id for v in report.violations] == ["no_idea_two"]
    assert cycle_of(backend).status == StageStatus.AWAITING_DECISION  # be decides; ml still returned the artifacts
    assert cycle_of(backend).artifacts


# -- the produced result --------------------------------------------------------------------------------------------


async def test_the_posted_result_validates_and_every_artifact_parses():
    backend, *_ = await run_cycle((100, 90, 95))
    row = cycle_of(backend)
    result = next(r for r in backend.posted if r.stage_row_id == row.id)
    assert result.status == "success" and result.consistency is not None and not result.consistency.has_errors
    for record in result.artifacts:
        assert parse_artifact(record) is not None
    assert sorted(r.type.value for r in result.artifacts) == sorted(["swot"] * 3 + ["errc"] * 2 + ["canvas"] * 2)


async def test_the_consistency_pass_of_the_cycle_row_runs_the_registered_rules_without_special_cases():
    # patterns is two hops away: the closure fallback of ONE makes canvas_group_id_is_known gatherable here
    backend, *_ = await run_cycle((100, 90, 95), shape=SPLIT_IN_TWO)
    for row in backend.rows_of(CYCLE):
        assert row.status == StageStatus.DONE and row.consistency.score == 5 and not row.consistency.violations


async def test_pitch_risk_check_input_is_gatherable_on_a_finished_cycle_row():
    from bizstruct_domain.schemas import JUDGE_CHECKS, StageRow
    from bizstruct_ml.core.context import gather_inputs, rows_by_id

    backend, *_ = await run_cycle((100, 90, 95))
    cycle = cycle_of(backend)
    pitch = StageRow(id="row_pitch_0", stage=Stage.PITCH, status=StageStatus.RUNNING, attempt_id="a", refs={CYCLE: [cycle.id]})
    check = next(c for c in JUDGE_CHECKS if c.id == "pitch_risk_analysis_grounded_in_swot")
    rows = rows_by_id([*backend.closure_of(cycle.id), pitch])
    ((swot,),) = gather_inputs((check.inputs[0],), fresh_row=pitch, fresh_artifacts=[], rows=rows)
    assert swot.canvas_version == 2


# -- trace metadata ---------------------------------------------------------------------------------------------------


async def test_final_version_and_the_score_series_go_into_the_trace(monkeypatch):
    fake = _FakeClient()
    monkeypatch.setattr(tracing, "_get_client", lambda: fake)
    await run_cycle((100, 90, 95))
    summary = next(s for s in fake.spans_created if s.name == "cycle_summary")
    meta = next(u["metadata"] for u in summary.updates if "metadata" in u)
    assert meta == {"final_version": 2, "scores": [100.0, 90.0, 95.0], "iterations": 3}
    labels = [s.kwargs["metadata"]["label"] for s in fake.spans_created if s.name == "llm_call" and "label" in s.kwargs.get("metadata", {})]
    assert labels[:3] == ["swot v1", "errc v1", "swot v2"]


# -- registration -----------------------------------------------------------------------------------------------------------


def test_the_runner_registers_the_cycle_generator_only_with_its_two_contracts():
    from bizstruct_domain.schemas import SwotGenerated
    from bizstruct_ml.stages.swot_errc_cycle import SwotErrcCycleGenerator

    class Wrong(SwotErrcCycleGenerator):
        contracts = (SwotGenerated,)

    with pytest.raises(ValueError, match="must declare that stage and exactly its generation contracts"):
        StageRunner({CYCLE: Wrong()}, FakeLLM([None]), ConsistencyJudge(FakeJudgeModel(), retry_wait=0))
    assert stage_runner(FakeLLM([None])).prompt_version(CYCLE) == "swot=1,errc=2"


def test_a_gap_in_the_swot_versions_is_refused_before_anything_is_returned():
    from bizstruct_ml.core.stage_runner import GenerationFailed
    from bizstruct_ml.stages.swot_errc_cycle import check_contiguous
    from tests.support.cycle_builders import swot_scoring

    one, three = swot_scoring(90, "r", 1), swot_scoring(80, "r", 3)
    check_contiguous([one, swot_scoring(80, "r", 2)])
    with pytest.raises(GenerationFailed, match=r"contiguous from 1, got \[1, 3\]"):
        check_contiguous([one, three])
    with pytest.raises(GenerationFailed):
        check_contiguous([swot_scoring(90, "r", 2)])


async def test_the_outcome_counts_the_per_call_consistency_retries():
    from bizstruct_domain.schemas import ConsistencyRule, ConsistencyViolation, RuleInput, Arity, ProjectSnapshot

    rule = ConsistencyRule(
        "always", (RuleInput(artifact=ArtifactType.ERRC, arity=Arity.EACH),),
        lambda e: [ConsistencyViolation(rule_id="always", severity="error", message="no", artifact_ids=[e.id])],
    )
    llm = scripted_llm(ONE, scores=(90, 100))
    runner = StageRunner(SLICE_3_GENERATORS, llm, ConsistencyJudge(FakeJudgeModel([NO_FINDINGS]), retry_wait=0), rules=[rule], retry_wait=0)
    backend = FakeBackend(through=CYCLE)
    await backend.run_to_completion(stage_runner(llm))
    row = cycle_of(backend)
    snapshot = ProjectSnapshot(project_id="project_001", idea="x", language="en", rows=backend.closure_of(row.id))
    outcome = await runner.run(row, snapshot, "en")
    assert outcome.consistency_retries == 2 and outcome.success and outcome.consistency.has_errors


# -- reduce / raise carry the card's new text (domain 0.17.0) ---------------------------------------------------------


async def test_a_raise_replaces_the_cards_text_in_the_next_version_and_keeps_its_id():
    backend, *_ = await run_cycle((100, 90, 95))
    row = cycle_of(backend)
    v1 = parse_artifact(backend.rows_of(Stage.CANVAS)[0].artifacts[0])
    v2, v3 = artifacts_of(row, ArtifactType.CANVAS)
    target = v1.sections.value_propositions[0]
    assert target.text == "value_propositions card 1"  # the default raise target
    assert (v2.sections.value_propositions[0].id, v2.sections.value_propositions[0].text) == (target.id, "value_propositions card 1 (level 1)")
    assert (v3.sections.value_propositions[0].id, v3.sections.value_propositions[0].text) == (target.id, "value_propositions card 1 (level 2)")
    assert v2.sections.value_propositions[0].errc_marker == ERRCActionType.RAISE


def _violating_then_valid(first: ErrcMove):
    def errc(version, messages):
        if version == 1 and not any("could not be used" in m["content"] for m in messages):
            return first
        return default_moves(version)

    return errc


@pytest.mark.parametrize(
    ("bad", "message"),
    [
        ({"action": ERRCActionType.RAISE, "target_card_text": "value_propositions card 1"}, "new_text must be provided when action is RAISE"),
        ({"action": ERRCActionType.REDUCE, "target_card_text": "value_propositions card 1"}, "new_text must be provided when action is REDUCE"),
        ({"action": ERRCActionType.ELIMINATE, "target_card_text": "value_propositions card 1", "new_text": "x"}, "new_text must be None when action is ELIMINATE"),
        ({"action": ERRCActionType.CREATE, "new_text": "x", "target_card_text": "value_propositions card 1"}, "target_card_text must be None when action is CREATE"),
    ],
)
async def test_a_field_rule_violation_retries_and_the_message_names_the_action_and_the_field(bad, message):
    """The client parses the answer with the contract, so the violation is raised by the LLM call itself. The runner
    must show the message to the model, not just retry blindly."""
    from pydantic import ValidationError

    inner = scripted_llm(ONE, scores=(90, 100))._replies[0]
    state = {"failed": False}

    def reply(messages, schema):
        if schema is ErrcGenerated and not state["failed"]:
            state["failed"] = True
            ErrcMove(action=bad["action"], target_section=CanvasSection.VALUE_PROPOSITIONS, target_card_text=bad.get("target_card_text"),
                     new_text=bad.get("new_text"), opposite_side_impact="i", rationale="r")  # raises the domain's ValidationError
        return inner(messages, schema)

    llm = FakeLLM([reply])
    with pytest.raises(ValidationError):
        reply([{}, {}], ErrcGenerated)  # the helper really does raise
    state["failed"] = False
    backend, llm, _ = await run_cycle(None, llm=llm)
    errc_calls = [c for c in llm.calls if c["schema"] is ErrcGenerated]
    assert len(errc_calls) == 2
    feedback = errc_calls[1]["messages"][-1]["content"]
    assert "could not be used" in feedback and message in feedback
    assert cycle_of(backend).status == StageStatus.DONE
