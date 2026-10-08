from openai import (
    APIError,
    APITimeoutError,
    AsyncAzureOpenAI,
    AsyncOpenAI,
    ContentFilterFinishReasonError,
    LengthFinishReasonError,
)
from pydantic import BaseModel

from bizstruct_ml.config import settings


# Model family of the generator. The judge must come from a different family
# (see bizstruct_ml.judge.guard); both the plain and the Azure OpenAI clients
# below serve OpenAI models.
GENERATOR_FAMILY = "openai"


class LLMError(Exception):
    pass


class LLMContentFilterError(LLMError):
    """The completion ended with finish_reason "content_filter"."""

    finish_reason = "content_filter"


class LLMLengthError(LLMError):
    """The completion ended with finish_reason "length": the output was cut off."""

    finish_reason = "length"


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


def _usage_of(completion) -> dict[str, int] | None:
    usage = completion.usage
    if usage is None:
        return None
    return {"input": usage.prompt_tokens, "output": usage.completion_tokens, "total": usage.total_tokens}


class LLMClient:
    def __init__(self) -> None:
        self._client = _build_client()
        self._model = _model_name()
        # Populated after each generate_structured() call — for tracing
        # (Langfuse generation spans need token usage per call). Single
        # generator owns its LLMClient and calls are sequential, so there's
        # no concurrency hazard in stashing this on the instance.
        self.last_usage: dict[str, int] | None = None
        # The finish reason of the last call ("stop", "length", "content_filter"), for
        # the same reason; None before the first call or when the call never got an answer.
        self.last_finish_reason: str | None = None

    @property
    def model_name(self) -> str:
        return self._model

    async def generate_structured(
        self,
        messages: list[dict],
        schema: type[BaseModel],
    ) -> BaseModel:
        self.last_usage = None
        self.last_finish_reason = None
        try:
            completion = await self._client.beta.chat.completions.parse(
                model=self._model,
                messages=messages,
                response_format=schema,
            )
            self.last_usage = _usage_of(completion)
            self.last_finish_reason = completion.choices[0].finish_reason
            result = completion.choices[0].message.parsed
            if result is None:
                raise LLMError("LLM returned empty parsed result")
            return result
        except LengthFinishReasonError as e:
            self.last_usage = _usage_of(e.completion)
            self.last_finish_reason = LLMLengthError.finish_reason
            raise LLMLengthError(f"LLM output was cut off (finish_reason=length): {e}") from e
        except ContentFilterFinishReasonError as e:
            self.last_finish_reason = LLMContentFilterError.finish_reason
            raise LLMContentFilterError(f"LLM output was blocked (finish_reason=content_filter): {e}") from e
        except APITimeoutError as e:
            raise LLMError(f"LLM request timed out: {e}") from e
        except APIError as e:
            raise LLMError(f"LLM API error: {e}") from e

    async def aclose(self) -> None:
        await self._client.close()
