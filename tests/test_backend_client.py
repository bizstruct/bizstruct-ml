"""BackendClient against a mock transport: request shape and status-code mapping (ADR-0011 Q9)."""
import json

import httpx
import pytest
from bizstruct_domain.schemas import ArtifactRecord, ArtifactType, StageResult

from bizstruct_ml.adapters.backend_client import (
    BackendAuthError,
    BackendClient,
    BackendRejectedError,
    BackendUnavailableError,
    HookRejectedError,
    HookStaleError,
    HookUnavailableError,
    ProjectNotFoundError,
)
from tests.support.fakes import brief_row, empathy_row, snapshot_for


def client_with(handler) -> BackendClient:
    http = httpx.AsyncClient(
        base_url="http://be.test", headers={"X-API-Key": "k"}, transport=httpx.MockTransport(handler)
    )
    return BackendClient(client=http, retry_wait_min=0, retry_wait_max=0)


def result() -> StageResult:
    return StageResult(
        project_id="project_001",
        stage_row_id="row_em_0",
        attempt_id="att1",
        status="success",
        artifacts=[ArtifactRecord(id="a1", type=ArtifactType.TEAM_INFO, data={"id": "a1"})],
    )


async def test_get_snapshot_asks_for_the_row_and_parses_the_snapshot():
    seen: list[httpx.Request] = []
    snap = snapshot_for(empathy_row(), brief_row())

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, content=snap.model_dump_json())

    got = await client_with(handler).get_snapshot("project_001", "row_em_0")
    assert got == snap
    assert seen[0].url.path == "/api/internal/projects/project_001"
    assert seen[0].url.params["row"] == "row_em_0"
    assert seen[0].headers["x-api-key"] == "k"


@pytest.mark.parametrize(
    ("status", "error"),
    [(404, ProjectNotFoundError), (400, BackendRejectedError), (500, BackendUnavailableError), (503, BackendUnavailableError)],
)
async def test_get_snapshot_error_mapping(status, error):
    with pytest.raises(error):
        await client_with(lambda r: httpx.Response(status, text="x")).get_snapshot("p", "r")


async def test_get_snapshot_timeout_is_unavailable():
    def handler(request):
        raise httpx.ReadTimeout("slow", request=request)

    with pytest.raises(BackendUnavailableError):
        await client_with(handler).get_snapshot("p", "r")


async def test_send_result_posts_the_result_to_the_hook_path():
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200)

    await client_with(handler).send_result(result())
    assert seen[0].method == "POST" and seen[0].url.path == "/api/internal/hook"
    body = json.loads(seen[0].content)
    assert body["stage_row_id"] == "row_em_0" and body["attempt_id"] == "att1" and body["status"] == "success"
    assert seen[0].headers["x-api-key"] == "k"


async def test_send_result_accepts_any_2xx():
    await client_with(lambda r: httpx.Response(204)).send_result(result())


@pytest.mark.parametrize(("status", "error"), [(409, HookStaleError), (404, HookRejectedError), (422, HookRejectedError), (400, HookRejectedError)])
async def test_send_result_4xx_is_not_retried(status, error):
    calls = {"n": 0}

    def handler(request):
        calls["n"] += 1
        return httpx.Response(status, text="no")

    with pytest.raises(error) as info:
        await client_with(handler).send_result(result())
    assert calls["n"] == 1
    if error is HookRejectedError:
        assert info.value.status_code == status


async def test_send_result_5xx_retries_three_times_then_is_unavailable():
    calls = {"n": 0}

    def handler(request):
        calls["n"] += 1
        return httpx.Response(502)

    with pytest.raises(HookUnavailableError):
        await client_with(handler).send_result(result())
    assert calls["n"] == 3


async def test_send_result_recovers_when_a_retry_succeeds():
    calls = {"n": 0}

    def handler(request):
        calls["n"] += 1
        return httpx.Response(500 if calls["n"] < 2 else 200)

    await client_with(handler).send_result(result())
    assert calls["n"] == 2


async def test_send_result_timeout_is_unavailable():
    def handler(request):
        raise httpx.ConnectTimeout("slow", request=request)

    with pytest.raises(HookUnavailableError):
        await client_with(handler).send_result(result())


@pytest.mark.parametrize("status", [401, 403])
async def test_a_401_or_403_is_an_auth_error_on_both_calls_and_the_hook_is_not_retried(status):
    calls = {"n": 0}

    def handler(request):
        calls["n"] += 1
        return httpx.Response(status, text="no")

    with pytest.raises(BackendAuthError) as info:
        await client_with(handler).get_snapshot("p", "r")
    assert info.value.status_code == status
    calls["n"] = 0
    with pytest.raises(BackendAuthError):
        await client_with(handler).send_result(result())
    assert calls["n"] == 1
