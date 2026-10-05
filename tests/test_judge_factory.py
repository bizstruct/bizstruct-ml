"""Judge provider selection, the family guard and fail-fast startup."""
from typing import ClassVar

import pytest

from bizstruct_ml import __main__ as worker_main
from bizstruct_ml.config import Settings
from bizstruct_ml.judge import factory
from bizstruct_ml.judge.azure_foundry import AzureFoundryChatJudge
from bizstruct_ml.judge.base import JudgeModel
from bizstruct_ml.judge.fake import FakeJudgeModel
from bizstruct_ml.judge.factory import JudgeConfigError, build_judge_model
from bizstruct_ml.judge.guard import FamilyGuardError, assert_different_family
from bizstruct_ml.strategies.pipeline import build_runner


def make_settings(**overrides) -> Settings:
    base = dict(
        service_bus_connection_string="Endpoint=sb://t/;SharedAccessKeyName=t;SharedAccessKey=dA==",
        service_bus_queue_name="q",
        backend_base_url="http://be.test",
        backend_api_key="k",
        azure_openai_endpoint="https://gen.test",
        azure_openai_api_key="gk",
        azure_openai_deployment="gpt",
        judge_provider="fake",
    )
    return Settings(_env_file=None, **{**base, **overrides})


def test_factory_selects_providers():
    assert isinstance(build_judge_model(make_settings(judge_provider="fake")), FakeJudgeModel)
    azure = build_judge_model(
        make_settings(
            judge_provider="azure_foundry_chat",
            judge_endpoint="https://j.test/openai/v1",
            judge_api_key="jk",
            judge_deployment="mistral-large-3",
        )
    )
    assert isinstance(azure, AzureFoundryChatJudge)
    assert azure.family == "mistral"


def test_factory_rejects_unknown_provider():
    with pytest.raises(JudgeConfigError, match="unknown JUDGE_PROVIDER 'nope'"):
        build_judge_model(make_settings(judge_provider="nope"))


def test_azure_provider_names_the_missing_settings():
    with pytest.raises(JudgeConfigError, match="JUDGE_ENDPOINT, JUDGE_API_KEY, JUDGE_DEPLOYMENT"):
        build_judge_model(make_settings(judge_provider="azure_foundry_chat"))


def test_guard_refuses_equal_families_case_insensitively():
    with pytest.raises(FamilyGuardError):
        assert_different_family("openai", "openai")
    with pytest.raises(FamilyGuardError):
        assert_different_family("openai", "OpenAI")
    with pytest.raises(FamilyGuardError):
        assert_different_family("OpenAI", "openai")
    with pytest.raises(FamilyGuardError):
        assert_different_family(" openai ", "openai")
    assert_different_family("openai", "mistral")


class SameFamilyJudge(JudgeModel):
    family: ClassVar[str] = "openai"

    async def complete_json(self, *, system: str, user: str, temperature: float = 0.0) -> str:
        return "{}"


class OtherFamilyJudge(JudgeModel):
    family: ClassVar[str] = "other"

    async def complete_json(self, *, system: str, user: str, temperature: float = 0.0) -> str:
        return '{"score": 5, "violations": []}'


def test_second_provider_is_switched_in_by_env_only(monkeypatch):
    # A new provider is one class plus one registry entry; selecting it is JUDGE_PROVIDER.
    monkeypatch.setitem(factory.PROVIDERS, "other", lambda s: OtherFamilyJudge())
    monkeypatch.setenv("JUDGE_PROVIDER", "other")
    settings = Settings(_env_file=None, **{
        k: v for k, v in make_settings().model_dump().items() if k != "judge_provider"
    })
    assert settings.judge_provider == "other"
    runner = build_runner(settings)
    assert runner is not None
    assert isinstance(build_judge_model(settings), OtherFamilyJudge)


def test_startup_refuses_same_family(monkeypatch):
    monkeypatch.setitem(factory.PROVIDERS, "same", lambda s: SameFamilyJudge())
    with pytest.raises(FamilyGuardError):
        build_runner(make_settings(judge_provider="same"))


def test_worker_exits_nonzero_at_startup_on_same_family(monkeypatch):
    monkeypatch.setitem(factory.PROVIDERS, "same", lambda s: SameFamilyJudge())
    monkeypatch.setattr(worker_main, "settings", make_settings(judge_provider="same"))
    with pytest.raises(SystemExit) as exit_info:
        worker_main.main()
    assert exit_info.value.code == 1


def test_worker_exits_nonzero_at_startup_on_missing_judge_config(monkeypatch):
    monkeypatch.setattr(worker_main, "settings", make_settings(judge_provider="azure_foundry_chat"))
    with pytest.raises(SystemExit):
        worker_main.main()
