"""Finish reasons: the client wraps them as LLMError subclasses, the runner retries by kind
and records the finish reason in the trace."""
import pytest
from bizstruct_domain.schemas import Stage
from openai import ContentFilterFinishReasonError, LengthFinishReasonError
from openai.types.chat import ChatCompletion

from bizstruct_ml.core import stage_runner
from bizstruct_ml.core.stage_runner import StageRunner
from bizstruct_ml.judge.base import ConsistencyJudge
from bizstruct_ml.judge.fake import FakeJudgeModel
from bizstruct_ml.llm.client import LLMClient, LLMContentFilterError, LLMError, LLMLengthError
from bizstruct_ml.observability import tracing
from tests.support.fakes import EmpathyMapTestGenerator, FakeLLM, brief_row, empathy_generated, empathy_row, snapshot_for
from tests.test_tracing import _FakeClient


def completion(finish_reason: str, parsed=None) -> ChatCompletion:
    return ChatCompletion.model_validate(
        {
            "id": "c1", "object": "chat.completion", "created": 0, "model": "m",
            "choices": [{"index": 0, "finish_reason": finish_reason, "message": {"role": "assistant", "content": "x"}}],
            "usage": {"prompt_tokens": 10, "completion_tokens": 7, "total_tokens": 17},
        }
    )


class _Completions:
    def __init__(self, outcome):
        self.outcome = outcome

    async def parse(self, **_kwargs):
        if isinstance(self.outcome, Exception):
            raise self.outcome
        return self.outcome


def client_with(outcome) -> LLMClient:
    client = object.__new__(LLMClient)  # no real API client: only the call path is under test
    client._model = "m"
    client.last_usage = None
    client.last_finish_reason = None
    beta = type("B", (), {"chat": type("C", (), {"completions": _Completions(outcome)})()})()
    client._client = type("X", (), {"beta": beta})()
    return client


async def test_client_wraps_length_and_keeps_usage_and_reason():
    client = client_with(LengthFinishReasonError(completion=completion("length")))
    with pytest.raises(LLMLengthError, match="finish_reason=length"):
        await client.generate_structured([], object)
    assert client.last_finish_reason == "length"
    assert client.last_usage == {"input": 10, "output": 7, "total": 17}


async def test_client_wraps_content_filter():
    client = client_with(ContentFilterFinishReasonError())
    with pytest.raises(LLMContentFilterError, match="finish_reason=content_filter"):
        await client.generate_structured([], object)
    assert client.last_finish_reason == "content_filter"
    assert issubclass(LLMContentFilterError, LLMError) and issubclass(LLMLengthError, LLMError)


def runner(llm: FakeLLM) -> StageRunner:
    return StageRunner(
        {Stage.EMPATHY_MAP: EmpathyMapTestGenerator()}, llm, ConsistencyJudge(FakeJudgeModel(), retry_wait=0), retry_wait=0
    )


async def run(r: StageRunner):
    row = empathy_row()
    return await r.run(row, snapshot_for(row, brief_row()), "en")


async def test_content_filter_is_retried_like_other_errors():
    llm = FakeLLM([LLMContentFilterError("blocked"), empathy_generated()])
    outcome = await run(runner(llm))
    assert outcome.success and len(llm.calls) == 2


async def test_content_filter_every_time_fails_after_the_normal_retries_and_names_the_reason():
    llm = FakeLLM([LLMContentFilterError("LLM output was blocked (finish_reason=content_filter)")])
    outcome = await run(runner(llm))
    assert not outcome.success and "finish_reason=content_filter" in outcome.failure.message
    assert len(llm.calls) == 3  # settings.llm_max_retries + 1


async def test_length_is_retried_once_then_succeeds():
    llm = FakeLLM([LLMLengthError("cut"), empathy_generated()])
    outcome = await run(runner(llm))
    assert outcome.success and len(llm.calls) == 2


async def test_length_twice_fails_the_row_without_a_third_call_and_names_the_reason():
    llm = FakeLLM([LLMLengthError("cut")])
    outcome = await run(runner(llm))
    assert not outcome.success
    assert "finish_reason=length" in outcome.failure.message
    assert len(llm.calls) == 2  # one retry, not the three attempts other errors get


async def test_length_budget_is_not_spent_by_other_errors():
    llm = FakeLLM([LLMError("boom"), LLMLengthError("cut"), empathy_generated()])
    assert (await run(runner(llm))).success


async def test_length_limit_constant_is_one_retry():
    assert stage_runner.MAX_LENGTH_RETRIES == 1


async def test_finish_reason_is_recorded_on_the_llm_span(monkeypatch):
    fake = _FakeClient()
    monkeypatch.setattr(tracing, "_get_client", lambda: fake)
    llm = FakeLLM([LLMLengthError("cut"), empathy_generated()])
    await run(runner(llm))
    spans = [s for s in fake.spans_created if s.name == "llm_call"]
    reasons = [next(u["metadata"]["finish_reason"] for u in s.updates if "metadata" in u) for s in spans]
    assert reasons == ["length", "stop"]
