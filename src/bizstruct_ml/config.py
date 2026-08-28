from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

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

    # Web PubSub — опціонально, якщо не вказано — нотифікації пропускаються
    webpubsub_connection_string: str | None = None
    webpubsub_hub: str = "projects"

    # Langfuse — опціонально. Якщо public/secret key не задані, трейсинг
    # повністю вимкнений: воркер працює як без нього, без жодних помилок
    # (див. bizstruct_ml.observability.tracing).
    langfuse_public_key: str | None = None
    langfuse_secret_key: str | None = None
    langfuse_host: str | None = None

    @property
    def langfuse_enabled(self) -> bool:
        return bool(self.langfuse_public_key and self.langfuse_secret_key)

    # Runtime
    llm_max_retries: int = 2
    log_level: str = "INFO"


settings = Settings()
