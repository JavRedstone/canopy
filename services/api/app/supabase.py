from functools import lru_cache

import httpx
from supabase import Client, ClientOptions, create_client

from app.settings import get_settings


@lru_cache
def get_service_client() -> Client:
    """Create the server-only client used by the API and worker-facing repository."""
    settings = get_settings()
    if not settings.supabase_url or not settings.supabase_service_role_key:
        raise RuntimeError("Supabase URL and server-only secret key must be configured.")
    # supabase-py defaults to HTTP/2, but httpx's *sync* HTTP/2 transport is not
    # safe when FastAPI's threadpool multiplexes concurrent requests over the one
    # shared connection (reads race and surface as WinError 10035 ReadError on
    # Windows). Plain HTTP/1.1 gives each thread its own pooled connection.
    http_client = httpx.Client(http2=False, timeout=httpx.Timeout(30.0), follow_redirects=True)
    return create_client(
        settings.supabase_url,
        settings.supabase_service_role_key,
        options=ClientOptions(httpx_client=http_client),
    )
