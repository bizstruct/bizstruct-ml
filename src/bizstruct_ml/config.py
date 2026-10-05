from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # extra="ignore": existing .env files still carry the removed WEBPUBSUB_* keys.
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # Service Bus
    service_bus_connection_string: str
    service_bus_queue_name: str

    # Backend
    backend_base_url: str
    backend_api_key: str

    # OpenAI (plain) — використовується якщо AZURE_OPENAI_ENDPOINT не вказано
    openai_api_key: str | None = None
    openai_model: str = "gpt-4o"

    # Azure OpenAI — використовується якщо AZURE_OPENAI_ENDPOINT вказано
    azure_openai_endpoint: str | None = None
    azure_openai_api_key: str | None = None
    azure_openai_deployment: str | None = None
    azure_openai_api_version: str = "2024-10-21"

    @property
    def use_azure(self) -> bool:
        return bool(self.azure_openai_endpoint)

    # Langfuse — опціонально. Якщо public/secret key не задані, трейсинг
    # повністю вимкнений: воркер працює як без нього, без жодних помилок
    # (див. bizstruct_ml.observability.tracing).
    langfuse_public_key: str | None = None
    langfuse_secret_key: str | None = None
    langfuse_host: str | None = None

    @property
    def langfuse_enabled(self) -> bool:
        return bool(self.langfuse_public_key and self.langfuse_secret_key)

    # Judge model (consistency checks) — a separate deployment and key from the
    # generator, and a different model family (enforced at startup, see
    # bizstruct_ml.judge.guard). JUDGE_PROVIDER picks the implementation from
    # the registry in bizstruct_ml.judge.factory.
    judge_provider: str = "azure_foundry_chat"
    judge_endpoint: str | None = None
    judge_api_key: str | None = None
    judge_deployment: str | None = None
    judge_timeout_seconds: float = 60.0
    # Whether to request response_format=json_object. Off until the live smoke
    # run (scripts/judge_smoke.py) shows the deployment accepts it.
    judge_json_mode: bool = False
    judge_max_tokens: int | None = None

    # Runtime
    llm_max_retries: int = 2
    # How long AutoLockRenewer keeps extending a message lock. Must cover the
    # slowest row (a swot_errc_cycle row can run for minutes).
    lock_renewal_seconds: int = 900
    log_level: str = "INFO"


settings = Settings()
