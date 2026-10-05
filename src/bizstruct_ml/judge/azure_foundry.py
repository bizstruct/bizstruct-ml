"""Judge on an Azure AI Foundry chat-completions deployment (Mistral Large 3).

Talks to the deployment through the OpenAI-compatible client already used for
the generator. Nothing about what the deployment accepts is assumed: JSON mode
and max tokens are opt-in settings, to be switched on only after
`scripts/judge_smoke.py` shows they work.
"""

from typing import ClassVar

import httpx
from openai import APIError, AsyncOpenAI

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
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
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
        try:
            completion = await self._client.chat.completions.create(**params)  # type: ignore[arg-type]
        except APIError as e:  # includes timeouts and connection errors
            raise JudgeModelError(f"judge API error: {e}") from e
        content = completion.choices[0].message.content if completion.choices else None
        if not content:
            raise JudgeModelError("judge returned an empty reply")
        return content

    async def aclose(self) -> None:
        await self._client.close()
