import argparse
import logging
import time

from supabase import create_client

from worker.ingestion import IngestionWorker
from worker.llm import LLMGatewayClient
from worker.sandbox import SandboxRunnerClient
from worker.settings import WorkerSettings


def _build_llm_client(settings: WorkerSettings) -> LLMGatewayClient:
    token = settings.internal_service_token.get_secret_value() if settings.internal_service_token else None
    return LLMGatewayClient(settings.llm_gateway_url, internal_service_token=token)


def main() -> None:
    parser = argparse.ArgumentParser(description="Adaptive Source Learning background worker")
    parser.add_argument("--once", action="store_true", help="Process at most one message from each queue and exit.")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")

    settings = WorkerSettings()
    settings.require_runtime_configuration()
    client = create_client(settings.supabase_url, settings.supabase_service_role_key)
    llm = _build_llm_client(settings)
    token = settings.internal_service_token.get_secret_value() if settings.internal_service_token else None
    sandbox = SandboxRunnerClient(
        settings.sandbox_runner_url,
        internal_service_token=token,
        timeout_seconds=settings.sandbox_timeout_seconds,
    )
    worker = IngestionWorker(settings, client, llm, sandbox)
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
