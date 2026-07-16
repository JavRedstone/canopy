import argparse
import logging
import time

from openai import OpenAI
from supabase import create_client

from worker.ingestion import IngestionWorker
from worker.settings import WorkerSettings


def _build_openai_client(settings: WorkerSettings) -> OpenAI:
    api_key = settings.openai_api_key.get_secret_value()
    if settings.openai_provider == "azure":
        # The Responses API (used for course planning) needs Azure's newer /openai/v1
        # surface, which drops the dated api-version parameter entirely; Microsoft's own
        # docs use the plain OpenAI client with an Azure base_url for this, not AzureOpenAI.
        base_url = settings.azure_openai_endpoint.rstrip("/") + "/openai/v1/"
        return OpenAI(api_key=api_key, base_url=base_url)
    return OpenAI(api_key=api_key)


def main() -> None:
    parser = argparse.ArgumentParser(description="Adaptive Source Learning background worker")
    parser.add_argument("--once", action="store_true", help="Process at most one message from each queue and exit.")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")

    settings = WorkerSettings()
    settings.require_runtime_configuration()
    client = create_client(settings.supabase_url, settings.supabase_service_role_key)
    openai = _build_openai_client(settings)
    worker = IngestionWorker(settings, client, openai)
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
