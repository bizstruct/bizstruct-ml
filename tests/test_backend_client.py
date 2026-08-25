"""BackendClient.send_hook — retry only on transient (5xx/timeout) failures."""
import httpx
import pytest

from bizstruct_ml.backend_client import BackendClient, HookRejectedError, HookUnavailableError
from bizstruct_ml.schemas.messages import HookPayload
from uuid import uuid4


def _hook() -> HookPayload:
    return HookPayload(project_id=uuid4(), block="architecture", status="success", data={"a": 1})


class _FakeResponse:
    def __init__(self, status_code: int, text: str = "") -> None:
        self.status_code = status_code
        self.text = text


@pytest.mark.asyncio
async def test_422_raises_hook_rejected_after_a_single_attempt(monkeypatch):
    client = BackendClient()
    calls = {"n": 0}

    async def fake_post(*args, **kwargs):
        calls["n"] += 1
        return _FakeResponse(422, '{"detail": "bad schema"}')

    monkeypatch.setattr(client._client, "post", fake_post)

    with pytest.raises(HookRejectedError) as exc_info:
        await client.send_hook(_hook())

    assert calls["n"] == 1  # no retry
    assert exc_info.value.status_code == 422


@pytest.mark.asyncio
async def test_404_raises_hook_rejected_after_a_single_attempt(monkeypatch):
    client = BackendClient()
    calls = {"n": 0}

    async def fake_post(*args, **kwargs):
        calls["n"] += 1
        return _FakeResponse(404, "not found")

    monkeypatch.setattr(client._client, "post", fake_post)

    with pytest.raises(HookRejectedError) as exc_info:
        await client.send_hook(_hook())

    assert calls["n"] == 1
    assert exc_info.value.status_code == 404


@pytest.mark.asyncio
async def test_500_retries_up_to_three_attempts_then_raises_unavailable(monkeypatch):
    client = BackendClient()
    calls = {"n": 0}

    async def fake_post(*args, **kwargs):
        calls["n"] += 1
        return _FakeResponse(500, "server error")

    monkeypatch.setattr(client._client, "post", fake_post)

    with pytest.raises(HookUnavailableError):
        await client.send_hook(_hook())

    assert calls["n"] == 3


@pytest.mark.asyncio
async def test_timeout_raises_hook_unavailable(monkeypatch):
    client = BackendClient()

    async def fake_post(*args, **kwargs):
        raise httpx.TimeoutException("timed out")

    monkeypatch.setattr(client._client, "post", fake_post)

    with pytest.raises(HookUnavailableError):
        await client.send_hook(_hook())


@pytest.mark.asyncio
async def test_2xx_does_not_raise(monkeypatch):
    client = BackendClient()

    async def fake_post(*args, **kwargs):
        return _FakeResponse(200, "")

    monkeypatch.setattr(client._client, "post", fake_post)

    await client.send_hook(_hook())  # must not raise
