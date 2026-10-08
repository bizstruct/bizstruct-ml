"""The Canvas generator and the whole slice 2 graph: patterns -> one canvas row per group."""
import json
import uuid

import pytest
from bizstruct_domain.schemas import (
    ARTIFACT_ID_NAMESPACE,
    ArtifactRecord,
    ArtifactType,
    Canvas,
    CanvasGenerated,
    CanvasSections,
    Patterns,
    ProjectSnapshot,
    Stage,
    StageStatus,
    canvas_rows_for,
    derive_artifact_id,
    parse_artifact,
    project_status,
    ready_rows,
)

from bizstruct_ml.core.stage_runner import StageRunner
from bizstruct_ml.judge.base import ConsistencyJudge
from bizstruct_ml.judge.fake import FakeJudgeModel
from bizstruct_ml.llm.prompts import canvas as prompt
from bizstruct_ml.stages import SLICE_2_GENERATORS
from bizstruct_ml.stages.canvas import CanvasGenerator, card_id_factory
from bizstruct_ml.strategies.pipeline import Action
from tests.support.fake_backend import FakeBackend, all_done
from tests.support.fakes import FakeLLM
from tests.support.projects import (
    NO_FINDINGS,
    ONE,
    SHAPES,
    SPLIT_IN_THREE,
    SPLIT_IN_TWO,
    THREE_IN_ONE_MULTI_SIDED,
    Shape,
    canvas_generated,
    scripted_llm,
    seed,
    stage_runner,
)


def em_id(k: int) -> str:
    return derive_artifact_id(f"row_empathy_map_{k}", ArtifactType.EMPATHY_MAP, 0)


async def settle(shape: Shape, llm: FakeLLM | None = None, judge_model: FakeJudgeModel | None = None):
    backend = FakeBackend(through=Stage.CANVAS)
    llm = llm or scripted_llm(shape)
    judge_model = judge_model or FakeJudgeModel([NO_FINDINGS])
    dispositions = await backend.run_to_completion(stage_runner(llm, judge_model))
    return backend, llm, judge_model, dispositions


def canvas_calls(llm: FakeLLM) -> list[dict]:
    return [c for c in llm.calls if c["schema"] is CanvasGenerated]


# -- the graph, end to end, per shape ----------------------------------------------------------------


@pytest.mark.parametrize("shape", SHAPES, ids=lambda s: s.name)
async def test_ready_rows_drive_the_project_through_patterns_and_canvas_to_done(shape: Shape):
    backend, llm, _, dispositions = await settle(shape)
    n = len(shape.segments)
    assert all(d.action == Action.COMPLETE and d.reason == "ResultApplied" for d in dispositions)
    assert all_done(backend)
    assert len(dispositions) == 1 + 3 * n + 1 + len(shape.groups)
    assert len(backend.rows_of(Stage.PATTERNS)) == 1
    assert len(backend.rows_of(Stage.CANVAS)) == len(shape.groups)
    assert ready_rows(list(backend.rows.values())) == ()
    # later stages do not exist, so the project is not complete
    assert project_status(list(backend.rows.values())) == "running"


@pytest.mark.parametrize("shape", SHAPES, ids=lambda s: s.name)
async def test_canvas_rows_are_created_in_canvas_rows_for_order_with_refs_per_the_adr(shape: Shape):
    backend, *_ = await settle(shape)
    (patterns_row,) = backend.rows_of(Stage.PATTERNS)
    patterns = parse_artifact(patterns_row.artifacts[0])
    assert isinstance(patterns, Patterns)
    specs = canvas_rows_for(patterns)
    assert [r.instance_index for r in backend.rows_of(Stage.CANVAS)] == list(range(len(specs)))
    assert patterns_row.refs == {
        Stage.CUSTOMER_SCENARIO: [r.id for r in backend.rows_of(Stage.CUSTOMER_SCENARIO)],
        Stage.IDEATION: [r.id for r in backend.rows_of(Stage.IDEATION)],
    }
    for row, spec, members in zip(backend.rows_of(Stage.CANVAS), specs, shape.groups):
        wanted = [f"row_empathy_map_{n - 1}" for n in members]
        assert row.refs[Stage.EMPATHY_MAP] == wanted
        assert row.refs[Stage.CUSTOMER_SCENARIO] == [f"row_customer_scenario_{n - 1}" for n in members]
        assert row.refs[Stage.IDEATION] == [f"row_ideation_{n - 1}" for n in members]
        assert row.refs[Stage.PATTERNS] == [patterns_row.id] and row.refs[Stage.BRIEF] == ["row_brief_0"]
        assert spec.empathy_map_ids == [em_id(n - 1) for n in members]


@pytest.mark.parametrize("shape", SHAPES, ids=lambda s: s.name)
async def test_scenario_and_ideation_rows_all_have_instance_index_zero(shape: Shape):
    backend, *_ = await settle(shape)
    for stage in (Stage.CUSTOMER_SCENARIO, Stage.IDEATION, Stage.PATTERNS):
        assert {r.instance_index for r in backend.rows_of(stage)} == {0}
    assert len({r.id for r in backend.rows_of(Stage.CUSTOMER_SCENARIO)}) == len(shape.segments)


# -- row k uses group k ---------------------------------------------------------------------------------


@pytest.mark.parametrize("shape", SHAPES, ids=lambda s: s.name)
async def test_canvas_row_k_uses_patterns_group_k_and_only_that_groups_maps(shape: Shape):
    backend, *_ = await settle(shape)
    patterns = parse_artifact(backend.rows_of(Stage.PATTERNS)[0].artifacts[0])
    for k, row in enumerate(backend.rows_of(Stage.CANVAS)):
        canvas = parse_artifact(row.artifacts[0])
        assert isinstance(canvas, Canvas)
        assert canvas.group_id == patterns.groups[k].id
        assert canvas.empathy_map_ids == [em_id(n - 1) for n in shape.groups[k]] == patterns.groups[k].empathy_map_ids
        assert canvas.version == 1 and canvas.previous_version_id is None and canvas.is_final is False
        assert canvas.id == derive_artifact_id(row.id, ArtifactType.CANVAS, 1)


@pytest.mark.parametrize("shape", [SPLIT_IN_TWO, SPLIT_IN_THREE], ids=lambda s: s.name)
async def test_each_canvas_prompt_shows_only_its_groups_segments(shape: Shape):
    _, llm, *_ = await settle(shape)
    calls = canvas_calls(llm)
    assert len(calls) == len(shape.groups)
    for call, members in zip(calls, shape.groups):
        user = call["messages"][1]["content"]
        for n, seg in enumerate(shape.segments, start=1):
            assert (seg.persona in user) == (n in members), (seg.persona, members)
        assert f"covers {len(members)} segment" in user


async def test_the_prompt_carries_the_group_relation_the_tags_and_their_rationale():
    _, llm, *_ = await settle(THREE_IN_ONE_MULTI_SIDED)
    (call,) = canvas_calls(llm)
    user, system = call["messages"][1]["content"], call["messages"][0]["content"]
    assert "relation_type of the group: multi_sided" in user
    assert "unified canvas with several customer segments" in user
    assert "- multi_sided_platform: Grounded in the epicenter of the segments." in user
    assert "pains: " in user and "gains: " in user and "open questions: Which channel fits Event hosts?" in user
    assert "a value proposition for EACH side" in system and "do not decide it here" in system


async def test_a_single_segment_canvas_is_described_as_such():
    _, llm, *_ = await settle(ONE)
    (call,) = canvas_calls(llm)
    user = call["messages"][1]["content"]
    assert "single-segment canvas" in user and "Pattern tags of the project: none." in user
    assert "Never invent another segment" in call["messages"][0]["content"]


# -- ids --------------------------------------------------------------------------------------------------


def test_card_ids_follow_the_documented_formula_in_the_order_from_generated_asks():
    new_id = card_id_factory("canvas-1")
    assert [new_id() for _ in range(3)] == [str(uuid.uuid5(ARTIFACT_ID_NAMESPACE, f"canvas-1:card:{n}")) for n in range(3)]
    assert card_id_factory("canvas-2")() != card_id_factory("canvas-1")()


def test_two_conversions_of_different_texts_yield_the_same_ids():
    def convert(tag: str) -> Canvas:
        return Canvas.from_generated(canvas_generated(tag), id="c", group_id="g", empathy_map_ids=["e"], new_card_id=card_id_factory("c"))

    one, two = convert(" first"), convert(" a completely different text")

    def ids(canvas: Canvas) -> list[str]:
        return [card.id for name in CanvasSections.model_fields for card in getattr(canvas.sections, name)]

    assert ids(one) == ids(two) and len(set(ids(one))) == len(ids(one)) == 18
    assert one.sections.value_propositions[0].text != two.sections.value_propositions[0].text


async def test_regenerating_a_canvas_row_keeps_the_canvas_id_and_every_card_id():
    backend, llm, *_ = await settle(SPLIT_IN_TWO)
    row = backend.rows_of(Stage.CANVAS)[0]
    before = parse_artifact(row.artifacts[0])
    snapshot = ProjectSnapshot(project_id="project_001", idea="x", language="en", rows=backend.closure_of(row.id))
    again = await stage_runner(FakeLLM([canvas_generated(" regenerated")])).run(row, snapshot, "en")
    after = parse_artifact(again.artifacts[0])
    assert after.id == before.id and after.group_id == before.group_id
    assert after.sections.value_propositions[0].text != before.sections.value_propositions[0].text
    for name in CanvasSections.model_fields:
        assert [c.id for c in getattr(after.sections, name)] == [c.id for c in getattr(before.sections, name)]


# -- the produced result validates -------------------------------------------------------------------------


@pytest.mark.parametrize("shape", SHAPES, ids=lambda s: s.name)
async def test_every_posted_result_validates_and_parses(shape: Shape):
    backend, *_ = await settle(shape)
    canvas_results = [r for r in backend.posted if r.stage_row_id.startswith("row_canvas")]
    assert len(canvas_results) == len(shape.groups)
    for result in canvas_results:
        assert result.status == "success" and len(result.artifacts) == 1
        (record,) = result.artifacts
        assert record.type == ArtifactType.CANVAS
        assert isinstance(parse_artifact(ArtifactRecord.model_validate(record.model_dump())), Canvas)
        assert result.consistency is not None and not result.consistency.has_errors


# -- consistency wiring -------------------------------------------------------------------------------------


@pytest.mark.parametrize("shape", SHAPES, ids=lambda s: s.name)
async def test_the_two_judge_checks_run_once_per_applicable_row(shape: Shape):
    _, _, judge_model, _ = await settle(shape)
    kinds = [tuple(sorted(json.loads(c["user"]))) for c in judge_model.calls]
    n = len(shape.segments)
    # customer_scenario rows: persona check x n; patterns row: ideation_grounds_pattern_tags x 1; canvas rows: one each
    assert kinds.count(("customer_scenario", "empathy_map")) == n
    assert kinds.count(("ideation", "patterns")) == 1
    assert kinds.count(("canvas", "customer_scenario", "empathy_map")) == len(shape.groups)
    assert len(kinds) == n + 1 + len(shape.groups)


@pytest.mark.parametrize("shape", [SPLIT_IN_TWO, SPLIT_IN_THREE, THREE_IN_ONE_MULTI_SIDED, ONE], ids=lambda s: s.name)
async def test_the_canvas_judge_gets_the_groups_maps_and_scenarios_not_the_projects(shape: Shape):
    _, _, judge_model, _ = await settle(shape)
    canvas_payloads = [json.loads(c["user"]) for c in judge_model.calls if "canvas" in json.loads(c["user"])]
    assert len(canvas_payloads) == len(shape.groups)
    for payload, members in zip(canvas_payloads, shape.groups):
        assert sorted(m["persona_name"] for m in payload["empathy_map"]) == sorted(shape.segments[n - 1].persona for n in members)
        assert len(payload["customer_scenario"]) == len(members)


async def test_gather_inputs_gives_a_patterns_row_all_maps_through_the_closure():
    from bizstruct_ml.core.consistency import applicable_checks
    from bizstruct_ml.core.context import gather_inputs, rows_by_id
    from bizstruct_domain.schemas import RuleInput, StageArity

    backend = seed(SPLIT_IN_THREE)
    rows = rows_by_id(backend.closure_of("row_patterns_0"))
    (maps,) = gather_inputs(
        [RuleInput(stage=Stage.EMPATHY_MAP, arity=StageArity.MANY)], fresh_row=backend.rows["row_patterns_0"], fresh_artifacts=[], rows=rows
    )
    assert len(maps) == 3
    assert applicable_checks(backend.rows["row_patterns_0"], rows) != []


class WrongGroupCanvas(CanvasGenerator):
    """Produces a canvas whose group_id is not one of the groups of Patterns."""

    def to_artifacts(self, generated, ctx):
        ((kind, canvas),) = super().to_artifacts(generated, ctx)
        return [(kind, canvas.model_copy(update={"group_id": "not-a-group"}))]


async def test_canvas_group_id_is_known_errors_retry_and_then_return_the_report():
    backend = seed(SPLIT_IN_TWO, through=Stage.CANVAS, dispatch=False)
    runner = StageRunner(
        {**SLICE_2_GENERATORS, Stage.CANVAS: WrongGroupCanvas()}, scripted_llm(SPLIT_IN_TWO),
        ConsistencyJudge(FakeJudgeModel([NO_FINDINGS]), retry_wait=0), retry_wait=0,
    )
    await backend.run_to_completion(runner)  # patterns first, then the canvas rows
    row = backend.rows_of(Stage.CANVAS)[0]
    assert row.status == StageStatus.AWAITING_DECISION
    assert [v.rule_id for v in row.consistency.violations if v.severity == "error"] == ["canvas_group_id_is_known"]


# -- context errors ---------------------------------------------------------------------------------------------


async def test_an_instance_index_beyond_the_groups_fails_the_row():
    backend, *_ = await settle(SPLIT_IN_TWO)
    row = backend.rows_of(Stage.CANVAS)[0]
    row.instance_index = 5
    snapshot = ProjectSnapshot(project_id="project_001", idea="x", language="en", rows=backend.closure_of(row.id))
    outcome = await stage_runner(FakeLLM([canvas_generated()])).run(row, snapshot, "en")
    assert not outcome.success and "instance_index 5 but Patterns has 2 groups" in outcome.failure.message


async def test_refs_that_do_not_match_the_group_fail_the_row():
    backend, *_ = await settle(SPLIT_IN_TWO)
    row = backend.rows_of(Stage.CANVAS)[0]
    row.instance_index = 1  # refs are group 0's maps
    snapshot = ProjectSnapshot(project_id="project_001", idea="x", language="en", rows=backend.closure_of(row.id))
    outcome = await stage_runner(FakeLLM([canvas_generated()])).run(row, snapshot, "en")
    assert not outcome.success and "refs empathy maps" in outcome.failure.message


def test_the_canvas_prompt_version_is_one():
    assert prompt.PROMPT_VERSION == "1" and CanvasGenerator.prompt_version == "1"
