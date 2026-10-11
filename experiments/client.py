"""The client side shared by the smoke script and the experiment runner: an authenticated session on be's
PUBLIC API, starting a generation and polling a project to its end. Imports no ml worker code."""

import asyncio
import time
from collections.abc import Awaitable, Callable
from typing import Any

import httpx

POLL_TRANSIENT_LIMIT = 5


class SmokeError(Exception):
    """The run cannot continue (login failed, generation refused)."""


# --------------------------------------------------------------------------- session


class Session:
    """An authenticated httpx client that logs in again if the access token expires mid-run."""

    def __init__(self, client: httpx.AsyncClient, email: str, password: str) -> None:
        self.client = client
        self.email = email
        self.password = password
        self.token: str | None = None

    async def ensure_user(self) -> None:
        response = await self.client.post("/api/users/", json={"email": self.email, "password": self.password})
        if response.status_code not in (201, 409):  # 409: the user already exists, which is fine
            raise SmokeError(f"creating the user failed: HTTP {response.status_code}: {response.text[:300]}")

    async def login(self) -> None:
        response = await self.client.post("/api/auth/login", data={"username": self.email, "password": self.password})
        if response.status_code != 200:
            raise SmokeError(f"login failed: HTTP {response.status_code}: {response.text[:300]}")
        self.token = response.json()["access_token"]

    async def request(self, method: str, url: str, **kwargs: Any) -> httpx.Response:
        for attempt in (1, 2):
            headers = {"Authorization": f"Bearer {self.token}"}
            response = await self.client.request(method, url, headers=headers, **kwargs)
            if response.status_code == 401 and attempt == 1:
                await self.login()
                continue
            return response
        raise AssertionError("unreachable")


# --------------------------------------------------------------------------- run


async def create_project(session: Session, *, idea: str, language: str, enabled_optional: list[str]) -> dict[str, Any]:
    body = {"idea": idea, "language": language, "enabledOptional": enabled_optional, "autoApprove": True}
    response = await session.request("POST", "/api/generation", json=body)
    if response.status_code != 201:
        raise SmokeError(f"POST /api/generation was refused: HTTP {response.status_code}: {response.text[:500]}")
    return response.json()


async def poll(
    session: Session,
    project_id: str,
    *,
    timeout: float,
    interval: float,
    sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
    clock: Callable[[], float] = time.monotonic,
    on_progress: Callable[[dict[str, Any]], None] | None = None,
) -> tuple[dict[str, Any] | None, str | None]:
    """Polls until the project is completed or failed. Returns (last project JSON, failure reason or None)."""
    deadline = clock() + timeout
    last: dict[str, Any] | None = None
    transient = 0
    while True:
        try:
            response = await session.request("GET", f"/api/projects/{project_id}")
        except httpx.HTTPError as error:
            response = None
            problem = f"{type(error).__name__}: {error}"
        else:
            problem = f"HTTP {response.status_code}"
        if response is not None and response.status_code == 200:
            transient = 0
            last = response.json()
            if on_progress is not None:
                on_progress(last)
            if last["status"] == "completed":
                return last, None
            if last["status"] == "failed":
                return last, "the project failed: " + _failure_summary(last)
        elif response is not None and response.status_code < 500:
            return last, f"GET /api/projects/{project_id} answered {problem}: {response.text[:300]}"
        else:
            transient += 1
            if transient >= POLL_TRANSIENT_LIMIT:
                return last, f"be unreachable: {POLL_TRANSIENT_LIMIT} polls in a row failed ({problem})"
        if clock() >= deadline:
            return last, f"timeout after {timeout:g} s; status {last['status'] if last else 'unknown'}"
        await sleep(interval)


def _failure_summary(project: dict[str, Any]) -> str:
    failed = [r for r in project["rows"] if r["status"] == "error"]
    return "; ".join(
        f"{r['stage']}[{r['instanceIndex']}] {r['error']['code'] if r['error'] else '?'}: "
        f"{(r['error'] or {}).get('message', '')[:200]}"
        for r in failed
    ) or "no row in error"
