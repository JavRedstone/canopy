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
    # Base URL of the web app -- used only to build durable, shareable links (e.g. a
    # certificate's public verification page) that point back at the frontend, not the API.
    public_app_url: str = "http://localhost:3000"
    # Must stay >= the sandbox runner's slowest per-environment timeout (python-ml's is
    # 60s -- torch/CUDA import alone eats into a tight budget) plus margin, or the API's
    # own HTTP call to the sandbox runner gives up before that environment's container
    # would, surfacing a false "sandbox unavailable" for a run that was still in progress.
    sandbox_timeout_seconds: int = 65
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
