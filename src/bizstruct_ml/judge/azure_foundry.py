"""Judge on an Azure AI Foundry chat-completions deployment (Mistral Large 3).

Talks to the deployment through the OpenAI-compatible client already used for
the generator. Nothing about what the deployment accepts is assumed: JSON mode
and max tokens are opt-in settings, to be switched on only after
`scripts/judge_smoke.py` shows they work.
"""

import asyncio
from collections.abc import Awaitable, Callable
from typing import ClassVar

import httpx
from openai import APIError, AsyncOpenAI, RateLimitError

from bizstruct_ml.judge.base import JudgeModel, JudgeModelError


class AzureFoundryChatJudge(JudgeModel):
    family: ClassVar[str] = "mistral"

    def __init__(
        self,
        *,
        endpoint: str,
        api_key: str,
        deployment: str,
        timeout_seconds: float = 60.0,
        json_mode: bool = False,
        max_tokens: int | None = None,
        rate_limit_retries: int = 4,
        max_retry_after_seconds: float = 60.0,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        self._rate_limit_retries = rate_limit_retries
        self._max_retry_after = max_retry_after_seconds
        self._sleep = sleep
        self._deployment = deployment
        self._json_mode = json_mode
        self._max_tokens = max_tokens
        self._client = AsyncOpenAI(
            base_url=endpoint,
            api_key=api_key,
            # Foundry endpoints accept the key as either a bearer token or an
            # `api-key` header; send both so the endpoint flavour does not matter.
            default_headers={"api-key": api_key},
            timeout=timeout_seconds,
            max_retries=0,  # retries belong to ConsistencyJudge, one layer only
            http_client=http_client,
        )

    async def complete_json(self, *, system: str, user: str, temperature: float = 0.0) -> str:
        params: dict[str, object] = {
            "model": self._deployment,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "temperature": temperature,
        }
        if self._json_mode:
            params["response_format"] = {"type": "json_object"}
        if self._max_tokens is not None:
            params["max_tokens"] = self._max_tokens
        completion = None
        for attempt in range(self._rate_limit_retries + 1):
            try:
                completion = await self._client.chat.completions.create(**params)  # type: ignore[arg-type]
                break
            except RateLimitError as e:
                # A 429 is the quota speaking, not a failure of the check: wait as long as the
                # service asks and try again, so the check is not silently skipped.
                if attempt == self._rate_limit_retries:
                    raise JudgeModelError(f"judge API error: still rate limited after {attempt} retries: {e}") from e
                await self._sleep(self._backoff(e, attempt))
            except APIError as e:  # includes timeouts and connection errors
                raise JudgeModelError(f"judge API error: {e}") from e
        assert completion is not None
        content = completion.choices[0].message.content if completion.choices else None
        if not content:
            raise JudgeModelError("judge returned an empty reply")
        return content

    def _backoff(self, error: RateLimitError, attempt: int) -> float:
        """Seconds to wait: the Retry-After header if it is a number, else 2, 4, 8 ... seconds."""
        header = error.response.headers.get("retry-after")
        try:
            wait = float(header) if header is not None else 2.0 ** (attempt + 1)
        except ValueError:  # an HTTP date: not worth parsing, fall back to the exponential wait
            wait = 2.0 ** (attempt + 1)
        return min(max(wait, 0.0), self._max_retry_after)

    async def aclose(self) -> None:
        await self._client.close()
