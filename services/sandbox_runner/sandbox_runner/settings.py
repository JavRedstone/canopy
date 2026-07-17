from functools import lru_cache

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class SandboxRunnerSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_prefix="APP_", extra="ignore")

    environment: str = "development"
    internal_service_token: SecretStr | None = None
    sandbox_timeout_seconds: int = 20

    def require_runtime_configuration(self) -> None:
        if self.environment != "development" and not self.internal_service_token:
            raise RuntimeError("APP_INTERNAL_SERVICE_TOKEN must be configured outside development.")


@lru_cache
def get_settings() -> SandboxRunnerSettings:
    return SandboxRunnerSettings()
