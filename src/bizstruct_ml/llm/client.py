from openai import AsyncAzureOpenAI, AsyncOpenAI, APIError, APITimeoutError
from pydantic import BaseModel

from bizstruct_ml.config import settings


class LLMError(Exception):
    pass


def _build_client() -> AsyncAzureOpenAI | AsyncOpenAI:
    if settings.use_azure:
        if not settings.azure_openai_endpoint or not settings.azure_openai_api_key:
            raise RuntimeError("AZURE_OPENAI_ENDPOINT and AZURE_OPENAI_API_KEY are required for Azure OpenAI")
        return AsyncAzureOpenAI(
            azure_endpoint=settings.azure_openai_endpoint,
            api_key=settings.azure_openai_api_key,
            api_version=settings.azure_openai_api_version,
            timeout=60.0,
        )
    if not settings.openai_api_key:
        raise RuntimeError("Either OPENAI_API_KEY or AZURE_OPENAI_ENDPOINT must be set")
    return AsyncOpenAI(
        api_key=settings.openai_api_key,
        timeout=60.0,
    )


def _model_name() -> str:
    if settings.use_azure:
        if not settings.azure_openai_deployment:
            raise RuntimeError("AZURE_OPENAI_DEPLOYMENT is required for Azure OpenAI")
        return settings.azure_openai_deployment
    return settings.openai_model


class LLMClient:
    def __init__(self) -> None:
        self._client = _build_client()
        self._model = _model_name()

    async def generate_structured(
        self,
        messages: list[dict],
        schema: type[BaseModel],
    ) -> BaseModel:
        try:
            completion = await self._client.beta.chat.completions.parse(
                model=self._model,
                messages=messages,
                response_format=schema,
            )
            result = completion.choices[0].message.parsed
            if result is None:
                raise LLMError("LLM returned empty parsed result")
            return result
        except APITimeoutError as e:
            raise LLMError(f"LLM request timed out: {e}") from e
        except APIError as e:
            raise LLMError(f"LLM API error: {e}") from e

    async def aclose(self) -> None:
        await self._client.close()
