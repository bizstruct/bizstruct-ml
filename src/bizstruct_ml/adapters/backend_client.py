"""HTTP client for bizstruct-be (ADR-0011).

Two calls: read the snapshot of a row's closure, post the `StageResult`. Every
failure is mapped to one of the exceptions below so the pipeline strategy can
turn it into a queue disposition without looking at status codes:

| call | response | raises |
|---|---|---|
| GET  | 404 | `ProjectNotFoundError` -> dead-letter |
| GET  | other 4xx | `BackendRejectedError` -> dead-letter |
| GET  | 5xx / timeout / network | `BackendUnavailableError` -> abandon |
| POST | 2xx | (returns) -> complete |
| POST | 409 stale attempt | `HookStaleError` -> complete |
| POST | 404, 422, other 4xx | `HookRejectedError` -> dead-letter |
| POST | 5xx / timeout / network | `HookUnavailableError` (retried first) -> abandon |
"""

import httpx
from bizstruct_domain.schemas import ProjectSnapshot, StageResult

from bizstruct_ml.config import settings
from bizstruct_ml.llm.retry import retry_async

HOOK_PATH = "/api/internal/hook"
HOOK_ATTEMPTS = 3


class ProjectNotFoundError(Exception):
    pass


class BackendUnavailableError(Exception):
    pass


class BackendRejectedError(Exception):
    """GET answered with a 4xx other than 404; retrying will not change it."""

    def __init__(self, status_code: int, body: str, message: str) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.body = body


class HookFailedError(Exception):
    """Base for any hook failure. Catch the subclasses below when the
    distinction between retrying and giving up matters."""


class HookUnavailableError(HookFailedError):
    """Backend unreachable or erroring transiently — 5xx, timeout, network
    error. Worth retrying: the same request might succeed next time."""


class HookStaleError(HookFailedError):
    """409: the attempt is stale or the row is no longer RUNNING. The result
    will never be applied; the message is done."""


class HookRejectedError(HookFailedError):
    """404 (project or row gone), 422 (result fails the schema; be has already
    moved the row to ERROR) or any other 4xx. Not worth retrying. Carries the
    status code and body so the caller can dead-letter with a useful reason."""

    def __init__(self, status_code: int, body: str, message: str) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.body = body


class BackendClient:
    def __init__(
        self,
        *,
        client: httpx.AsyncClient | None = None,
        retry_wait_min: float = 1.0,
        retry_wait_max: float = 10.0,
    ) -> None:
        self._client = client or httpx.AsyncClient(
            base_url=settings.backend_base_url,
            headers={"X-API-Key": settings.backend_api_key},
            timeout=10.0,
        )
        self._retry_wait_min = retry_wait_min
        self._retry_wait_max = retry_wait_max

    async def get_snapshot(self, project_id: str, row_id: str) -> ProjectSnapshot:
        """The project fields plus the row and the closure of its refs."""
        try:
            response = await self._client.get(f"/api/internal/projects/{project_id}", params={"row": row_id})
        except httpx.TimeoutException as e:
            raise BackendUnavailableError(f"Timeout fetching project {project_id}") from e
        except httpx.RequestError as e:
            raise BackendUnavailableError(f"Request error fetching project {project_id}") from e

        if response.status_code == 404:
            raise ProjectNotFoundError(f"Project {project_id} or row {row_id} not found")
        if response.status_code >= 500:
            raise BackendUnavailableError(f"Backend returned {response.status_code} for project {project_id}")
        if response.status_code >= 400:
            raise BackendRejectedError(
                response.status_code,
                response.text,
                f"Backend rejected snapshot request for {project_id} with {response.status_code}",
            )
        return ProjectSnapshot.model_validate(response.json())

    async def send_result(self, result: StageResult) -> None:
        """Post the result. 2xx returns; see the module table for the rest."""

        async def attempt() -> None:
            await self._post_once(result)

        await retry_async(
            attempt,
            retry_on=(HookUnavailableError,),
            attempts=HOOK_ATTEMPTS,
            wait_min=self._retry_wait_min,
            wait_max=self._retry_wait_max,
        )

    async def _post_once(self, result: StageResult) -> None:
        label = f"{result.project_id}/{result.stage_row_id}"
        try:
            response = await self._client.post(HOOK_PATH, json=result.model_dump(mode="json"))
        except httpx.TimeoutException as e:
            raise HookUnavailableError(f"Timeout sending result for {label}") from e
        except httpx.RequestError as e:
            raise HookUnavailableError(f"Request error sending result for {label}: {e}") from e

        if 200 <= response.status_code < 300:
            return
        if response.status_code >= 500:
            raise HookUnavailableError(f"Hook returned {response.status_code} for {label}")
        if response.status_code == 409:
            raise HookStaleError(f"Hook returned 409 for {label}: {response.text}")
        raise HookRejectedError(
            status_code=response.status_code,
            body=response.text,
            message=f"Hook rejected with {response.status_code} for {label}: {response.text}",
        )

    async def aclose(self) -> None:
        await self._client.aclose()
