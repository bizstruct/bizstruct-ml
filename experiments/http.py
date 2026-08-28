"""Thin HTTP client for the experiment runner — talks to bizstruct-be's
public API only (POST /api/generation, GET /api/projects/{id}), both of
which are unauthenticated in the current backend (see app/main.py /
app/routers/generation.py / app/routers/projects.py — only /api/internal/*
requires X-API-Key). If that changes, set EXPERIMENT_BACKEND_API_KEY and
it'll be sent as X-API-Key on every request.

Retries with exponential backoff on 429 and on 5xx/network errors — per the
experiment brief, throttling or a transient backend hiccup must never abort
the whole run.
"""

from __future__ import annotations

import asyncio
import random
from typing import Any

import httpx

DEFAULT_MAX_BACKOFF = 60.0
DEFAULT_BASE_BACKOFF = 1.0


class BackendClient:
    def __init__(self, base_url: str, api_key: str | None, timeout: float = 30.0) -> None:
        headers = {"X-API-Key": api_key} if api_key else {}
        self._client = httpx.AsyncClient(base_url=base_url, headers=headers, timeout=timeout)

    async def aclose(self) -> None:
        await self._client.aclose()

    async def _request_with_retry(
        self,
        method: str,
        url: str,
        *,
        json_body: dict[str, Any] | None = None,
        max_attempts: int = 12,
    ) -> httpx.Response:
        attempt = 0
        while True:
            attempt += 1
            try:
                response = await self._client.request(method, url, json=json_body)
            except httpx.RequestError as e:
                if attempt >= max_attempts:
                    raise
                delay = _backoff_delay(attempt)
                print(f"[retry] {method} {url}: network error ({e}), retrying in {delay:.1f}s "
                      f"(attempt {attempt}/{max_attempts})")
                await asyncio.sleep(delay)
                continue

            if response.status_code == 429 or response.status_code >= 500:
                if attempt >= max_attempts:
                    response.raise_for_status()
                retry_after = response.headers.get("Retry-After")
                delay = float(retry_after) if retry_after else _backoff_delay(attempt)
                print(f"[retry] {method} {url}: HTTP {response.status_code}, retrying in "
                      f"{delay:.1f}s (attempt {attempt}/{max_attempts})")
                await asyncio.sleep(delay)
                continue

            return response

    async def create_project(self, idea_text: str, title: str, language: str = "en") -> str:
        response = await self._request_with_retry(
            "POST", "/api/generation",
            json_body={"title": title, "idea": idea_text, "language": language},
        )
        response.raise_for_status()
        body = response.json()
        return str(body["id"])

    async def get_project(self, project_id: str) -> dict[str, Any]:
        response = await self._request_with_retry("GET", f"/api/projects/{project_id}")
        response.raise_for_status()
        return response.json()


def _backoff_delay(attempt: int) -> float:
    base = min(DEFAULT_MAX_BACKOFF, DEFAULT_BASE_BACKOFF * (2 ** (attempt - 1)))
    return base * (0.5 + random.random())  # jitter, avoid thundering herd across parallel projects
