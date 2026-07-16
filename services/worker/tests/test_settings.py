import pytest

from worker.settings import WorkerSettings


def _settings(**overrides: object) -> WorkerSettings:
    return WorkerSettings(_env_file=None, **overrides)


def test_default_provider_uses_openai_model_names() -> None:
    settings = _settings(openai_planner_model="gpt-planner", openai_embedding_model="text-embed")

    assert settings.openai_provider == "openai"
    assert settings.planner_model == "gpt-planner"
    assert settings.embedding_model == "text-embed"


def test_azure_provider_uses_deployment_names_instead_of_model_names() -> None:
    settings = _settings(
        openai_provider="azure",
        openai_planner_model="gpt-planner",
        openai_embedding_model="text-embed",
        azure_openai_planner_deployment="my-planner-deployment",
        azure_openai_embedding_deployment="my-embedding-deployment",
    )

    assert settings.planner_model == "my-planner-deployment"
    assert settings.embedding_model == "my-embedding-deployment"


def test_require_runtime_configuration_rejects_azure_without_endpoint() -> None:
    settings = _settings(
        supabase_url="https://example.supabase.co",
        supabase_service_role_key="service-role-key",
        openai_api_key="sk-test",
        openai_provider="azure",
        azure_openai_planner_deployment="my-planner-deployment",
        azure_openai_embedding_deployment="my-embedding-deployment",
    )

    with pytest.raises(RuntimeError, match="APP_AZURE_OPENAI_ENDPOINT"):
        settings.require_runtime_configuration()


def test_require_runtime_configuration_rejects_azure_without_deployments() -> None:
    settings = _settings(
        supabase_url="https://example.supabase.co",
        supabase_service_role_key="service-role-key",
        openai_api_key="sk-test",
        openai_provider="azure",
        azure_openai_endpoint="https://example.openai.azure.com/",
    )

    with pytest.raises(RuntimeError, match="APP_AZURE_OPENAI_PLANNER_DEPLOYMENT"):
        settings.require_runtime_configuration()


def test_require_runtime_configuration_accepts_complete_azure_configuration() -> None:
    settings = _settings(
        supabase_url="https://example.supabase.co",
        supabase_service_role_key="service-role-key",
        openai_api_key="sk-test",
        openai_provider="azure",
        azure_openai_endpoint="https://example.openai.azure.com/",
        azure_openai_planner_deployment="my-planner-deployment",
        azure_openai_embedding_deployment="my-embedding-deployment",
    )

    settings.require_runtime_configuration()
