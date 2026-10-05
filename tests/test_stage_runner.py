"""StageRunner: generation, id derivation, the retry-inside-message loop, judge handling."""
import json

import pytest
from bizstruct_domain.schemas import (
    ArtifactType,
    ConsistencyRule,
    ConsistencyViolation,
    EmpathyMap,
    JudgeCheck,
    RuleInput,
    Stage,
    StageArity,
    StageErrorCode,
    derive_artifact_id,
    parse_artifact,
)

from bizstruct_ml.core.stage_runner import MAX_CONSISTENCY_RETRIES, StageRunner
from bizstruct_ml.judge.base import ConsistencyJudge, JudgeModelError
from bizstruct_ml.judge.fake import FakeJudgeModel
from bizstruct_ml.llm.client import LLMError
from tests.support.fakes import (
    EmpathyMapTestGenerator,
    FakeLLM,
    brief_row,
    empathy_generated,
    empathy_row,
    snapshot_for,
)

EM_INPUT = (RuleInput(stage=Stage.EMPATHY_MAP, arity=StageArity.ONE),)


def rule(severity: str = "error", bad_name: str = "Bad") -> ConsistencyRule:
    """Violates when the persona is called `bad_name`."""

    def check(em: EmpathyMap) -> list[ConsistencyViolation]:
        if em.persona_name != bad_name:
            return []
        return [ConsistencyViolation(rule_id="no_bad", severity=severity, message="Persona must not be Bad.", artifact_ids=[em.id])]

    return ConsistencyRule("no_bad", EM_INPUT, check)


JUDGE_CHECK = JudgeCheck(id="judge_demo", inputs=EM_INPUT, instruction="Check the persona.")
JUDGE_REPLY = json.dumps(
    {"score": 3, "violations": [{"rule_id": "judge_demo", "severity": "error", "message": "Odd.", "artifact_ids": ["x"]}]}
)


def runner(llm: FakeLLM, judge_model: FakeJudgeModel | None = None, rules=(), checks=()) -> StageRunner:
    return StageRunner(
        {Stage.EMPATHY_MAP: EmpathyMapTestGenerator()},
        llm,
        ConsistencyJudge(judge_model or FakeJudgeModel(), retry_wait=0),
        rules=rules,
        checks=checks,
        retry_wait=0,
    )


async def run(r: StageRunner):
    row = empathy_row()
    return await r.run(row, snapshot_for(row, brief_row()), "en")


async def test_success_converts_with_derived_ids_and_valid_artifacts():
    outcome = await run(runner(FakeLLM([empathy_generated()])))
    assert outcome.success
    (record,) = outcome.artifacts
    assert record.type == ArtifactType.EMPATHY_MAP
    assert record.id == derive_artifact_id("row_em_0", ArtifactType.EMPATHY_MAP, 0)
    assert parse_artifact(record).persona_name == "Olena"
    assert outcome.consistency is not None and outcome.consistency.score == 5


async def test_the_llm_is_asked_for_the_stage_contract():
    llm = FakeLLM([empathy_generated()])
    await run(runner(llm))
    from bizstruct_domain.schemas import GENERATION_CONTRACTS

    assert llm.calls[0]["schema"] is GENERATION_CONTRACTS[Stage.EMPATHY_MAP][0]


async def test_regenerating_the_same_row_yields_the_same_ids():
    first = await run(runner(FakeLLM([empathy_generated("A")])))
    second = await run(runner(FakeLLM([empathy_generated("B")])))
    assert [a.id for a in first.artifacts] == [a.id for a in second.artifacts]
    assert first.artifacts[0].data["persona_name"] != second.artifacts[0].data["persona_name"]


async def test_an_error_violation_regenerates_with_the_messages_in_the_prompt():
    llm = FakeLLM([empathy_generated("Bad"), empathy_generated("Good")])
    outcome = await run(runner(llm, rules=[rule()]))
    assert outcome.success and outcome.consistency_retries == 1
    assert outcome.artifacts[0].data["persona_name"] == "Good"
    assert len(llm.calls) == 2
    assert not any("Persona must not be Bad." in m["content"] for m in llm.calls[0]["messages"])
    assert "Persona must not be Bad." in llm.calls[1]["messages"][-1]["content"]
    assert outcome.consistency is not None and outcome.consistency.violations == []


async def test_retries_stop_after_two_and_the_final_report_keeps_the_errors():
    llm = FakeLLM([empathy_generated("Bad")])
    outcome = await run(runner(llm, rules=[rule()]))
    assert MAX_CONSISTENCY_RETRIES == 2
    assert len(llm.calls) == 3  # first attempt + 2 retries
    assert outcome.success and outcome.consistency_retries == 2
    assert outcome.consistency is not None and outcome.consistency.has_errors
    assert outcome.consistency.score == 4


async def test_warnings_never_retry():
    llm = FakeLLM([empathy_generated("Bad")])
    outcome = await run(runner(llm, rules=[rule(severity="warning")]))
    assert len(llm.calls) == 1 and outcome.consistency_retries == 0
    assert outcome.consistency is not None
    assert [v.severity for v in outcome.consistency.violations] == ["warning"]
    assert outcome.consistency.score == 5


async def test_judge_findings_never_trigger_a_retry_and_are_capped_at_warning():
    llm = FakeLLM([empathy_generated()])
    judge_model = FakeJudgeModel([JUDGE_REPLY])
    outcome = await run(runner(llm, judge_model, checks=[JUDGE_CHECK]))
    assert len(llm.calls) == 1 and len(judge_model.calls) == 1
    assert outcome.consistency is not None
    assert [v.severity for v in outcome.consistency.violations] == ["warning"]
    assert outcome.consistency.score == 3  # min(judge 3, deterministic 5)


async def test_the_judge_runs_once_on_the_final_artifacts_not_per_retry():
    llm = FakeLLM([empathy_generated("Bad"), empathy_generated("Good")])
    judge_model = FakeJudgeModel([JUDGE_REPLY])
    await run(runner(llm, judge_model, rules=[rule()], checks=[JUDGE_CHECK]))
    assert len(judge_model.calls) == 1
    assert "Good" in judge_model.calls[0]["user"] and "Bad" not in judge_model.calls[0]["user"]


async def test_an_unavailable_judge_is_a_warning_and_the_stage_still_succeeds():
    llm = FakeLLM([empathy_generated()])
    judge_model = FakeJudgeModel([JudgeModelError("down")])
    outcome = await run(runner(llm, judge_model, checks=[JUDGE_CHECK]))
    assert outcome.success
    (v,) = outcome.consistency.violations  # type: ignore[union-attr]
    assert v.rule_id == "judge_unavailable:judge_demo"
    assert v.severity == "warning"
    assert v.artifact_ids == [outcome.artifacts[0].id]
    assert outcome.consistency.score == 5  # type: ignore[union-attr]


async def test_a_failing_generator_call_fails_the_row_after_the_llm_retries():
    llm = FakeLLM([LLMError("rate limited")])
    outcome = await run(runner(llm))
    assert not outcome.success and outcome.artifacts == []
    assert outcome.failure is not None and outcome.failure.code == StageErrorCode.GENERATION_FAILED
    assert "rate limited" in outcome.failure.message
    assert len(llm.calls) == 3


async def test_content_that_does_not_fit_the_system_fields_fails_the_row():
    class BrokenGenerator(EmpathyMapTestGenerator):
        def to_artifacts(self, generated, ctx):
            return [(ArtifactType.EMPATHY_MAP, EmpathyMap.from_generated(generated, id="x"))]  # project_id missing

    r = StageRunner({Stage.EMPATHY_MAP: BrokenGenerator()}, FakeLLM([empathy_generated()]), ConsistencyJudge(FakeJudgeModel()), retry_wait=0)
    outcome = await run(r)
    assert not outcome.success and outcome.failure is not None


async def test_a_missing_ref_row_fails_the_row_without_calling_the_llm():
    llm = FakeLLM([empathy_generated()])
    row = empathy_row()
    outcome = await runner(llm).run(row, snapshot_for(row), "en")  # no brief row in the snapshot
    assert not outcome.success and "context" in outcome.failure.message  # type: ignore[union-attr]
    assert llm.calls == []


def test_registering_a_generator_for_a_stage_without_a_single_contract_is_refused():
    class CycleGenerator(EmpathyMapTestGenerator):
        stage = Stage.SWOT_ERRC_CYCLE

    with pytest.raises(ValueError, match="exactly one generation contract"):
        StageRunner({Stage.SWOT_ERRC_CYCLE: CycleGenerator()}, FakeLLM([]), ConsistencyJudge(FakeJudgeModel()))
    with pytest.raises(ValueError):
        StageRunner({Stage.TEAM_INFO: CycleGenerator()}, FakeLLM([]), ConsistencyJudge(FakeJudgeModel()))


async def test_a_conversion_validation_error_is_retried_with_a_new_llm_call():
    class FlakyGenerator(EmpathyMapTestGenerator):
        calls = 0

        def to_artifacts(self, generated, ctx):
            FlakyGenerator.calls += 1
            if FlakyGenerator.calls == 1:
                EmpathyMap.from_generated(generated, id="x")  # raises ValidationError: project_id missing
            return super().to_artifacts(generated, ctx)

    llm = FakeLLM([empathy_generated()])
    r = StageRunner({Stage.EMPATHY_MAP: FlakyGenerator()}, llm, ConsistencyJudge(FakeJudgeModel()), retry_wait=0)
    outcome = await run(r)
    assert outcome.success and len(llm.calls) == 2


async def test_an_artifact_that_be_would_reject_fails_the_row_here():
    class InvalidGenerator(EmpathyMapTestGenerator):
        def to_artifacts(self, generated, ctx):
            # built without validation: the data no longer satisfies the persisted model
            return [(ArtifactType.EMPATHY_MAP, EmpathyMap.model_construct(id="e1", project_id="p", persona_name="x"))]

    llm = FakeLLM([empathy_generated()])
    r = StageRunner({Stage.EMPATHY_MAP: InvalidGenerator()}, llm, ConsistencyJudge(FakeJudgeModel()), retry_wait=0)
    outcome = await run(r)
    assert not outcome.success and outcome.artifacts == []


async def test_a_generator_that_returns_no_artifacts_fails_the_row():
    class EmptyGenerator(EmpathyMapTestGenerator):
        def to_artifacts(self, generated, ctx):
            return []

    r = StageRunner({Stage.EMPATHY_MAP: EmptyGenerator()}, FakeLLM([empathy_generated()]), ConsistencyJudge(FakeJudgeModel()), retry_wait=0)
    outcome = await run(r)
    assert not outcome.success and "no artifacts" in outcome.failure.message  # type: ignore[union-attr]
