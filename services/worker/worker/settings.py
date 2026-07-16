from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class WorkerSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_prefix="APP_", extra="ignore")

    environment: str = "development"
    supabase_url: str | None = None
    supabase_service_role_key: str | None = None
    openai_api_key: SecretStr | None = None
    openai_planner_model: str = "gpt-5.4-mini"
    openai_embedding_model: str = "text-embedding-3-small"
    embedding_dimensions: int = 1536
    queue_visibility_seconds: int = 300
    queue_poll_seconds: float = 2.0
    chunk_characters: int = 1600
    chunk_overlap_characters: int = 200
    embedding_batch_size: int = 32
    planner_context_chunk_limit: int = 40

    def require_runtime_configuration(self) -> None:
        if not self.supabase_url or not self.supabase_service_role_key:
            raise RuntimeError("Supabase URL and server-only secret key must be configured for the worker.")
        if not self.openai_api_key:
            raise RuntimeError("APP_OPENAI_API_KEY must be configured before the worker can process jobs.")
