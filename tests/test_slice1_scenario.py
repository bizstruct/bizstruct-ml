"""Walk brief -> 3 empathy_map rows -> customer_scenario/ideation rows with ready_rows
against the in-memory fake backend (which stands in for be)."""
import json

from bizstruct_domain.schemas import (
    ArtifactType,
    Brief,
    CustomerScenarioGenerated,
    EmpathyMapGenerated,
    IdeationGenerated,
    Stage,
    StageStatus,
    parse_artifact,
    project_status,
    ready_rows,
)

from bizstruct_ml.core.stage_runner import StageRunner
from bizstruct_ml.judge.base import ConsistencyJudge
from bizstruct_ml.judge.fake import FakeJudgeModel
from bizstruct_ml.strategies.pipeline import Action
from bizstruct_ml.stages import SLICE_1_GENERATORS
from tests.support.fake_backend import FakeBackend, all_done
from tests.support.fakes import FakeLLM, brief_model, empathy_generated
from tests.test_slice1_stages import IDEATION, NO_FINDINGS, SCENARIO

CANDIDATES = ["Urban parents", "Small farms", "Cafes"]


def scripted_llm() -> FakeLLM:
    """Answers by schema; the persona name echoes the segment named in the prompt."""

    def reply(messages: list[dict], schema: type):
        user = messages[-1]["content"]
        if schema is Brief:
            return brief_model().model_copy(update={"customer_segment_candidates": CANDIDATES})
        if schema is EmpathyMapGenerated:
            candidate = next(c for c in CANDIDATES if f"for this segment: {c}" in user)
            return empathy_generated(f"Persona of {candidate}")
        if schema is CustomerScenarioGenerated:
            return SCENARIO
        if schema is IdeationGenerated:
            return IDEATION
        raise AssertionError(f"unexpected schema {schema}")

    return FakeLLM([reply])


def runner(llm: FakeLLM, judge_model: FakeJudgeModel) -> StageRunner:
    return StageRunner(SLICE_1_GENERATORS, llm, ConsistencyJudge(judge_model, retry_wait=0), retry_wait=0)


async def test_graph_unfolds_through_ready_rows_and_every_row_ends_done():
    backend = FakeBackend()
    llm, judge_model = scripted_llm(), FakeJudgeModel([NO_FINDINGS])

    # Round 1: only the brief is ready.
    assert ready_rows(list(backend.rows.values())) == ("row_brief_0",)
    dispositions = await backend.run_to_completion(runner(llm, judge_model))

    assert all(d.action == Action.COMPLETE and d.reason == "ResultApplied" for d in dispositions)
    assert len(dispositions) == 1 + 3 + 3 + 3
    assert all_done(backend)
    assert {s: len(backend.rows_of(s)) for s in (Stage.BRIEF, Stage.EMPATHY_MAP, Stage.CUSTOMER_SCENARIO, Stage.IDEATION)} == {
        Stage.BRIEF: 1, Stage.EMPATHY_MAP: 3, Stage.CUSTOMER_SCENARIO: 3, Stage.IDEATION: 3,
    }
    assert project_status(list(backend.rows.values())) == "running"  # patterns and later stages do not exist yet


async def test_empathy_row_k_covers_candidate_k_and_downstream_rows_follow_their_map():
    backend = FakeBackend()
    await backend.run_to_completion(runner(scripted_llm(), FakeJudgeModel([NO_FINDINGS])))

    for k, candidate in enumerate(CANDIDATES):
        em_row = backend.rows_of(Stage.EMPATHY_MAP)[k]
        em = parse_artifact(em_row.artifacts[0])
        assert em.persona_name == f"Persona of {candidate}"
        for stage, artifact_type in ((Stage.CUSTOMER_SCENARIO, ArtifactType.CUSTOMER_SCENARIO), (Stage.IDEATION, ArtifactType.IDEATION)):
            row = backend.rows_of(stage)[k]
            assert row.refs == {Stage.EMPATHY_MAP: [em_row.id]}
            artifact = parse_artifact(row.artifacts[0])
            assert artifact.empathy_map_id == em.id  # foreign key follows the map of the same segment
            assert row.artifacts[0].type == artifact_type


async def test_only_the_scenarios_are_judged_once_each():
    backend = FakeBackend()
    judge_model = FakeJudgeModel([NO_FINDINGS])
    await backend.run_to_completion(runner(scripted_llm(), judge_model))
    assert len(judge_model.calls) == 3  # one persona check per customer_scenario row
    personas = {json.loads(c["user"])["empathy_map"]["persona_name"] for c in judge_model.calls}
    assert personas == {f"Persona of {c}" for c in CANDIDATES}


async def test_scenario_and_ideation_rows_are_not_ready_before_their_map_is_done():
    backend = FakeBackend()
    llm, judge_model = scripted_llm(), FakeJudgeModel([NO_FINDINGS])
    r = runner(llm, judge_model)
    from bizstruct_ml.strategies.pipeline import handle_message

    client = backend.client()
    await handle_message(backend.message_for("row_brief_0"), client, r)
    for k in range(3):
        assert backend.rows[f"row_empathy_map_{k}"].status == StageStatus.PENDING
    assert ready_rows(list(backend.rows.values())) == tuple(f"row_empathy_map_{k}" for k in range(3))
    await handle_message(backend.message_for("row_empathy_map_1"), client, r)
    ready = set(ready_rows(list(backend.rows.values())))
    assert {"row_customer_scenario_1", "row_ideation_1"} <= ready
    assert not ({"row_customer_scenario_0", "row_customer_scenario_2"} & ready)


async def test_a_redelivered_message_after_success_does_no_work():
    backend = FakeBackend()
    llm = scripted_llm()
    r = runner(llm, FakeJudgeModel([NO_FINDINGS]))
    from bizstruct_ml.strategies.pipeline import handle_message

    message = backend.message_for("row_brief_0")
    await handle_message(message, backend.client(), r)
    calls = len(llm.calls)
    again = await handle_message(message, backend.client(), r)  # same attempt_id, row is DONE
    assert again.reason == "AlreadyApplied" and len(llm.calls) == calls
