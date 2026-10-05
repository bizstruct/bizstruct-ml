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
