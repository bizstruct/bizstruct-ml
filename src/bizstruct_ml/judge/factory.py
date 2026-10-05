"""Choose the judge provider by JUDGE_PROVIDER. A new provider is one class
plus one entry in `PROVIDERS`."""

from collections.abc import Callable

from bizstruct_ml.config import Settings
from bizstruct_ml.judge.azure_foundry import AzureFoundryChatJudge
from bizstruct_ml.judge.base import JudgeModel
from bizstruct_ml.judge.fake import FakeJudgeModel


class JudgeConfigError(RuntimeError):
    """The judge settings are missing or name an unknown provider."""


def _azure_foundry_chat(settings: Settings) -> JudgeModel:
    missing = [
        name
        for name, value in (
            ("JUDGE_ENDPOINT", settings.judge_endpoint),
            ("JUDGE_API_KEY", settings.judge_api_key),
            ("JUDGE_DEPLOYMENT", settings.judge_deployment),
        )
        if not value
    ]
    if missing:
        raise JudgeConfigError(f"{', '.join(missing)} required for JUDGE_PROVIDER=azure_foundry_chat")
    assert settings.judge_endpoint and settings.judge_api_key and settings.judge_deployment
    return AzureFoundryChatJudge(
        endpoint=settings.judge_endpoint,
        api_key=settings.judge_api_key,
        deployment=settings.judge_deployment,
        timeout_seconds=settings.judge_timeout_seconds,
        json_mode=settings.judge_json_mode,
        max_tokens=settings.judge_max_tokens,
    )


def _fake(settings: Settings) -> JudgeModel:
    return FakeJudgeModel()


PROVIDERS: dict[str, Callable[[Settings], JudgeModel]] = {
    "azure_foundry_chat": _azure_foundry_chat,
    "fake": _fake,
}


def build_judge_model(settings: Settings) -> JudgeModel:
    try:
        builder = PROVIDERS[settings.judge_provider]
    except KeyError:
        raise JudgeConfigError(
            f"unknown JUDGE_PROVIDER '{settings.judge_provider}'; known: {', '.join(sorted(PROVIDERS))}"
        ) from None
    return builder(settings)
