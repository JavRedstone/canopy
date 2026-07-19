"""Lesson building: generate, validate, and store the lesson bundle for one concept.

Generation is split into two phases so a failure in one doesn't force regenerating the
other: lesson content (prose, worked examples, quiz items, hints) is generated and
citation-validated first, then checkpointed (`pending_content_json`) so a worker restart
mid-build doesn't re-pay for it; for coding lessons, the coding artifacts (workspace,
tests, reference solution) are generated second, grounded in the finalized explanation.
Both the starter-too-complete case and the reference-solution-fails case go through a
real, sandbox-verified, path-restricted repair loop (never blind regeneration, and never
able to "fix" a failure by rewriting a test instead of the code). The two content/
artifact pieces are composed into the same LessonBundle shape that was always stored, so
nothing downstream of this module changes. Conceptual lessons carry no workspace, so they
only go through content generation and citation validation. Both kinds are stored as
lesson_revisions through apply_lesson_bundle, which also records the failure reason (if
any) on the lesson_definitions row.
"""

import logging
from typing import Any

from supabase import Client

from worker.context import citation_chunks
from worker.errors import RETRYABLE_ERRORS
from worker.lesson_agent import ENVIRONMENT_ID_BY_LANGUAGE, generate_assessment_content, generate_coding_artifacts, generate_conceptual_content, generate_lesson_content, repair_bundle, strip_starter_solution
from worker.lesson_schema import Assessment, CodingArtifactsBundle, LessonBundle, LessonContentBundle, reference_workspace, starter_workspace, validate_lesson_content
from worker.llm import LLMGatewayClient
from worker.sandbox import SandboxFile, SandboxRunnerClient
from worker.settings import WorkerSettings


logger = logging.getLogger(__name__)

# How many times lesson content, the starter stub, or the reference solution may be
# regenerated/repaired with feedback before the build is declared failed.
BUNDLE_VALIDATION_ATTEMPTS = 3


class LessonBuilder:
    def __init__(self, settings: WorkerSettings, client: Client, openai: LLMGatewayClient, sandbox: SandboxRunnerClient) -> None:
        self.settings = settings
        self.client = client
        self.openai = openai
        self.sandbox = sandbox

    def build_lesson(self, lesson_definition_id: str) -> bool:
        """Returns True once the job is resolved (claimed and finished, or already resolved
        by someone else) so the caller can archive its queue message. Returns False when
        another attempt still holds the claim and hasn't gone stale yet -- the message must
        stay queued so a later redelivery can retry instead of being discarded for good."""
        claim = self.client.rpc(
            "claim_lesson_build",
            {"p_lesson_definition_id": lesson_definition_id, "p_stale_seconds": self.settings.queue_visibility_seconds},
        ).execute().data or []
        if not claim:
            return not self._lesson_still_building(lesson_definition_id)
        claimed = claim[0]
        try:
            if self._concept_kind(claimed) != "coding":
                bundle, status, build_error = self._conceptual_bundle(lesson_definition_id, claimed)
            else:
                # Check Docker-backed execution before paying for generation. If Docker
                # Desktop is stopped, the worker leaves this transient job queued with
                # the direct, actionable error from the sandbox service.
                self.sandbox.ensure_available()
                bundle, status, build_error = self._coding_bundle(lesson_definition_id, claimed)
            self.client.rpc(
                "apply_lesson_bundle",
                {
                    "p_lesson_definition_id": lesson_definition_id,
                    "p_revision": claimed["next_revision"],
                    "p_bundle": bundle.model_dump(mode="json"),
                    "p_validation_status": status,
                    "p_build_error": build_error,
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
        except Exception as exc:
            self.client.table("lesson_definitions").update(
                {"build_status": "failed", "build_error": str(exc)[:2000]}
            ).eq("id", lesson_definition_id).execute()
            raise
        return True

    def _lesson_still_building(self, lesson_definition_id: str) -> bool:
        rows = self.client.table("lesson_definitions").select("build_status").eq("id", lesson_definition_id).execute().data or []
        return bool(rows) and rows[0]["build_status"] == "building"

    def _concept_kind(self, claimed: dict[str, Any]) -> str:
        kind = claimed.get("concept_kind")
        if kind:
            return str(kind)
        # A claim from the pre-conceptual-bundles claim_lesson_build lacks the kind;
        # resolve it so a conceptual lesson is never sandbox-built as a coding lab.
        rows = self.client.table("concepts").select("kind").eq("id", claimed["concept_id"]).execute().data or []
        return rows[0]["kind"] if rows else "coding"

    def _coding_bundle(self, lesson_definition_id: str, claimed: dict[str, Any]) -> tuple[LessonBundle, str, str | None]:
        language = claimed.get("language") or "python"
        environment_id = ENVIRONMENT_ID_BY_LANGUAGE.get(language, "python-basic")
        content = self._content_from_checkpoint_or_generate(generate_lesson_content, self.settings.builder_model, claimed, lesson_definition_id, language)

        artifacts = generate_coding_artifacts(
            self.openai,
            self.settings.builder_model,
            concept_title=claimed["concept_title"],
            concept_summary=claimed["summary_markdown"],
            lesson_explanation=content.lesson_content.explanation_markdown,
            language=language,
        )
        bundle = _compose_bundle(content, artifacts)

        # A starter that already passes every test leaves the learner nothing to do. The
        # classic failure being the model copying the reference solution into the visible
        # workspace files. Strip it back to a stub with a targeted, sandbox-verified repair
        # loop instead of blindly regenerating the whole artifacts bundle.
        starter_files = {file.path: file.content for file in starter_workspace(bundle)}
        starter_result = self.sandbox.run_pytest([SandboxFile(path, file_content) for path, file_content in starter_files.items()], environment_id=environment_id)
        starter_attempts = 1
        while starter_result.passed and starter_attempts < self.settings.lesson_build_max_attempts:
            logger.warning(
                "Starter workspace already passes the tests; stripping it back to a stub",
                extra={"lesson_definition_id": lesson_definition_id},
            )
            starter_files, starter_result = strip_starter_solution(
                self.openai,
                self.settings.builder_model,
                self.sandbox,
                starter_files,
                artifacts.workspace.visible_paths,
                starter_result,
                self.settings.lesson_build_max_tool_calls,
                environment_id,
            )
            starter_attempts += 1
        if starter_result.passed:
            raise ValueError(f"Lesson starter still passed every test after {starter_attempts} targeted repair attempts.")
        bundle = _patch_starter_files(bundle, starter_files)

        files = {file.path: file.content for file in reference_workspace(bundle)}
        result = self.sandbox.run_pytest([SandboxFile(path, file_content) for path, file_content in files.items()], environment_id=environment_id)

        attempts = 1
        while not result.passed and attempts < self.settings.lesson_build_max_attempts:
            files, result = repair_bundle(
                self.openai,
                self.settings.builder_model,
                self.sandbox,
                files,
                {file.path for file in bundle.assessment.reference_solution_files},
                result,
                self.settings.lesson_build_max_tool_calls,
                environment_id,
            )
            bundle = _patch_reference_solution(bundle, files)
            attempts += 1

        build_error = None if result.passed else result.output[-2000:]
        return bundle, "validated" if result.passed else "failed", build_error

    def _conceptual_bundle(self, lesson_definition_id: str, claimed: dict[str, Any]) -> tuple[LessonBundle, str, str | None]:
        generator = generate_assessment_content if self._concept_kind(claimed) == "assessment" else generate_conceptual_content
        content = self._content_from_checkpoint_or_generate(generator, self.settings.conceptual_builder_model, claimed, lesson_definition_id)
        return _compose_bundle(content, artifacts=None), "validated", None

    def _content_from_checkpoint_or_generate(
        self,
        generate: Any,
        model: str,
        claimed: dict[str, Any],
        lesson_definition_id: str,
        language: str | None = None,
    ) -> LessonContentBundle:
        pending = claimed.get("pending_content_json")
        if pending:
            return LessonContentBundle.model_validate(pending)
        content = self._generate_content_validated(generate, model, claimed, lesson_definition_id, language)
        self.client.rpc(
            "save_lesson_content_checkpoint",
            {"p_lesson_definition_id": lesson_definition_id, "p_content": content.model_dump(mode="json")},
        ).execute()
        return content

    def _generate_content_validated(
        self,
        generate: Any,
        model: str,
        claimed: dict[str, Any],
        lesson_definition_id: str,
        language: str | None = None,
    ) -> LessonContentBundle:
        feedback: str | None = None
        # Only the coding-lesson generator (generate_lesson_content) accepts a language --
        # conceptual/assessment content has no code in it, so there's nothing to vary.
        language_kwargs = {"language": language} if language else {}
        for _ in range(BUNDLE_VALIDATION_ATTEMPTS):
            content = generate(
                self.openai,
                model,
                concept_title=claimed["concept_title"],
                concept_summary=claimed["summary_markdown"],
                chunks=citation_chunks(self.client, claimed["citations_json"]),
                feedback=feedback,
                **language_kwargs,
            )
            try:
                validate_lesson_content(content, claimed["citations_json"])
                return content
            except ValueError as exc:
                feedback = str(exc)
                logger.warning(
                    "Lesson content failed validation; regenerating with feedback: %s",
                    feedback,
                    extra={"lesson_definition_id": lesson_definition_id},
                )
        raise ValueError(f"Lesson content failed validation after {BUNDLE_VALIDATION_ATTEMPTS} attempts: {feedback}")


def _compose_bundle(content: LessonContentBundle, artifacts: CodingArtifactsBundle | None) -> LessonBundle:
    return LessonBundle(
        lesson_content=content.lesson_content,
        workspace=artifacts.workspace if artifacts else None,
        assessment=Assessment(
            visible_tests=artifacts.visible_tests if artifacts else [],
            hidden_tests=artifacts.hidden_tests if artifacts else [],
            quiz_items=content.quiz_items,
            hints=content.hints,
            reference_solution_files=artifacts.reference_solution_files if artifacts else [],
        ),
    )


def _patch_reference_solution(bundle: LessonBundle, files: dict[str, str]) -> LessonBundle:
    """Fold the repair loop's writes back into the bundle. write_file is restricted to
    reference_solution_files paths, so tests and the starter are guaranteed unchanged."""
    patched = [file.model_copy(update={"content": files.get(file.path, file.content)}) for file in bundle.assessment.reference_solution_files]
    return bundle.model_copy(update={"assessment": bundle.assessment.model_copy(update={"reference_solution_files": patched})})


def _patch_starter_files(bundle: LessonBundle, files: dict[str, str]) -> LessonBundle:
    """Fold the targeted starter-repair loop's writes back into the bundle's workspace.
    write_file is restricted to the starter's own paths, so tests and the reference
    solution are guaranteed unchanged."""
    assert bundle.workspace is not None
    patched_files = [file.model_copy(update={"content": files.get(file.path, file.content)}) for file in bundle.workspace.files]
    return bundle.model_copy(update={"workspace": bundle.workspace.model_copy(update={"files": patched_files})})
