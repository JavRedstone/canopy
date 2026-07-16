from typing import Literal

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class WorkerSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_prefix="APP_", extra="ignore")

    environment: str = "development"
    supabase_url: str | None = None
    supabase_service_role_key: str | None = None

    # Provider switch: "openai" talks to api.openai.com directly, "azure" talks to an
    # Azure OpenAI resource. Both branches reuse the same APP_OPENAI_API_KEY field.
    openai_provider: Literal["openai", "azure"] = "openai"
    openai_api_key: SecretStr | None = None
    openai_planner_model: str = "gpt-5.4-mini"
    openai_embedding_model: str = "text-embedding-3-small"
    openai_builder_model: str = "gpt-5.4-mini"

    # Azure OpenAI only: the resource endpoint and the *deployment* names configured in
    # that resource (Azure calls models by deployment name, not model name). Calls go
    # through the unified /openai/v1 surface, which has no api-version parameter.
    azure_openai_endpoint: str | None = None
    azure_openai_planner_deployment: str | None = None
    azure_openai_embedding_deployment: str | None = None
    azure_openai_builder_deployment: str | None = None

    embedding_dimensions: int = 1536
    queue_visibility_seconds: int = 300
    queue_poll_seconds: float = 2.0
    chunk_characters: int = 1600
    chunk_overlap_characters: int = 200
    embedding_batch_size: int = 32
    planner_context_chunk_limit: int = 40

    # Agentic lesson sandbox builder: generate -> run in Docker -> repair on failure.
    lesson_build_max_attempts: int = 3
    lesson_build_max_tool_calls: int = 8
    sandbox_timeout_seconds: int = 20

    @property
    def planner_model(self) -> str:
        if self.openai_provider == "azure":
            assert self.azure_openai_planner_deployment is not None
            return self.azure_openai_planner_deployment
        return self.openai_planner_model

    @property
    def embedding_model(self) -> str:
        if self.openai_provider == "azure":
            assert self.azure_openai_embedding_deployment is not None
            return self.azure_openai_embedding_deployment
        return self.openai_embedding_model

    @property
    def builder_model(self) -> str:
        if self.openai_provider == "azure":
            assert self.azure_openai_builder_deployment is not None
            return self.azure_openai_builder_deployment
        return self.openai_builder_model

    def require_runtime_configuration(self) -> None:
        if not self.supabase_url or not self.supabase_service_role_key:
            raise RuntimeError("Supabase URL and server-only secret key must be configured for the worker.")
        if not self.openai_api_key:
            raise RuntimeError("APP_OPENAI_API_KEY must be configured before the worker can process jobs.")
        if self.openai_provider == "azure":
            if not self.azure_openai_endpoint:
                raise RuntimeError("APP_AZURE_OPENAI_ENDPOINT must be configured when APP_OPENAI_PROVIDER=azure.")
            if (
                not self.azure_openai_planner_deployment
                or not self.azure_openai_embedding_deployment
                or not self.azure_openai_builder_deployment
            ):
                raise RuntimeError(
                    "APP_AZURE_OPENAI_PLANNER_DEPLOYMENT, APP_AZURE_OPENAI_EMBEDDING_DEPLOYMENT, and "
                    "APP_AZURE_OPENAI_BUILDER_DEPLOYMENT must be configured when APP_OPENAI_PROVIDER=azure."
                )
