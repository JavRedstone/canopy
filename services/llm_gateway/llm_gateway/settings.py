from functools import lru_cache
from typing import Literal

from pydantic import AliasChoices, Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


GatewayTask = Literal["course_planning", "lesson_build", "lesson_repair", "concept_regeneration", "quiz_grading", "embedding"]


class GatewaySettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_prefix="APP_", extra="ignore", populate_by_name=True)

    environment: str = "development"
    internal_service_token: SecretStr | None = None

    # "aws" is Bedrock's Converse API (Claude/Nova/Titan); "aws_openai" is
    # Bedrock's bedrock-mantle OpenAI Responses endpoint (GPT-5.4 family).
    # APP_OPENAI_PROVIDER is accepted as a legacy alias for APP_LLM_PROVIDER.
    llm_provider: Literal["openai", "azure", "aws", "aws_openai"] = Field(
        default="openai",
        validation_alias=AliasChoices("app_llm_provider", "app_openai_provider"),
    )
    openai_api_key: SecretStr | None = None
    openai_planner_model: str = "gpt-5.4-mini"
    openai_embedding_model: str = "text-embedding-3-small"
    # Lesson generation runs on every concept, so it uses Luna, the newest-generation
    # small/fast tier. Repair only fires on labs that already failed their first sandbox
    # run, so it can afford the flagship Sol reasoning tier where generation cannot.
    openai_builder_model: str = "gpt-5.6-luna"
    openai_repair_model: str = "gpt-5.6-sol"

    azure_openai_endpoint: str | None = None
    azure_openai_planner_deployment: str | None = None
    azure_openai_embedding_deployment: str | None = None
    azure_openai_builder_deployment: str | None = None
    # Optional; repair reuses the builder deployment when this is unset.
    azure_openai_repair_deployment: str | None = None

    # AWS Bedrock (Converse API). Credentials come from the standard boto3
    # chain (AWS_ACCESS_KEY_ID / AWS_SECRET_ACCESS_KEY / profile / role).
    aws_region: str | None = None
    aws_bedrock_planner_model: str = "us.anthropic.claude-sonnet-4-5-20250929-v1:0"
    aws_bedrock_builder_model: str = "us.anthropic.claude-sonnet-4-5-20250929-v1:0"
    # Optional; repair reuses the builder model when unset (Bedrock has no Sol tier).
    aws_bedrock_repair_model: str | None = None
    aws_bedrock_embedding_model: str = "amazon.titan-embed-text-v2:0"

    # Only used when llm_provider=aws_openai: a long-term Bedrock API key for
    # the bedrock-mantle OpenAI-compatible endpoint. Embeddings still go to
    # the Titan model above via bedrock-runtime (Mantle has no embeddings).
    aws_bedrock_api_key: SecretStr | None = None
    aws_openai_planner_model: str = "openai.gpt-5.4"
    aws_openai_builder_model: str = "openai.gpt-5.4"
    # Only used when llm_provider=aws_openai: repair reuses the builder model when unset.
    aws_openai_repair_model: str | None = None

    def require_runtime_configuration(self) -> None:
        if self.environment != "development" and not self.internal_service_token:
            raise RuntimeError("APP_INTERNAL_SERVICE_TOKEN must be configured outside development.")
        if self.llm_provider in {"openai", "azure"} and not self.openai_api_key:
            raise RuntimeError("APP_OPENAI_API_KEY must be configured before the LLM gateway can start.")
        if self.llm_provider == "azure":
            if not self.azure_openai_endpoint:
                raise RuntimeError("APP_AZURE_OPENAI_ENDPOINT must be configured when APP_LLM_PROVIDER=azure.")
            if (
                not self.azure_openai_planner_deployment
                or not self.azure_openai_embedding_deployment
                or not self.azure_openai_builder_deployment
            ):
                raise RuntimeError(
                    "APP_AZURE_OPENAI_PLANNER_DEPLOYMENT, APP_AZURE_OPENAI_EMBEDDING_DEPLOYMENT, and "
                    "APP_AZURE_OPENAI_BUILDER_DEPLOYMENT must be configured when APP_LLM_PROVIDER=azure."
                )
        if self.llm_provider in {"aws", "aws_openai"} and not self.aws_region:
            raise RuntimeError(f"APP_AWS_REGION must be configured when APP_LLM_PROVIDER={self.llm_provider}.")
        if self.llm_provider == "aws_openai" and not self.aws_bedrock_api_key:
            raise RuntimeError("APP_AWS_BEDROCK_API_KEY must be configured when APP_LLM_PROVIDER=aws_openai.")

    def model_for(self, task: GatewayTask) -> str:
        if task == "course_planning":
            return self._provider_model(
                self.openai_planner_model,
                self.azure_openai_planner_deployment,
                self.aws_bedrock_planner_model,
                self.aws_openai_planner_model,
            )
        if task == "embedding":
            # bedrock-mantle serves no embedding models, so aws_openai reuses Titan.
            return self._provider_model(
                self.openai_embedding_model,
                self.azure_openai_embedding_deployment,
                self.aws_bedrock_embedding_model,
                self.aws_bedrock_embedding_model,
            )
        if task == "lesson_repair":
            # The agentic repair loop is the last line of defense before a lab is declared
            # failed, so it runs on the flagship tier. Providers without a dedicated repair
            # model fall back to their builder model, leaving their behavior unchanged.
            return self._provider_model(
                self.openai_repair_model,
                self.azure_openai_repair_deployment or self.azure_openai_builder_deployment,
                self.aws_bedrock_repair_model or self.aws_bedrock_builder_model,
                self.aws_openai_repair_model or self.aws_openai_builder_model,
            )
        return self._provider_model(
            self.openai_builder_model,
            self.azure_openai_builder_deployment,
            self.aws_bedrock_builder_model,
            self.aws_openai_builder_model,
        )

    def _provider_model(
        self, openai_model: str, azure_deployment: str | None, aws_model: str, aws_openai_model: str
    ) -> str:
        if self.llm_provider == "azure":
            assert azure_deployment is not None
            return azure_deployment
        if self.llm_provider == "aws":
            return aws_model
        if self.llm_provider == "aws_openai":
            return aws_openai_model
        return openai_model


@lru_cache
def get_settings() -> GatewaySettings:
    return GatewaySettings()
