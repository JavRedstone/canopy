import pytest

from worker.settings import WorkerSettings


def _settings(**overrides: object) -> WorkerSettings:
    return WorkerSettings(_env_file=None, **overrides)


def test_worker_uses_gateway_task_names_instead_of_provider_models() -> None:
    settings = _settings()

    assert settings.outline_model == "course_outline"
    assert settings.module_concepts_model == "module_concepts"
    assert settings.embedding_model == "embedding"
    assert settings.builder_model == "lesson_build"


def test_worker_requires_supabase_configuration() -> None:
    with pytest.raises(RuntimeError, match="Supabase URL"):
        _settings().require_runtime_configuration()


def test_production_worker_requires_internal_service_token() -> None:
    settings = _settings(
        environment="production",
        supabase_url="https://example.supabase.co",
        supabase_service_role_key="service-role-key",
    )

    with pytest.raises(RuntimeError, match="APP_INTERNAL_SERVICE_TOKEN"):
        settings.require_runtime_configuration()


def test_development_worker_accepts_gateway_without_provider_key() -> None:
    settings = _settings(
        environment="development",
        supabase_url="https://example.supabase.co",
        supabase_service_role_key="service-role-key",
    )

    settings.require_runtime_configuration()
