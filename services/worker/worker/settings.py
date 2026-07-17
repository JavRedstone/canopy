from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class WorkerSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_prefix="APP_", extra="ignore")

    environment: str = "development"
    supabase_url: str | None = None
    supabase_service_role_key: str | None = None
    llm_gateway_url: str = "http://localhost:8010"
    sandbox_runner_url: str = "http://localhost:8020"
    internal_service_token: SecretStr | None = None

    embedding_dimensions: int = 1536
    queue_visibility_seconds: int = 300
    queue_poll_seconds: float = 2.0
    chunk_characters: int = 1600
    chunk_overlap_characters: int = 200
    embedding_batch_size: int = 32
    # Broad goal-relevant chunks shown to the skeleton call; a tighter, module-focused
    # set is retrieved per module for its concepts.
    planner_context_chunk_limit: int = 40
    planner_module_context_chunk_limit: int = 16

    # Agentic lesson sandbox builder: generate -> run in Docker -> repair on failure.
    lesson_build_max_attempts: int = 3
    lesson_build_max_tool_calls: int = 8
    sandbox_timeout_seconds: int = 20

    @property
    def planner_model(self) -> str:
        return "course_planning"

    @property
    def embedding_model(self) -> str:
        return "embedding"

    @property
    def builder_model(self) -> str:
        return "lesson_build"

    @property
    def conceptual_builder_model(self) -> str:
        return "concept_regeneration"

    def require_runtime_configuration(self) -> None:
        if not self.supabase_url or not self.supabase_service_role_key:
            raise RuntimeError("Supabase URL and server-only secret key must be configured for the worker.")
        if self.environment != "development" and not self.internal_service_token:
            raise RuntimeError("APP_INTERNAL_SERVICE_TOKEN must be configured outside development.")
