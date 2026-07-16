from types import SimpleNamespace
from uuid import UUID

import pytest
from fastapi import HTTPException

from app import dependencies
from app.settings import get_settings


def test_supabase_auth_returns_verified_user(monkeypatch: pytest.MonkeyPatch) -> None:
    user_id = "5a8b6f45-cc55-4e4a-a9c7-3db69ebd8ec0"
    monkeypatch.setenv("APP_AUTH_MODE", "supabase")
    get_settings.cache_clear()
    monkeypatch.setattr(
        dependencies,
        "get_service_client",
        lambda: SimpleNamespace(auth=SimpleNamespace(get_user=lambda token: SimpleNamespace(user=SimpleNamespace(id=user_id)))),
    )

    assert dependencies.get_current_user(authorization="Bearer valid-access-token") == UUID(user_id)


def test_supabase_auth_rejects_missing_bearer_token(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_AUTH_MODE", "supabase")
    get_settings.cache_clear()

    with pytest.raises(HTTPException, match="Missing bearer token") as error:
        dependencies.get_current_user()

    assert error.value.status_code == 401
