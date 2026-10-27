"""AzureFoundryChatJudge request shape against a mock transport."""
import json

import httpx
import pytest

from bizstruct_ml.judge.azure_foundry import AzureFoundryChatJudge
from bizstruct_ml.judge.base import JudgeModelError

ENDPOINT = "https://judge.example.test/openai/v1"


def completion(content: str | None) -> dict:
    return {
        "id": "c1",
        "object": "chat.completion",
        "created": 0,
        "model": "mistral-large-3",
        "choices": [{"index": 0, "finish_reason": "stop", "message": {"role": "assistant", "content": content}}],
    }


def make(handler, **kwargs) -> AzureFoundryChatJudge:
    return AzureFoundryChatJudge(
        endpoint=ENDPOINT,
        api_key="judge-key",
        deployment="mistral-large-3",
        http_client=httpx.AsyncClient(transport=httpx.MockTransport(handler)),
        **kwargs,
    )


def capture():
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, json=completion('{"score": 5, "violations": []}'))

    return seen, handler


async def test_request_shape():
    seen, handler = capture()
    reply = await make(handler).complete_json(system="SYS", user="USR", temperature=0.0)
    assert reply == '{"score": 5, "violations": []}'

    request = seen[0]
    assert request.url == httpx.URL(f"{ENDPOINT}/chat/completions")
    assert request.headers["api-key"] == "judge-key"
    assert request.headers["authorization"] == "Bearer judge-key"
    body = json.loads(request.content)
    assert body["model"] == "mistral-large-3"
    assert body["temperature"] == 0.0
    assert body["messages"] == [{"role": "system", "content": "SYS"}, {"role": "user", "content": "USR"}]
    assert "response_format" not in body
    assert "max_tokens" not in body


async def test_json_mode_and_max_tokens_are_opt_in():
    seen, handler = capture()
    await make(handler, json_mode=True, max_tokens=800).complete_json(system="s", user="u")
    body = json.loads(seen[0].content)
    assert body["response_format"] == {"type": "json_object"}
    assert body["max_tokens"] == 800


async def test_api_error_becomes_judge_model_error():
    judge = make(lambda request: httpx.Response(500, json={"error": {"message": "boom"}}))
    with pytest.raises(JudgeModelError):
        await judge.complete_json(system="s", user="u")


async def test_timeout_becomes_judge_model_error():
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("slow", request=request)

    with pytest.raises(JudgeModelError):
        await make(handler).complete_json(system="s", user="u")


async def test_empty_reply_is_an_error():
    judge = make(lambda request: httpx.Response(200, json=completion(None)))
    with pytest.raises(JudgeModelError):
        await judge.complete_json(system="s", user="u")


def rate_limited_then_ok(retry_after: str | None, failures: int):
    calls: list[int] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(1)
        if len(calls) <= failures:
            headers = {"retry-after": retry_after} if retry_after is not None else {}
            return httpx.Response(429, headers=headers, json={"error": {"message": "slow down"}})
        return httpx.Response(200, json=completion('{"score": 5, "violations": []}'))

    return calls, handler


async def test_429_backs_off_for_retry_after_and_then_succeeds():
    calls, handler = rate_limited_then_ok("7", failures=2)
    slept: list[float] = []

    async def sleep(seconds: float) -> None:
        slept.append(seconds)

    reply = await make(handler, sleep=sleep).complete_json(system="s", user="u")
    assert reply == '{"score": 5, "violations": []}'
    assert len(calls) == 3
    assert slept == [7.0, 7.0]


async def test_429_without_retry_after_uses_exponential_backoff():
    _, handler = rate_limited_then_ok(None, failures=2)
    slept: list[float] = []

    async def sleep(seconds: float) -> None:
        slept.append(seconds)

    await make(handler, sleep=sleep).complete_json(system="s", user="u")
    assert slept == [2.0, 4.0]


async def test_retry_after_is_capped():
    _, handler = rate_limited_then_ok("3600", failures=1)
    slept: list[float] = []

    async def sleep(seconds: float) -> None:
        slept.append(seconds)

    await make(handler, sleep=sleep, max_retry_after_seconds=30.0).complete_json(system="s", user="u")
    assert slept == [30.0]


async def test_persistent_429_ends_as_judge_model_error():
    calls, handler = rate_limited_then_ok("1", failures=99)

    async def sleep(seconds: float) -> None:
        pass

    with pytest.raises(JudgeModelError):
        await make(handler, sleep=sleep, rate_limit_retries=3).complete_json(system="s", user="u")
    assert len(calls) == 4  # the first try plus three retries
