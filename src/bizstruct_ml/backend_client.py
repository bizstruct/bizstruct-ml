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
    pass


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
        retry=retry_if_exception_type(HookFailedError),
        reraise=True,
    )
    async def send_hook(self, payload: HookPayload) -> None:
        try:
            response = await self._client.post(
                "/api/internal/hook",
                json=payload.model_dump(mode="json"),
            )
        except httpx.TimeoutException as e:
            raise HookFailedError(f"Timeout sending hook for {payload.project_id}/{payload.block}") from e
        except httpx.RequestError as e:
            raise HookFailedError(f"Request error sending hook: {e}") from e

        if not (200 <= response.status_code < 300):
            raise HookFailedError(
                f"Hook returned non-2xx status {response.status_code} for {payload.project_id}/{payload.block}"
            )

    async def aclose(self) -> None:
        await self._client.aclose()
