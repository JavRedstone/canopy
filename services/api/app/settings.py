from functools import lru_cache
from typing import Literal

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_prefix="APP_", extra="ignore")

    environment: str = "development"
    auth_mode: Literal["development", "supabase"] = "development"
    repository_backend: Literal["memory", "supabase"] = "memory"
    supabase_url: str | None = None
    supabase_service_role_key: str | None = None
    database_url: str | None = None
    cors_origins: str = "http://localhost:3000"
    sandbox_timeout_seconds: int = 20
    sandbox_runner_url: str = "http://localhost:8020"
    llm_gateway_url: str = "http://localhost:8010"
    llm_gateway_timeout_seconds: int = 30
    internal_service_token: SecretStr | None = None

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
