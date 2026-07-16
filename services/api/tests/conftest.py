import os

import pytest

from app.settings import get_settings
from app.supabase import get_service_client


# API tests remain isolated from the linked Supabase project.
os.environ["APP_AUTH_MODE"] = "development"
os.environ["APP_REPOSITORY_BACKEND"] = "memory"


@pytest.fixture(autouse=True)
def clear_configuration_caches() -> None:
    get_settings.cache_clear()
    get_service_client.cache_clear()
    yield
    get_settings.cache_clear()
    get_service_client.cache_clear()
