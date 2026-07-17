"""Lesson building: generate, validate, and store the lesson bundle for one concept.

Coding lessons are sandbox-validated (the reference solution must pass every test, with
an agentic repair loop on failure). Conceptual lessons carry no workspace, so they only
go through generation and schema/citation validation. Both kinds are stored as
lesson_revisions through apply_lesson_bundle.
"""

import logging
from typing import Any

from supabase import Client

from worker.context import citation_chunks
from worker.errors import RETRYABLE_ERRORS
from worker.lesson_agent import generate_conceptual_bundle, generate_lesson_bundle, repair_bundle
from worker.lesson_schema import LessonBundle, WorkspaceFile, reference_workspace, starter_workspace, validate_lesson_bundle
from worker.llm import LLMGatewayClient
from worker.sandbox import SandboxFile, SandboxRunnerClient
from worker.settings import WorkerSettings


logger = logging.getLogger(__name__)

# How many times a lesson bundle may be regenerated with validation feedback
# before the build is declared failed.
BUNDLE_VALIDATION_ATTEMPTS = 3


class LessonBuilder:
    def __init__(self, settings: WorkerSettings, client: Client, openai: LLMGatewayClient, sandbox: SandboxRunnerClient) -> None:
        self.settings = settings
        self.client = client
        self.openai = openai
        self.sandbox = sandbox

    def build_lesson(self, lesson_definition_id: str) -> None:
        claim = self.client.rpc("claim_lesson_build", {"p_lesson_definition_id": lesson_definition_id}).execute().data or []
        if not claim:
            return
        claimed = claim[0]
        try:
            if self._concept_kind(claimed) == "conceptual":
                bundle, status = self._conceptual_bundle(lesson_definition_id, claimed)
            else:
                bundle, status = self._coding_bundle(lesson_definition_id, claimed)
            self.client.rpc(
                "apply_lesson_bundle",
                {
                    "p_lesson_definition_id": lesson_definition_id,
                    "p_revision": claimed["next_revision"],
                    "p_bundle": bundle.model_dump(mode="json"),
                    "p_validation_status": status,
                },
            ).execute()
            if status == "failed":
                logger.warning(
                    "Lesson exhausted its build attempts without passing tests",
                    extra={"lesson_definition_id": lesson_definition_id},
                )
        except RETRYABLE_ERRORS:
            self.client.table("lesson_definitions").update({"build_status": "pending"}).eq("id", lesson_definition_id).execute()
            raise
        except Exception:
            self.client.table("lesson_definitions").update({"build_status": "failed"}).eq("id", lesson_definition_id).execute()
            raise

    def _concept_kind(self, claimed: dict[str, Any]) -> str:
        kind = claimed.get("concept_kind")
        if kind:
            return str(kind)
        # A claim from the pre-conceptual-bundles claim_lesson_build lacks the kind;
        # resolve it so a conceptual lesson is never sandbox-built as a coding lab.
        rows = self.client.table("concepts").select("kind").eq("id", claimed["concept_id"]).execute().data or []
        return rows[0]["kind"] if rows else "coding"

    def _coding_bundle(self, lesson_definition_id: str, claimed: dict[str, Any]) -> tuple[LessonBundle, str]:
        # A starter that already passes every test leaves the learner nothing to do —
        # the classic failure being the model copying the reference solution into the
        # visible workspace files. Verify the starter FAILS before accepting the bundle.
        starter_feedback: str | None = None
        for _ in range(BUNDLE_VALIDATION_ATTEMPTS):
            bundle = self._generate_validated(
                generate_lesson_bundle,
                self.settings.builder_model,
                claimed,
                lesson_definition_id,
                initial_feedback=starter_feedback,
                require_workspace=True,
            )
            starter_result = self.sandbox.run_pytest(
                [SandboxFile(file.path, file.content) for file in starter_workspace(bundle)]
            )
            if not starter_result.passed:
                break
            starter_feedback = (
                "The visible workspace files already pass every test, so the learner has nothing to implement. "
                "Rewrite the visible files as stubs or deliberate gaps that fail the tests until completed; "
                "keep the full implementation only in reference_solution_files."
            )
            logger.warning(
                "Starter workspace already passes the tests; regenerating with feedback",
                extra={"lesson_definition_id": lesson_definition_id},
            )
        else:
            raise ValueError(
                f"Lesson starter still passed every test after {BUNDLE_VALIDATION_ATTEMPTS} attempts."
            )
        files = {file.path: file.content for file in reference_workspace(bundle)}
        result = self.sandbox.run_pytest([SandboxFile(path, content) for path, content in files.items()])

        attempts = 1
        while not result.passed and attempts < self.settings.lesson_build_max_attempts:
            files, result = repair_bundle(
                self.openai,
                self.settings.builder_model,
                self.sandbox,
                files,
                result,
                self.settings.lesson_build_max_tool_calls,
            )
            bundle = _patch_reference_solution(bundle, files)
            attempts += 1

        return bundle, "validated" if result.passed else "failed"

    def _conceptual_bundle(self, lesson_definition_id: str, claimed: dict[str, Any]) -> tuple[LessonBundle, str]:
        bundle = self._generate_validated(
            generate_conceptual_bundle,
            self.settings.conceptual_builder_model,
            claimed,
            lesson_definition_id,
            forbid_workspace=True,
        )
        return bundle, "validated"

    def _generate_validated(
        self,
        generate: Any,
        model: str,
        claimed: dict[str, Any],
        lesson_definition_id: str,
        initial_feedback: str | None = None,
        **workspace_rule: bool,
    ) -> LessonBundle:
        feedback: str | None = initial_feedback
        for _ in range(BUNDLE_VALIDATION_ATTEMPTS):
            bundle = generate(
                self.openai,
                model,
                concept_title=claimed["concept_title"],
                concept_summary=claimed["summary_markdown"],
                chunks=citation_chunks(self.client, claimed["citations_json"]),
                feedback=feedback,
            )
            try:
                validate_lesson_bundle(bundle, claimed["citations_json"], **workspace_rule)
                return bundle
            except ValueError as exc:
                feedback = str(exc)
                logger.warning(
                    "Lesson bundle failed validation; regenerating with feedback: %s",
                    feedback,
                    extra={"lesson_definition_id": lesson_definition_id},
                )
        raise ValueError(f"Lesson bundle failed validation after {BUNDLE_VALIDATION_ATTEMPTS} attempts: {feedback}")


def _patch_reference_solution(bundle: LessonBundle, files: dict[str, str]) -> LessonBundle:
    """Fold repair-loop file writes back into the bundle. Visible workspace files are
    untouched — they're deliberately supposed to have the gap the student fills in."""

    def patched(group: list[WorkspaceFile]) -> list[WorkspaceFile]:
        return [WorkspaceFile(path=file.path, content=files.get(file.path, file.content)) for file in group]

    return bundle.model_copy(
        update={
            "assessment": bundle.assessment.model_copy(
                update={
                    "reference_solution_files": patched(bundle.assessment.reference_solution_files),
                    "visible_tests": patched(bundle.assessment.visible_tests),
                    "hidden_tests": patched(bundle.assessment.hidden_tests),
                }
            )
        }
    )
