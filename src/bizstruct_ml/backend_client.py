import httpx
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from bizstruct_ml.config import settings
from bizstruct_ml.schemas.messages import HookPayload
from bizstruct_ml.schemas.project import ProjectState


class ProjectNotFoundError(Exception):
    pass


class BackendUnavailableError(Exception):
    pass


class HookFailedError(Exception):
    """Base for any hook failure. Catch this for "something went wrong";
    catch the subclasses below when the distinction between retrying and
    giving up matters (it always should, at the call site)."""


class HookUnavailableError(HookFailedError):
    """Backend unreachable or erroring transiently — 5xx, timeout, network
    error. Worth retrying: the same request might succeed next time."""


class HookRejectedError(HookFailedError):
    """Backend rejected the payload outright — any 4xx, including 422
    (schema violation) and 404 (project gone). NOT worth retrying: the same
    request will fail the same way every time. Carries the status code and
    response body so the caller can dead-letter with a useful reason."""

    def __init__(self, status_code: int, body: str, message: str) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.body = body


class BackendClient:
    def __init__(self) -> None:
        self._client = httpx.AsyncClient(
            base_url=settings.backend_base_url,
            headers={"X-API-Key": settings.backend_api_key},
            timeout=10.0,
        )

    async def get_project(self, project_id: str) -> ProjectState:
        try:
            response = await self._client.get(f"/api/internal/projects/{project_id}")
        except httpx.TimeoutException as e:
            raise BackendUnavailableError(f"Timeout fetching project {project_id}") from e
        except httpx.RequestError as e:
            raise BackendUnavailableError(f"Request error fetching project {project_id}") from e

        if response.status_code == 404:
            raise ProjectNotFoundError(f"Project {project_id} not found")
        if response.status_code >= 500:
            raise BackendUnavailableError(f"Backend returned {response.status_code} for project {project_id}")

        response.raise_for_status()
        return ProjectState.model_validate(response.json())

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(min=1, max=10),
        # Only retry transient failures. A HookRejectedError (4xx) is not a
        # HookUnavailableError, so tenacity's predicate doesn't match it and
        # it propagates on the first attempt — retrying a rejected payload
        # would just get the same rejection three times over.
        retry=retry_if_exception_type(HookUnavailableError),
        reraise=True,
    )
    async def send_hook(self, payload: HookPayload) -> None:
        try:
            response = await self._client.post(
                "/api/internal/hook",
                json=payload.model_dump(mode="json"),
            )
        except httpx.TimeoutException as e:
            raise HookUnavailableError(f"Timeout sending hook for {payload.project_id}/{payload.block}") from e
        except httpx.RequestError as e:
            raise HookUnavailableError(f"Request error sending hook: {e}") from e

        if 200 <= response.status_code < 300:
            return

        if response.status_code >= 500:
            raise HookUnavailableError(
                f"Hook returned {response.status_code} for {payload.project_id}/{payload.block}"
            )

        # Any other 4xx (422 schema violation, 404 project gone, 400, ...):
        # the backend has definitively rejected this request. Retrying it
        # unchanged will not help.
        raise HookRejectedError(
            status_code=response.status_code,
            body=response.text,
            message=(
                f"Hook rejected with {response.status_code} for "
                f"{payload.project_id}/{payload.block}: {response.text}"
            ),
        )

    async def aclose(self) -> None:
        await self._client.aclose()
