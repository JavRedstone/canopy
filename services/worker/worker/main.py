import argparse
import logging
import time

import httpx
from supabase import ClientOptions, create_client

from worker.llm import LLMGatewayClient
from worker.runner import Worker
from worker.sandbox import SandboxRunnerClient
from worker.settings import WorkerSettings


def _build_llm_client(settings: WorkerSettings) -> LLMGatewayClient:
    token = settings.internal_service_token.get_secret_value() if settings.internal_service_token else None
    return LLMGatewayClient(settings.llm_gateway_url, internal_service_token=token)


def _build_supabase_client(settings: WorkerSettings):
    # Same hardening as the API service: avoid httpx's sync HTTP/2 transport,
    # whose single long-lived multiplexed connection is prone to transport-level
    # failures (corrupted TLS records, stalled reads) on a poller that keeps the
    # connection open for hours. HTTP/1.1 pools short-lived connections instead.
    http_client = httpx.Client(http2=False, timeout=httpx.Timeout(30.0), follow_redirects=True)
    return create_client(
        settings.supabase_url,
        settings.supabase_service_role_key,
        options=ClientOptions(httpx_client=http_client),
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Adaptive Source Learning background worker")
    parser.add_argument("--once", action="store_true", help="Process at most one message from each queue and exit.")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")

    settings = WorkerSettings()
    settings.require_runtime_configuration()
    client = _build_supabase_client(settings)
    llm = _build_llm_client(settings)
    token = settings.internal_service_token.get_secret_value() if settings.internal_service_token else None
    sandbox = SandboxRunnerClient(
        settings.sandbox_runner_url,
        internal_service_token=token,
        timeout_seconds=settings.sandbox_timeout_seconds,
    )
    worker = Worker(settings, client, llm, sandbox)
    print(f"Adaptive Source Learning worker started in {settings.environment} mode.")
    while True:
        if not worker.run_once():
            if args.once:
                return
            time.sleep(settings.queue_poll_seconds)
        elif args.once:
            return


if __name__ == "__main__":
    main()
