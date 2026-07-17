import logging
from uuid import UUID

from supabase import Client

from worker.errors import RETRYABLE_ERRORS
from worker.ingestion import SourceIngestor
from worker.lesson_build import LessonBuilder
from worker.llm import LLMGatewayClient
from worker.planning import CoursePlanner
from worker.queues import QueueAdapter, QueueMessage
from worker.sandbox import SandboxRunnerClient
from worker.settings import WorkerSettings


logger = logging.getLogger(__name__)


class Worker:
    """Reads queue messages and dispatches them to the right service.

    Owns the retry policy: a transient error leaves the message on the queue to
    be redelivered after its visibility timeout; anything else marks the record
    failed and archives the message.
    """

    def __init__(self, settings: WorkerSettings, client: Client, openai: LLMGatewayClient, sandbox: SandboxRunnerClient) -> None:
        self.client = client
        self.queue = QueueAdapter(client, settings.queue_visibility_seconds)
        self.ingestor = SourceIngestor(settings, client, openai, self.queue)
        self.planner = CoursePlanner(settings, client, openai)
        self.lesson_builder = LessonBuilder(settings, client, openai, sandbox)

    def run_once(self) -> bool:
        did_work = False
        for message in self.queue.read("ingestion"):
            did_work = True
            self._handle_ingestion(message)
        for message in self.queue.read("generation"):
            did_work = True
            self._handle_generation(message)
        return did_work

    def _handle_ingestion(self, message: QueueMessage) -> None:
        source_id = str(message.payload.get("source_id", ""))
        try:
            UUID(source_id)
            self.ingestor.ingest_source(source_id)
        except RETRYABLE_ERRORS:
            logger.exception("Source ingestion hit a transient error; leaving job queued for retry", extra={"source_id": source_id})
            return
        except Exception:
            logger.exception("Source ingestion failed", extra={"source_id": source_id})
            if source_id:
                self.client.table("source_documents").update({"status": "failed"}).eq("id", source_id).execute()
        self.queue.archive("ingestion", message.message_id)

    def _handle_generation(self, message: QueueMessage) -> None:
        job_type = message.payload.get("type")
        try:
            if job_type == "course_planning":
                course_id = str(message.payload.get("course_id", ""))
                UUID(course_id)
                self.planner.plan_course(course_id)
            elif job_type == "lesson_build":
                lesson_definition_id = str(message.payload.get("lesson_definition_id", ""))
                UUID(lesson_definition_id)
                self.lesson_builder.build_lesson(lesson_definition_id)
            elif job_type == "concept_regeneration":
                # Retired job type; in-flight messages build the same conceptual bundle.
                lesson_definition_id = str(message.payload.get("lesson_definition_id", ""))
                UUID(lesson_definition_id)
                self.lesson_builder.build_lesson(lesson_definition_id)
            else:
                raise ValueError("Unsupported generation job.")
        except RETRYABLE_ERRORS:
            logger.exception("Generation job hit a transient error; leaving job queued for retry", extra={"payload": message.payload})
            return
        except Exception:
            if job_type == "concept_regeneration":
                lesson_definition_id = message.payload.get("lesson_definition_id")
                if lesson_definition_id:
                    self.client.table("lesson_definitions").update({"build_status": "failed"}).eq("id", lesson_definition_id).execute()
            logger.exception("Generation job failed", extra={"payload": message.payload})
        self.queue.archive("generation", message.message_id)
