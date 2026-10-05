"""ConsistencyJudge: prompt, parsing, retries, severity cap."""
import json

import pytest
from bizstruct_domain.schemas import JudgeCheck, RuleInput, Stage, StageArity

from bizstruct_ml.judge import base
from bizstruct_ml.judge.base import (
    OUTPUT_FORMAT,
    ConsistencyJudge,
    JudgeModel,
    JudgeModelError,
    JudgeUnavailable,
)
from bizstruct_ml.judge.fake import FakeJudgeModel
from bizstruct_domain.schemas import EmpathyMap
from tests.support.fakes import empathy_generated

EM = EmpathyMap.from_generated(empathy_generated(), id="em1", project_id="p")
INPUTS = [EM, [], None]

CHECK = JudgeCheck(
    id="demo_check",
    inputs=(
        RuleInput(stage=Stage.EMPATHY_MAP, arity=StageArity.ONE),
        RuleInput(stage=Stage.CUSTOMER_SCENARIO, arity=StageArity.MANY),
        RuleInput(stage=Stage.BUSINESS_CASE, arity=StageArity.ONE, optional=True),
    ),
    instruction="Check that the scenario does not contradict the empathy map.",
)

VALID = json.dumps(
    {
        "score": 3,
        "violations": [
            {"rule_id": "demo_check", "severity": "error", "message": "Contradiction.", "artifact_ids": ["em1"]}
        ],
    }
)


def judge(*replies, **kwargs) -> tuple[ConsistencyJudge, FakeJudgeModel]:
    model = FakeJudgeModel(replies)
    return ConsistencyJudge(model, retry_wait=0, **kwargs), model


def test_abstract_judge_model_cannot_be_instantiated():
    with pytest.raises(TypeError):
        JudgeModel()  # type: ignore[abstract]


def test_prompt_golden():
    system, user = ConsistencyJudge.build_prompts(CHECK, [empathy_generated(), [], None])
    assert system == f'{CHECK.instruction}\n\n{OUTPUT_FORMAT}\n\nThe id of this check is "demo_check".'
    payload = json.loads(user)
    # labelled by RuleInput stage, in input order; absent optional ONE is null, MANY is a list
    assert list(payload) == ["empathy_map", "customer_scenario", "business_case"]
    assert payload["empathy_map"]["persona_name"] == "Olena"
    assert payload["customer_scenario"] == []
    assert payload["business_case"] is None
    assert user == json.dumps(payload, ensure_ascii=False, indent=2)


def test_output_format_names_the_report_fields():
    for fragment in ("valid JSON only", "score", "violations", "rule_id", "severity", "message", "artifact_ids"):
        assert fragment in OUTPUT_FORMAT
    assert "from 1 " in OUTPUT_FORMAT and "to 5" in OUTPUT_FORMAT
    assert "never invent an id" in OUTPUT_FORMAT


def test_prompt_rejects_wrong_input_count():
    with pytest.raises(ValueError):
        ConsistencyJudge.build_prompts(CHECK, [empathy_generated()])


async def test_parses_valid_json_and_sends_temperature_zero():
    j, model = judge(VALID)
    report = await j.evaluate(CHECK, INPUTS)
    assert report.score == 3
    assert report.violations[0].message == "Contradiction."
    assert model.calls[0]["temperature"] == 0.0


async def test_strips_markdown_fence():
    j, _ = judge(f"```json\n{VALID}\n```")
    assert (await j.evaluate(CHECK, INPUTS)).score == 3


async def test_garbage_is_retried_then_raises_judge_unavailable():
    j, model = judge("not json", '{"score": 9, "violations": []}', "still not json", max_attempts=3)
    with pytest.raises(JudgeUnavailable):
        await j.evaluate(CHECK, INPUTS)
    assert len(model.calls) == 3


async def test_recovers_when_a_retry_is_valid():
    j, model = judge("garbage", JudgeModelError("boom"), VALID)
    report = await j.evaluate(CHECK, INPUTS)
    assert report.score == 3
    assert len(model.calls) == 3


async def test_provider_errors_exhaust_into_judge_unavailable():
    j, model = judge(JudgeModelError("down"), max_attempts=2)
    with pytest.raises(JudgeUnavailable):
        await j.evaluate(CHECK, INPUTS)
    assert len(model.calls) == 2


async def test_severity_is_capped_at_warning():
    j, _ = judge(VALID)
    report = await j.evaluate(CHECK, INPUTS)
    assert [v.severity for v in report.violations] == ["warning"]
    assert report.score == 3  # the score is the judge's own


async def test_errors_survive_when_judge_is_blocking(monkeypatch):
    monkeypatch.setattr(base, "JUDGE_BLOCKING", True)
    j, _ = judge(VALID)
    report = await j.evaluate(CHECK, INPUTS)
    assert [v.severity for v in report.violations] == ["error"]


def test_judge_is_not_blocking_by_default():
    assert base.JUDGE_BLOCKING is False


def reply(*violations: dict, score: int = 3) -> str:
    return json.dumps({"score": score, "violations": list(violations)})


def violation(artifact_ids: list[str], rule_id: str = "demo_check") -> dict:
    return {"rule_id": rule_id, "severity": "warning", "message": "m", "artifact_ids": artifact_ids}


async def test_rule_id_is_forced_to_the_check_id():
    j, _ = judge(reply(violation(["em1"], rule_id="whatever_the_model_said")))
    report = await j.evaluate(CHECK, INPUTS)
    assert [v.rule_id for v in report.violations] == ["demo_check"]


async def test_cited_ids_that_are_not_inputs_are_dropped_and_known_ones_kept_in_order():
    j, _ = judge(reply(violation(["ghost", "em1", "phantom"])))
    (v,) = (await j.evaluate(CHECK, INPUTS)).violations
    assert v.artifact_ids == ["em1"]


async def test_a_violation_citing_only_unknown_ids_falls_back_to_all_input_ids():
    scenario_like = {"id": "cs1", "situation_narrative": "x"}
    j, _ = judge(reply(violation(["ghost"])))
    (v,) = (await j.evaluate(CHECK, [EM, [scenario_like], None])).violations
    assert v.artifact_ids == ["em1", "cs1"]  # ids of every provided input that has one, in input order


async def test_a_violation_with_no_citable_input_is_dropped_but_the_score_stays():
    j, _ = judge(reply(violation(["ghost"]), violation(["also ghost"]), score=2))
    report = await j.evaluate(CHECK, [{"no_id": 1}, [], None])
    assert report.violations == [] and report.score == 2


async def test_dropped_violations_are_logged(capsys):
    j, _ = judge(reply(violation(["ghost"])))
    await j.evaluate(CHECK, [{"no_id": 1}, [], None])
    assert "judge_violation_dropped" in capsys.readouterr().out


async def test_a_clean_report_stays_clean_when_the_inputs_have_no_ids():
    j, _ = judge(reply())
    assert (await j.evaluate(CHECK, [{"no_id": 1}, [], None])).violations == []


async def test_ids_of_list_inputs_count_as_provided():
    j, _ = judge(reply(violation(["cs2"])))
    (v,) = (await j.evaluate(CHECK, [EM, [{"id": "cs1"}, {"id": "cs2"}], None])).violations
    assert v.artifact_ids == ["cs2"]
