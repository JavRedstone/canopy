"""Practice-pool building: generate, validate, and store one batch of drill questions.

Runs as its own ``practice_pool_build`` generation job, enqueued once a lesson has finished
building and again whenever a learner exhausts a concept's unseen questions. Keeping it off
the lesson's critical path is the point: the lesson renders as soon as it is built, the pool
backfills behind it, and a pool failure can never mark a shipped lesson failed.

Everything one pass needs comes back from ``practice_pool_context`` in a single round trip --
the concept, the finalized explanation the questions must test, every question the learner
could already have been asked, and the batch number to write. Generation is validated before
it is stored, and rejected batches are regenerated with the validator's own message as
feedback, mirroring the lesson content loop in ``lesson_build.py``.
"""

import logging
from typing import Any

from supabase import Client

from worker.context import citation_chunks
from worker.lesson_agent import generate_practice_pool
from worker.lesson_schema import PracticePoolBundle, validate_practice_pool
from worker.llm import LLMGatewayClient
from worker.settings import WorkerSettings


logger = logging.getLogger(__name__)

# How many times a rejected batch is regenerated with feedback before the job gives up.
POOL_VALIDATION_ATTEMPTS = 3


class PracticePoolBuilder:
    def __init__(self, settings: WorkerSettings, client: Client, openai: LLMGatewayClient) -> None:
        self.settings = settings
        self.client = client
        self.openai = openai

    def build_pool(self, lesson_definition_id: str) -> bool:
        """Generate and store one batch for this lesson's concept.

        Returns True once the job is resolved so the caller can archive its queue message.
        A lesson that is no longer built -- deleted, or rebuilding after a regeneration --
        resolves the job rather than retrying: there is no explanation to draw questions
        from, and a later build enqueues its own pool job.
        """
        rows = self.client.rpc(
            "practice_pool_context",
            {"p_lesson_definition_id": lesson_definition_id},
        ).execute().data or []
        if not rows:
            logger.info(
                "Skipping practice pool build: lesson is not currently built",
                extra={"lesson_definition_id": lesson_definition_id},
            )
            return True

        context = rows[0]
        pool = self._generate_validated(context, lesson_definition_id)
        inserted = self.client.rpc(
            "apply_practice_pool",
            {
                "p_concept_id": context["concept_id"],
                "p_course_version_id": context["course_version_id"],
                "p_batch": context["next_batch"],
                "p_items": [item.model_dump(mode="json") for item in pool.practice_items],
            },
        ).execute().data
        if not inserted:
            # Another delivery of the same job already wrote this batch.
            logger.info(
                "Practice pool batch was already stored; discarding this one",
                extra={"lesson_definition_id": lesson_definition_id, "batch": context["next_batch"]},
            )
        return True

    def _generate_validated(self, context: dict[str, Any], lesson_definition_id: str) -> PracticePoolBundle:
        """Generate a batch, and keep regenerating with feedback until it validates.

        Validation is not optional and not the caller's job: a batch that cites an invented
        chunk, or re-asks a question the learner has already seen, must never reach storage.
        """
        citations = context["citations_json"] or []
        existing_prompts = context["existing_prompts"] or []
        feedback: str | None = None
        for _ in range(POOL_VALIDATION_ATTEMPTS):
            pool = generate_practice_pool(
                self.openai,
                self.settings.practice_pool_model,
                concept_title=context["concept_title"],
                concept_summary=context["summary_markdown"],
                lesson_explanation=context["lesson_explanation"],
                chunks=citation_chunks(self.client, citations),
                count=self.settings.practice_pool_batch_size,
                existing_prompts=existing_prompts,
                feedback=feedback,
            )
            try:
                self._validate_batch(pool, citations, existing_prompts)
                return pool
            except ValueError as exc:
                feedback = str(exc)
                logger.warning(
                    "Practice pool batch failed validation; regenerating with feedback: %s",
                    feedback,
                    extra={"lesson_definition_id": lesson_definition_id},
                )
        raise ValueError(f"Practice pool failed validation after {POOL_VALIDATION_ATTEMPTS} attempts: {feedback}")

    def _validate_batch(self, pool: PracticePoolBundle, citations: list[str], existing_prompts: list[str]) -> None:
        """Grounding and variety, plus a floor on batch size.

        The size check is a floor rather than an exact match on the requested count: a batch
        one question short is still a perfectly good batch, and regenerating the whole thing
        to chase an exact number costs a call for no learner benefit. Falling under the
        floor means the model ignored the instruction, which regeneration can actually fix.
        """
        if len(pool.practice_items) < self.settings.practice_pool_min_batch_size:
            raise ValueError(
                f"Only {len(pool.practice_items)} practice questions were written, but at least "
                f"{self.settings.practice_pool_min_batch_size} are needed; write the full batch."
            )
        validate_practice_pool(pool, citations, existing_prompts)
