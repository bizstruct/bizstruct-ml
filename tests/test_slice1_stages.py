"""Slice 1 generators end to end: snapshot -> StageResult, with FakeLLM and a fake backend."""
import json

import pytest
from bizstruct_domain.schemas import (
    ArtifactType,
    Brief,
    CustomerScenarioGenerated,
    Epicenter,
    EmpathyMap,
    EpicenterClassification,
    GENERATION_CONTRACTS,
    IdeationGenerated,
    PricingTier,
    Stage,
    StageResult,
    StageStatus,
    derive_artifact_id,
    parse_artifact,
)

from bizstruct_ml.core.stage_runner import StageRunner
from bizstruct_ml.judge.base import ConsistencyJudge
from bizstruct_ml.judge.fake import FakeJudgeModel
from bizstruct_ml.llm.prompts._shared import field_guide
from bizstruct_ml.stages import SLICE_1_GENERATORS
from tests.support.fake_backend import FakeBackend
from tests.support.fakes import FakeLLM, brief_model, empathy_generated
from bizstruct_domain.schemas import EmpathyMapGenerated

SCENARIO = CustomerScenarioGenerated(
    situation_narrative="Olena orders a farm box on Friday evening.",
    pricing_tier=PricingTier.MID_MARKET,
    channel_type="digital-self-service",
    relationship_type="self-service",
    interdependence_signal=False,
    open_questions=["Which delivery window fits?"],
)
IDEATION = IdeationGenerated(
    epicenter=EpicenterClassification(tags=[Epicenter.CUSTOMER_DRIVEN], rationale="Strong unmet pain."),
    what_if_questions=["What if farms delivered directly?"],
)
NO_FINDINGS = json.dumps({"score": 5, "violations": []})


def runner(llm: FakeLLM, judge_model: FakeJudgeModel | None = None) -> StageRunner:
    return StageRunner(SLICE_1_GENERATORS, llm, ConsistencyJudge(judge_model or FakeJudgeModel([NO_FINDINGS]), retry_wait=0), retry_wait=0)


async def run_row(backend: FakeBackend, row_id: str, llm: FakeLLM, judge_model: FakeJudgeModel | None = None) -> StageResult:
    """Start the row the way be would and hand its message to the pipeline."""
    from bizstruct_ml.strategies.pipeline import handle_message

    message = backend.message_for(row_id)
    await handle_message(message, backend.client(), runner(llm, judge_model))
    return backend.posted[-1]


def finish(backend: FakeBackend, row_id: str, artifacts) -> None:
    """Mark an upstream row DONE with the given (type, model) artifacts, as if it had run."""
    from bizstruct_domain.schemas import ArtifactRecord

    row = backend.rows[row_id]
    row.status = StageStatus.DONE
    row.attempt_id = row.attempt_id or "done"
    row.artifacts = [ArtifactRecord(id=_id(row_id, t, m), type=t, data=m.model_dump(mode="json")) for t, m in artifacts]
    backend.expand()


def _id(row_id, t, m):
    return getattr(m, "id", None) or derive_artifact_id(row_id, t, 0)


def brief_with(candidates: list[str]) -> Brief:
    return brief_model().model_copy(update={"customer_segment_candidates": candidates})


async def test_brief_generator():
    backend = FakeBackend(idea="An app for farm boxes")
    brief = brief_with(["Urban parents"])
    llm = FakeLLM([brief])
    result = await run_row(backend, "row_brief_0", llm)
    assert result.status == "success"
    (record,) = result.artifacts
    assert record.type == ArtifactType.BRIEF and record.id == derive_artifact_id("row_brief_0", ArtifactType.BRIEF, 0)
    assert parse_artifact(record).industry == "Food"
    assert llm.calls[0]["schema"] is GENERATION_CONTRACTS[Stage.BRIEF][0]
    assert "An app for farm boxes" in llm.calls[0]["messages"][1]["content"]


async def test_brief_in_ukrainian_asks_for_ukrainian():
    backend = FakeBackend(language="uk")
    llm = FakeLLM([brief_with(["Міські батьки"])])
    await run_row(backend, "row_brief_0", llm)
    assert "Ukrainian" in llm.calls[0]["messages"][0]["content"]


@pytest.mark.parametrize("candidates", [["Urban parents"], ["Urban parents", "Small farms", "Cafes"]])
async def test_empathy_map_row_k_uses_candidate_k(candidates):
    backend = FakeBackend()
    finish(backend, "row_brief_0", [(ArtifactType.BRIEF, brief_with(candidates))])
    for k, candidate in enumerate(candidates):
        llm = FakeLLM([empathy_generated(f"Persona {k}")])
        result = await run_row(backend, f"row_empathy_map_{k}", llm)
        assert result.status == "success"
        user = llm.calls[0]["messages"][1]["content"]
        assert f"Build the empathy map for this segment: {candidate}" in user
        for other in candidates:
            if other != candidate:
                assert f"for this segment: {other}" not in user


async def test_empathy_map_system_fields_and_stable_ids():
    backend = FakeBackend()
    finish(backend, "row_brief_0", [(ArtifactType.BRIEF, brief_with(["Urban parents"]))])
    first = await run_row(backend, "row_empathy_map_0", FakeLLM([empathy_generated("A")]))
    (record,) = first.artifacts
    empathy = parse_artifact(record)
    assert isinstance(empathy, EmpathyMap)
    assert empathy.project_id == "project_001"
    assert record.id == derive_artifact_id("row_empathy_map_0", ArtifactType.EMPATHY_MAP, 0)

    # regenerating the same row (a new attempt) yields the same artifact id
    backend.rows["row_empathy_map_0"].status = StageStatus.PENDING
    second = await run_row(backend, "row_empathy_map_0", FakeLLM([empathy_generated("B")]))
    assert second.artifacts[0].id == record.id and second.artifacts[0].data["persona_name"] == "B"


async def test_an_instance_index_beyond_the_candidates_fails_the_row():
    backend = FakeBackend()
    finish(backend, "row_brief_0", [(ArtifactType.BRIEF, brief_with(["Only one"]))])
    backend.add_row(Stage.EMPATHY_MAP, 2, {Stage.BRIEF: ["row_brief_0"]})
    llm = FakeLLM([empathy_generated()])
    result = await run_row(backend, "row_empathy_map_2", llm)
    assert result.status == "failed" and result.error.message.startswith("context: ") and "instance_index 2" in result.error.message
    assert llm.calls == []


def ready_empathy(backend: FakeBackend) -> EmpathyMap:
    finish(backend, "row_brief_0", [(ArtifactType.BRIEF, brief_with(["Urban parents"]))])
    from bizstruct_domain.schemas import EmpathyMap as EM

    em = EM.from_generated(empathy_generated("Olena"), id=derive_artifact_id("row_empathy_map_0", ArtifactType.EMPATHY_MAP, 0), project_id="project_001")
    finish(backend, "row_empathy_map_0", [(ArtifactType.EMPATHY_MAP, em)])
    return em


async def test_customer_scenario_generator_links_to_its_empathy_map_and_sees_the_brief():
    backend = FakeBackend()
    em = ready_empathy(backend)
    llm = FakeLLM([SCENARIO])
    result = await run_row(backend, "row_customer_scenario_0", llm)
    assert result.status == "success"
    (record,) = result.artifacts
    scenario = parse_artifact(record)
    assert scenario.empathy_map_id == em.id
    assert record.id == derive_artifact_id("row_customer_scenario_0", ArtifactType.CUSTOMER_SCENARIO, 0)
    user = llm.calls[0]["messages"][1]["content"]
    assert "Farm produce delivery" in user  # the Brief
    assert "Olena" in user and em.id not in user  # the empathy map, without its system ids
    assert llm.calls[0]["schema"] is GENERATION_CONTRACTS[Stage.CUSTOMER_SCENARIO][0]


async def test_ideation_generator_links_to_its_empathy_map_and_sees_the_brief():
    backend = FakeBackend()
    em = ready_empathy(backend)
    llm = FakeLLM([IDEATION])
    result = await run_row(backend, "row_ideation_0", llm)
    assert result.status == "success"
    (record,) = result.artifacts
    ideation = parse_artifact(record)
    assert ideation.empathy_map_id == em.id and record.id == derive_artifact_id("row_ideation_0", ArtifactType.IDEATION, 0)
    user = llm.calls[0]["messages"][1]["content"]
    assert "Farm produce delivery" in user and "Olena" in user and em.id not in user
    assert result.consistency is not None and result.consistency.violations == []


async def test_persona_check_is_wired_through_the_judge_after_customer_scenario():
    backend = FakeBackend()
    em = ready_empathy(backend)
    finding = json.dumps({"score": 2, "violations": [
        {"rule_id": "empathy_map_customer_scenario_persona_consistency", "severity": "error",
         "message": "Scenario contradicts the pains.", "artifact_ids": [em.id]}]})
    judge_model = FakeJudgeModel([finding])
    result = await run_row(backend, "row_customer_scenario_0", FakeLLM([SCENARIO]), judge_model)
    assert len(judge_model.calls) == 1
    payload = json.loads(judge_model.calls[0]["user"])
    assert list(payload) == ["empathy_map", "customer_scenario"]
    assert payload["empathy_map"]["id"] == em.id and payload["customer_scenario"]["situation_narrative"].startswith("Olena")
    report = result.consistency
    assert report is not None and report.score == 2
    assert [v.severity for v in report.violations] == ["warning"]  # advisory
    assert backend.rows["row_customer_scenario_0"].status == StageStatus.DONE  # be does not block on a warning


@pytest.mark.parametrize("row_id", ["row_brief_0", "row_empathy_map_0", "row_ideation_0"])
async def test_the_judge_does_not_run_for_the_other_stages(row_id):
    backend = FakeBackend()
    judge_model = FakeJudgeModel([NO_FINDINGS])
    if row_id == "row_brief_0":
        llm = FakeLLM([brief_with(["Urban parents"])])
    else:
        ready_empathy(backend) if row_id == "row_ideation_0" else finish(backend, "row_brief_0", [(ArtifactType.BRIEF, brief_with(["Urban parents"]))])
        llm = FakeLLM([IDEATION if row_id == "row_ideation_0" else empathy_generated()])
    await run_row(backend, row_id, llm, judge_model)
    assert judge_model.calls == []


async def test_a_judge_outage_does_not_fail_the_scenario():
    backend = FakeBackend()
    ready_empathy(backend)
    from bizstruct_ml.judge.base import JudgeModelError

    result = await run_row(backend, "row_customer_scenario_0", FakeLLM([SCENARIO]), FakeJudgeModel([JudgeModelError("down")]))
    assert result.status == "success"
    assert [v.rule_id for v in result.consistency.violations] == ["judge_unavailable:empathy_map_customer_scenario_persona_consistency"]


def test_prompts_carry_the_field_descriptions_of_the_contract():
    from bizstruct_ml.llm.prompts import brief, customer_scenario, empathy_map, ideation

    for module, contract in (
        (brief, GENERATION_CONTRACTS[Stage.BRIEF][0]),
        (empathy_map, EmpathyMapGenerated),
        (customer_scenario, GENERATION_CONTRACTS[Stage.CUSTOMER_SCENARIO][0]),
        (ideation, GENERATION_CONTRACTS[Stage.IDEATION][0]),
    ):
        guide = field_guide(contract)
        assert guide in module.SYSTEM
        for name, prop in contract.model_json_schema()["properties"].items():
            assert f"- {name} (" in guide
            if "description" in prop:
                assert prop["description"] in guide


def test_field_guide_expands_nested_objects_and_enums():
    guide = field_guide(IdeationGenerated)
    assert "- epicenter.tags (list of one of" in guide and '"multiple_epicenter"' in guide
    assert "- epicenter.rationale (string)" in guide
    assert "(list of string (min 1, max 10 items))" in guide


async def test_language_comes_from_the_snapshot_not_the_message():
    backend = FakeBackend(language="uk")
    llm = FakeLLM([brief_with(["Міські батьки"])])
    message = backend.message_for("row_brief_0").model_copy(update={"language": "en"})
    from bizstruct_ml.strategies.pipeline import handle_message

    await handle_message(message, backend.client(), runner(llm))
    assert "Ukrainian" in llm.calls[0]["messages"][0]["content"]
