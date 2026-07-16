from functools import lru_cache

from supabase import Client, create_client

from app.settings import get_settings


@lru_cache
def get_service_client() -> Client:
    """Create the server-only client used by the API and worker-facing repository."""
    settings = get_settings()
    if not settings.supabase_url or not settings.supabase_service_role_key:
        raise RuntimeError("Supabase URL and server-only secret key must be configured.")
    return create_client(settings.supabase_url, settings.supabase_service_role_key)
