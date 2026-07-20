import logging
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import PurePosixPath
from typing import Any, Protocol
from uuid import UUID, uuid4

from fastapi import HTTPException, status
from httpx import HTTPError
from postgrest.exceptions import APIError
from supabase import Client

from app.course_category import accent_colors_for
from app.lesson_bundle import bundle_view
from app.mastery import (
    AssessmentKind,
    assessment_for_quiz_kind,
    bkt_update,
    concept_mastered,
    concept_struggling,
    params_for,
    practice_update,
    prerequisite_needs_review,
    track_for,
    MASTERY_THRESHOLD,
    REVIEW_THRESHOLD,
)
from app.practice import (
    PracticeAttempt,
    PracticeItem,
    PracticeSession,
    concepts_needing_top_up,
    select_practice_items,
)
from app.schemas import CertificateResponse, CitationExcerptResponse, ConceptDetailResponse, ConceptMastery, CoursePointsResponse, CourseMapConcept, CourseMapModule, CourseMapResponse, CourseMasteryResponse, CourseProgressResponse, CourseSourceSummary, CourseSummary, CreateCourseRequest, CreateSourceRequest, LessonPreview, LessonWorkspaceFile, PracticeFilter, PracticeOrder, PracticeQuestion, PracticeScope, PracticeSessionResponse, PrerequisiteConcept, PrerequisiteRecommendation, PrerequisiteReviewResponse, ProfileResponse, QuizAnswerRequest, QuizGradeResponse, QuizItemPreview, QuizOptionPreview, RecommendationDecision, RecommendationSummary, RecommendationsResponse, SourceDownloadResponse, SourceSummary, SourceUploadTarget, UpdateCourseRequest, UpdateProfileRequest
from app.settings import get_settings
from app.supabase import get_service_client


logger = logging.getLogger(__name__)


def _join_titles(titles: list[str]) -> str:
    """Render titles as a bold, human-readable list -- ``**A**``; ``**A** and **B**``;
    ``**A**, **B**, and **C**`` -- for a recommendation sentence."""
    bold = [f"**{title}**" for title in titles]
    if len(bold) == 1:
        return bold[0]
    if len(bold) == 2:
        return f"{bold[0]} and {bold[1]}"
    return ", ".join(bold[:-1]) + f", and {bold[-1]}"


def _prerequisite_closure(adjacency: dict[str, list[str]], start: str) -> list[str]:
    """Breadth-first walk of the prerequisite graph from ``start``, returning every transitive
    prerequisite (ancestor) concept id in nearest-first order, each exactly once. ``adjacency``
    maps a concept id to the ids it directly builds on. The planner keeps this graph acyclic, but
    a ``seen`` guard makes the walk terminate regardless, so a future regression can't hang it."""
    seen = {start}
    order: list[str] = []
    frontier = list(adjacency.get(start, []))
    while frontier:
        current = frontier.pop(0)
        if current in seen:
            continue
        seen.add(current)
        order.append(current)
        frontier.extend(adjacency.get(current, []))
    return order


# When a struggle nudge lists shaky prerequisites, show at most this many -- weakest first -- so
# a deep dependency chain doesn't bury the learner in links. The full set still shows in the
# course-level recommendations panel.
MAX_RECOMMENDED_PREREQS = 5


def _relevant_p(entry: PrerequisiteConcept) -> float:
    """The prerequisite's mastery on the track that decided it was shaky (applied code for a lab,
    understanding otherwise). Used to order weakest-first; a missing estimate sorts last."""
    p = entry.p_apply if entry.kind == "coding" else entry.p_understand
    return p if p is not None else 1.0


# A fixed award per lesson (a coding lab passed via Submit, or every item in a
# conceptual lesson's mastery check answered correctly) -- a coarse, gamified
# completion signal. Not configurable yet; see CourseSummary.quiz_max_attempts for
# the one course-level knob this pass wires up.
POINTS_PER_LESSON = 10

# Mirrors the phase order the planner already validates at generation time
# (worker/planner.py's validate_module_concepts): lectures, then labs, then the
# assessment. Concepts have no persisted position column, so course_map() re-sorts
# by this on every read to guarantee a learner never lands on a lab before any
# lecture in the same module, regardless of slug ordering.
CONCEPT_KIND_PHASE = {"conceptual": 0, "coding": 1, "assessment": 2}


class CourseRepository(Protocol):
    name: str

    def create_source(self, owner_id: UUID, request: CreateSourceRequest) -> SourceUploadTarget: ...

    def complete_source(self, owner_id: UUID, source_id: UUID) -> SourceSummary: ...

    def create_course(self, owner_id: UUID, request: CreateCourseRequest) -> CourseSummary: ...

    def list_courses(self, owner_id: UUID) -> list[CourseSummary]: ...

    def get_course(self, owner_id: UUID, course_id: UUID) -> CourseSummary: ...

    def update_course(self, owner_id: UUID, course_id: UUID, request: UpdateCourseRequest) -> CourseSummary: ...

    def import_course(self, owner_id: UUID, source_course_id: UUID) -> CourseSummary:
        """Clone a shared course's content (not progress) into the caller's account and
        return the new course. Raises 404 if the source is missing or not shared."""
        ...

    def course_map(self, owner_id: UUID, course_id: UUID) -> CourseMapResponse: ...

    def course_progress(self, owner_id: UUID, course_id: UUID) -> CourseProgressResponse: ...

    def regenerate_course(self, owner_id: UUID, course_id: UUID) -> CourseSummary: ...

    def resume_course_lessons(self, owner_id: UUID, course_id: UUID) -> int: ...

    def delete_course(self, owner_id: UUID, course_id: UUID) -> None: ...

    def concept_detail(self, owner_id: UUID, course_id: UUID, slug: str) -> ConceptDetailResponse: ...

    def lesson_workspace(
        self, owner_id: UUID, course_id: UUID, slug: str
    ) -> tuple[list[LessonWorkspaceFile], list[LessonWorkspaceFile], list[LessonWorkspaceFile], str]: ...

    def quiz_item(self, owner_id: UUID, course_id: UUID, slug: str, item_id: str) -> dict[str, Any]: ...

    def quiz_progress(self, owner_id: UUID, course_id: UUID, slug: str, item_id: str) -> tuple[int, int, bool]:
        """Returns (max_attempts, attempts_used, already_correct) for one quiz item,
        lazily creating the learner's assignment for the lesson's current revision."""
        ...

    def record_quiz_response(
        self, owner_id: UUID, course_id: UUID, slug: str, item_id: str, answer: QuizAnswerRequest, grade: QuizGradeResponse
    ) -> int:
        """Persists one attempt (answer and full grade reveal) and marks the lesson's
        assignment completed once every quiz item in it has been answered correctly.
        Returns the new attempts_used count."""
        ...

    def practice_session(
        self,
        owner_id: UUID,
        course_id: UUID,
        scope: PracticeScope,
        ids: list[str],
        count: int,
        order: PracticeOrder,
        filter: PracticeFilter,
        seed: int,
    ) -> PracticeSessionResponse:
        """A batch of answer-stripped pool questions over the concepts in scope, chosen by
        the pure engine in ``practice.py``. Bounded by what the learner has actually
        started, so practice never runs ahead of the course."""
        ...

    def practice_item(self, owner_id: UUID, course_id: UUID, item_id: UUID) -> tuple[dict[str, Any], dict[str, Any]]:
        """The stored pool question (grading material included) and its concept row."""
        ...

    def record_practice_answer(
        self, owner_id: UUID, course_id: UUID, item_id: UUID, concept: dict[str, Any], correct: bool
    ) -> float | None:
        """Log one practice attempt and, when it was correct, award capped positive credit.
        Returns the concept's refreshed ``p_understand`` if the answer moved it."""
        ...

    def request_practice_top_up(self, owner_id: UUID, course_id: UUID, concept_slugs: list[str]) -> list[str]:
        """Queue another generated batch for each named concept; returns those queued."""
        ...

    def complete_coding_lesson(self, owner_id: UUID, course_id: UUID, slug: str) -> None:
        """Marks a coding lab's assignment completed once its checks pass."""
        ...

    def record_coding_submission(self, owner_id: UUID, course_id: UUID, slug: str, passed: bool) -> None:
        """Records a deliberate Submit as an ``apply``-track mastery observation (pass or
        fail) and, on pass, marks the lab completed. Run (visible tests only) is behavioral
        signal and never lands here."""
        ...

    def course_mastery(self, owner_id: UUID, course_id: UUID) -> CourseMasteryResponse:
        """Per-concept dual-track BKT estimates for the learner over the active version."""
        ...

    def concept_prerequisites(self, owner_id: UUID, course_id: UUID, slug: str) -> PrerequisiteReviewResponse:
        """The concepts this one builds on, each with the learner's mastery and a review flag."""
        ...

    def prerequisite_recommendation(self, owner_id: UUID, course_id: UUID, slug: str) -> PrerequisiteRecommendation | None:
        """A review nudge when the learner is struggling on this concept and it builds on a
        shaky prerequisite; ``None`` otherwise. Call after a graded answer updates mastery."""
        ...

    def list_recommendations(self, owner_id: UUID, course_id: UUID) -> RecommendationsResponse:
        """Open (proposed) prerequisite-review recommendations for the learner on this course."""
        ...

    def decide_recommendation(self, owner_id: UUID, course_id: UUID, event_id: UUID, decision: RecommendationDecision) -> None:
        """Record the learner's accept/defer/decline verdict on a recommendation."""
        ...

    def citation_excerpt(self, owner_id: UUID, course_id: UUID, citation_id: UUID) -> CitationExcerptResponse:
        """The source chunk text and filename behind a lesson citation marker."""
        ...

    def certificate(self, owner_id: UUID, course_id: UUID) -> CertificateResponse:
        """The completion certificate for a fully finished course. Raises 409 if the
        course isn't fully completed yet."""
        ...

    def public_certificate(self, certificate_id: UUID) -> CertificateResponse:
        """The same certificate, looked up by its durable public link id instead of
        (owner_id, course_id) -- no authenticated owner required. Raises 404 if unknown."""
        ...

    def profile(self, owner_id: UUID) -> ProfileResponse:
        """The current user's own profile (email + optional display name)."""
        ...

    def update_profile(self, owner_id: UUID, request: UpdateProfileRequest) -> ProfileResponse:
        ...

    def course_sources(self, owner_id: UUID, course_id: UUID) -> list[CourseSourceSummary]:
        """The documents this course was built from, in their attached order."""
        ...

    def source_download_url(self, owner_id: UUID, course_id: UUID, source_id: UUID) -> SourceDownloadResponse:
        """A short-lived signed URL to download one of this course's attached source documents."""
        ...

    def course_points(self, owner_id: UUID, course_id: UUID) -> CoursePointsResponse: ...

    def regenerate_lesson(self, owner_id: UUID, course_id: UUID, slug: str) -> None: ...

    def clear_demo_progress(self, owner_id: UUID, course_id: UUID, concept_slugs: list[str] | None) -> None:
        """Dev-only: the undo for a demo auto-complete run. Wipes mastery, observations,
        and lesson-assignment state for the given concepts (every concept when None) back
        to a blank, never-attempted state."""
        ...


@dataclass
class SourceRecord:
    id: UUID
    owner_id: UUID
    filename: str
    storage_path: str
    status: str
    mime_type: str = "application/pdf"
    byte_size: int = 0


@dataclass
class CourseRecord:
    id: UUID
    owner_id: UUID
    title: str
    goal: str
    source_ids: list[UUID]
    status: str
    active_version: int
    updated_at: datetime
    quiz_max_attempts: int = 3
    lesson_min: int = 12
    lesson_max: int = 20
    language: str = "python"
    is_shared: bool = False


class MemoryCourseRepository:
    """Development-only adapter retained for isolated local tests."""

    name = "memory"

    def __init__(self) -> None:
        self.sources: dict[UUID, SourceRecord] = {}
        self.courses: dict[UUID, CourseRecord] = {}
        self.display_names: dict[UUID, str | None] = {}

    def create_source(self, owner_id: UUID, request: CreateSourceRequest) -> SourceUploadTarget:
        source_id = uuid4()
        safe_name = PurePosixPath(request.filename).name
        storage_path = f"{owner_id}/{source_id}/{safe_name}"
        self.sources[source_id] = SourceRecord(source_id, owner_id, safe_name, storage_path, "uploading", request.mime_type, request.byte_size)
        return SourceUploadTarget(
            id=source_id,
            storage_path=storage_path,
            upload_token="development-upload-token",
            status="uploading",
        )

    def complete_source(self, owner_id: UUID, source_id: UUID) -> SourceSummary:
        source = self._source_for_owner(owner_id, source_id)
        source.status = "uploaded"
        return SourceSummary(id=source.id, filename=source.filename, status="uploaded")

    def create_course(self, owner_id: UUID, request: CreateCourseRequest) -> CourseSummary:
        if request.lesson_min > request.lesson_max:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="Minimum lessons cannot exceed maximum lessons.")
        for source_id in request.source_ids:
            source = self._source_for_owner(owner_id, source_id)
            if source.status == "uploading":
                raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Source upload is not complete.")
            if source.status == "failed":
                raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Source ingestion failed.")

        now = datetime.now(UTC)
        course_id = uuid4()
        self.courses[course_id] = CourseRecord(
            id=course_id,
            owner_id=owner_id,
            title=request.title,
            goal=request.goal,
            source_ids=request.source_ids,
            status="draft",
            active_version=1,
            updated_at=now,
            quiz_max_attempts=request.quiz_max_attempts,
            lesson_min=request.lesson_min,
            lesson_max=request.lesson_max,
            language=request.language,
        )
        return self._summary(self.courses[course_id])

    def list_courses(self, owner_id: UUID) -> list[CourseSummary]:
        records = [record for record in self.courses.values() if record.owner_id == owner_id]
        return [self._summary(record) for record in sorted(records, key=lambda item: item.updated_at, reverse=True)]

    def get_course(self, owner_id: UUID, course_id: UUID) -> CourseSummary:
        return self._summary(self._course_for_owner(owner_id, course_id))

    def update_course(self, owner_id: UUID, course_id: UUID, request: UpdateCourseRequest) -> CourseSummary:
        course = self._course_for_owner(owner_id, course_id)
        if request.title is not None:
            course.title = request.title
        if request.quiz_max_attempts is not None:
            course.quiz_max_attempts = request.quiz_max_attempts
        if request.lesson_min is not None:
            course.lesson_min = request.lesson_min
        if request.lesson_max is not None:
            course.lesson_max = request.lesson_max
        if request.is_shared is not None:
            course.is_shared = request.is_shared
        course.updated_at = datetime.now(UTC)
        return self._summary(course)

    def import_course(self, owner_id: UUID, source_course_id: UUID) -> CourseSummary:
        source = self.courses.get(source_course_id)
        if source is None or not source.is_shared:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Shared course not found.")
        new_id = uuid4()
        self.courses[new_id] = CourseRecord(
            id=new_id,
            owner_id=owner_id,
            title=source.title,
            goal=source.goal,
            source_ids=list(source.source_ids),
            status="ready",
            active_version=1,
            updated_at=datetime.now(UTC),
            quiz_max_attempts=source.quiz_max_attempts,
            lesson_min=source.lesson_min,
            lesson_max=source.lesson_max,
            language=source.language,
            is_shared=False,
        )
        return self._summary(self.courses[new_id])

    def course_map(self, owner_id: UUID, course_id: UUID) -> CourseMapResponse:
        course = self._course_for_owner(owner_id, course_id)
        source_hash = sha256("".join(str(source_id) for source_id in course.source_ids).encode()).hexdigest()[:8]
        return CourseMapResponse(
            course_id=course.id,
            version=course.active_version,
            modules=[
                CourseMapModule(
                    title="Course modules",
                    position=1,
                    concepts=[
                        CourseMapConcept(slug="source-orientation", title="Orient to the source", kind="conceptual", summary_markdown=f"A cited course map generated from source set `{source_hash}`."),
                        CourseMapConcept(slug="robustness", title="Verify robust behavior", kind="conceptual", summary_markdown="A second lecture connects the pattern to realistic edge cases."),
                        CourseMapConcept(slug="core-pattern", title="Apply the core pattern", kind="coding", summary_markdown="The first coding lab will be generated by the lesson worker."),
                        CourseMapConcept(slug="topic-assessment", title="Check your understanding", kind="assessment", summary_markdown="An assessment checkpoint confirms you can apply the topic end to end."),
                    ],
                )
            ],
        )

    def course_progress(self, owner_id: UUID, course_id: UUID) -> CourseProgressResponse:
        course = self._course_for_owner(owner_id, course_id)
        source_count = len(course.source_ids)
        return CourseProgressResponse(
            course_id=course.id,
            stage="ready",
            sources_ready=source_count,
            sources_total=source_count,
            lessons_built=2,
            lessons_total=2,
        )

    def regenerate_course(self, owner_id: UUID, course_id: UUID) -> CourseSummary:
        return self._summary(self._course_for_owner(owner_id, course_id))

    def resume_course_lessons(self, owner_id: UUID, course_id: UUID) -> int:
        self._course_for_owner(owner_id, course_id)
        return 0

    def delete_course(self, owner_id: UUID, course_id: UUID) -> None:
        self._course_for_owner(owner_id, course_id)
        del self.courses[course_id]

    def concept_detail(self, owner_id: UUID, course_id: UUID, slug: str) -> ConceptDetailResponse:
        self._course_for_owner(owner_id, course_id)
        dummy_concepts = {
            "source-orientation": ("Orient to the source", "conceptual", "A cited course map generated from your sources."),
            "core-pattern": ("Apply the core pattern", "coding", "The first coding lab will be generated by the lesson worker."),
            "robustness": ("Verify robust behavior", "conceptual", "A second lecture connects the pattern to realistic edge cases."),
            "topic-assessment": ("Check your understanding", "assessment", "An assessment checkpoint confirms you can apply the topic end to end."),
        }
        if slug not in dummy_concepts:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Concept not found.")
        title, kind, summary = dummy_concepts[slug]
        return ConceptDetailResponse(slug=slug, title=title, kind=kind, summary_markdown=summary, citations=[], lesson=None)

    def lesson_workspace(
        self, owner_id: UUID, course_id: UUID, slug: str
    ) -> tuple[list[LessonWorkspaceFile], list[LessonWorkspaceFile], list[LessonWorkspaceFile], str]:
        self._course_for_owner(owner_id, course_id)
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="A generated lesson is required before it can run.")

    def quiz_item(self, owner_id: UUID, course_id: UUID, slug: str, item_id: str) -> dict[str, Any]:
        self._course_for_owner(owner_id, course_id)
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="A generated lesson is required before its quiz can be answered.")

    def quiz_progress(self, owner_id: UUID, course_id: UUID, slug: str, item_id: str) -> tuple[int, int, bool]:
        self._course_for_owner(owner_id, course_id)
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="A generated lesson is required before its quiz can be answered.")

    def record_quiz_response(
        self, owner_id: UUID, course_id: UUID, slug: str, item_id: str, answer: QuizAnswerRequest, grade: QuizGradeResponse
    ) -> int:
        self._course_for_owner(owner_id, course_id)
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="A generated lesson is required before its quiz can be answered.")

    def practice_session(
        self,
        owner_id: UUID,
        course_id: UUID,
        scope: PracticeScope,
        ids: list[str],
        count: int,
        order: PracticeOrder,
        filter: PracticeFilter,
        seed: int,
    ) -> PracticeSessionResponse:
        # No generated pool in memory mode, so the scope is simply empty rather than an error --
        # the practice surface degrades to "nothing to drill yet" like the rest of the UI.
        course = self._course_for_owner(owner_id, course_id)
        return PracticeSessionResponse(course_id=course.id, questions=[], scope_empty=True)

    def practice_item(self, owner_id: UUID, course_id: UUID, item_id: UUID) -> tuple[dict[str, Any], dict[str, Any]]:
        self._course_for_owner(owner_id, course_id)
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="A generated practice pool is required before it can be answered.")

    def record_practice_answer(
        self, owner_id: UUID, course_id: UUID, item_id: UUID, concept: dict[str, Any], correct: bool
    ) -> float | None:
        self._course_for_owner(owner_id, course_id)
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="A generated practice pool is required before it can be answered.")

    def request_practice_top_up(self, owner_id: UUID, course_id: UUID, concept_slugs: list[str]) -> list[str]:
        self._course_for_owner(owner_id, course_id)
        return []

    def complete_coding_lesson(self, owner_id: UUID, course_id: UUID, slug: str) -> None:
        self._course_for_owner(owner_id, course_id)

    def record_coding_submission(self, owner_id: UUID, course_id: UUID, slug: str, passed: bool) -> None:
        self._course_for_owner(owner_id, course_id)

    def course_mastery(self, owner_id: UUID, course_id: UUID) -> CourseMasteryResponse:
        course = self._course_for_owner(owner_id, course_id)
        return CourseMasteryResponse(course_id=course.id, threshold=MASTERY_THRESHOLD, concepts=[])

    def concept_prerequisites(self, owner_id: UUID, course_id: UUID, slug: str) -> PrerequisiteReviewResponse:
        course = self._course_for_owner(owner_id, course_id)
        return PrerequisiteReviewResponse(
            course_id=course.id, slug=slug, threshold=MASTERY_THRESHOLD,
            review_threshold=REVIEW_THRESHOLD, prerequisites=[], review_recommended=False,
        )

    def prerequisite_recommendation(self, owner_id: UUID, course_id: UUID, slug: str) -> PrerequisiteRecommendation | None:
        # No mastery or prerequisite graph in memory mode, so there is never anything to recommend.
        self._course_for_owner(owner_id, course_id)
        return None

    def list_recommendations(self, owner_id: UUID, course_id: UUID) -> RecommendationsResponse:
        course = self._course_for_owner(owner_id, course_id)
        return RecommendationsResponse(course_id=course.id, recommendations=[])

    def decide_recommendation(
        self, owner_id: UUID, course_id: UUID, event_id: UUID, decision: RecommendationDecision
    ) -> None:
        # No adaptation events exist in memory mode; validating ownership is all there is to do.
        self._course_for_owner(owner_id, course_id)

    def citation_excerpt(self, owner_id: UUID, course_id: UUID, citation_id: UUID) -> CitationExcerptResponse:
        self._course_for_owner(owner_id, course_id)
        # concept_detail() always returns citations=[] in memory mode, so this is unreachable from the UI.
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Citation not found.")

    def certificate(self, owner_id: UUID, course_id: UUID) -> CertificateResponse:
        self._course_for_owner(owner_id, course_id)
        # Memory mode never tracks real lesson completion, so a course here is never "done".
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="This course is not fully completed yet.")

    def public_certificate(self, certificate_id: UUID) -> CertificateResponse:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Certificate not found.")

    def profile(self, owner_id: UUID) -> ProfileResponse:
        return ProfileResponse(email="dev@example.com", display_name=self.display_names.get(owner_id))

    def update_profile(self, owner_id: UUID, request: UpdateProfileRequest) -> ProfileResponse:
        name = (request.display_name or "").strip() or None
        self.display_names[owner_id] = name
        return self.profile(owner_id)

    def course_sources(self, owner_id: UUID, course_id: UUID) -> list[CourseSourceSummary]:
        course = self._course_for_owner(owner_id, course_id)
        summaries = []
        for position, source_id in enumerate(course.source_ids, start=1):
            source = self.sources.get(source_id)
            if source is None:
                continue
            summaries.append(CourseSourceSummary(
                id=source.id, filename=source.filename, mime_type=source.mime_type,
                byte_size=source.byte_size, status=source.status, position=position,
            ))
        return summaries

    def source_download_url(self, owner_id: UUID, course_id: UUID, source_id: UUID) -> SourceDownloadResponse:
        course = self._course_for_owner(owner_id, course_id)
        if source_id not in course.source_ids:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Source not found.")
        source = self._source_for_owner(owner_id, source_id)
        return SourceDownloadResponse(
            filename=source.filename, mime_type=source.mime_type,
            download_url=f"https://development.invalid/dev-sources/{source.storage_path}",
        )

    def course_points(self, owner_id: UUID, course_id: UUID) -> CoursePointsResponse:
        course = self._course_for_owner(owner_id, course_id)
        return CoursePointsResponse(course_id=course.id, points_earned=0, points_total=0, points_per_lesson=POINTS_PER_LESSON)

    def regenerate_lesson(self, owner_id: UUID, course_id: UUID, slug: str) -> None:
        self._course_for_owner(owner_id, course_id)
        if slug not in {"core-pattern", "robustness"}:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Concept not found.")

    def clear_demo_progress(self, owner_id: UUID, course_id: UUID, concept_slugs: list[str] | None) -> None:
        # No mastery/observations/assignments exist in memory mode; validating ownership is
        # all there is to do.
        self._course_for_owner(owner_id, course_id)

    def _source_for_owner(self, owner_id: UUID, source_id: UUID) -> SourceRecord:
        source = self.sources.get(source_id)
        if source is None or source.owner_id != owner_id:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Source not found.")
        return source

    def _course_for_owner(self, owner_id: UUID, course_id: UUID) -> CourseRecord:
        course = self.courses.get(course_id)
        if course is None or course.owner_id != owner_id:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Course not found.")
        return course

    @staticmethod
    def _summary(course: CourseRecord) -> CourseSummary:
        return CourseSummary(
            id=course.id,
            title=course.title,
            goal=course.goal,
            status=course.status,
            active_version=course.active_version,
            updated_at=course.updated_at,
            quiz_max_attempts=course.quiz_max_attempts,
            lesson_min=course.lesson_min,
            lesson_max=course.lesson_max,
            language=course.language,
            is_shared=course.is_shared,
        )


class SupabaseCourseRepository:
    """Server-side adapter that applies explicit owner filters even with a service key."""

    name = "supabase"

    def __init__(self, client: Client) -> None:
        self.client = client

    def create_source(self, owner_id: UUID, request: CreateSourceRequest) -> SourceUploadTarget:
        source_id = uuid4()
        safe_name = PurePosixPath(request.filename).name
        storage_path = f"{owner_id}/{source_id}/{safe_name}"
        self._data(
            self.client.table("source_documents").insert(
                {
                    "id": str(source_id),
                    "owner_id": str(owner_id),
                    "filename": safe_name,
                    "mime_type": request.mime_type,
                    "byte_size": request.byte_size,
                    "storage_path": storage_path,
                    "status": "uploading",
                }
            ),
            "create source",
        )
        try:
            signed_upload = self.client.storage.from_("sources").create_signed_upload_url(storage_path)
        except Exception as exc:
            self._delete_source(owner_id, source_id)
            logger.exception("Could not create a signed source upload URL")
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="A secure upload could not be prepared. Please try again.",
            ) from exc
        return SourceUploadTarget(
            id=source_id,
            storage_path=storage_path,
            upload_token=signed_upload["token"],
            status="uploading",
        )

    def complete_source(self, owner_id: UUID, source_id: UUID) -> SourceSummary:
        source = self._source_for_owner(owner_id, source_id)
        if source["status"] == "uploaded":
            return self._enqueue_source_ingestion(owner_id, source_id, source["filename"])
        if source["status"] in {"ingesting", "ready"}:
            return SourceSummary(id=source_id, filename=source["filename"], status=source["status"])
        if source["status"] != "uploading":
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Source cannot be completed in its current state.")

        storage_path = PurePosixPath(source["storage_path"])
        objects = self._list_storage_objects(str(storage_path.parent), storage_path.name)
        uploaded_object = next((item for item in objects if item.get("name") == storage_path.name), None)
        if uploaded_object is None:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Source file upload could not be verified.")
        metadata = uploaded_object.get("metadata") or {}
        if self._stored_size(metadata) != source["byte_size"]:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Uploaded source size does not match the request.")
        stored_mime_type = metadata.get("mimetype")
        if stored_mime_type and stored_mime_type != source["mime_type"]:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Uploaded source type does not match the request.")

        self._data(
            self.client.table("source_documents")
            .update({"status": "uploaded", "updated_at": datetime.now(UTC).isoformat()})
            .eq("id", str(source_id))
            .eq("owner_id", str(owner_id)),
            "complete source",
        )
        return self._enqueue_source_ingestion(owner_id, source_id, source["filename"])

    def create_course(self, owner_id: UUID, request: CreateCourseRequest) -> CourseSummary:
        source_ids = list(dict.fromkeys(request.source_ids))
        source_rows: list[dict[str, Any]] = []
        if source_ids:
            source_rows = self._data(
                self.client.table("source_documents")
                .select("id,status")
                .eq("owner_id", str(owner_id))
                .in_("id", [str(source_id) for source_id in source_ids]),
                "validate course sources",
            )
        found_ids = {UUID(row["id"]) for row in source_rows}
        if found_ids != set(source_ids):
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Source not found.")
        if any(row["status"] == "uploading" for row in source_rows):
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Source upload is not complete.")
        if any(row["status"] == "failed" for row in source_rows):
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Source ingestion failed.")

        source_set_hash = sha256(":".join(sorted(str(source_id) for source_id in source_ids)).encode()).hexdigest()
        course_row = self._one(
            self._data(
                self.client.table("courses").insert(
                    {
                        "owner_id": str(owner_id),
                        "title": request.title,
                        "goal": request.goal,
                        "source_set_hash": source_set_hash,
                        "lesson_min": request.lesson_min,
                        "lesson_max": request.lesson_max,
                        "quiz_max_attempts": request.quiz_max_attempts,
                        "language": request.language,
                        "status": "draft",
                    }
                ),
                "create course",
            ),
            "Course",
        )
        course_id = UUID(course_row["id"])

        try:
            version_row = self._one(
                self._data(
                    self.client.table("course_versions").insert(
                        {"course_id": str(course_id), "version": 1, "status": "planning"}
                    ),
                    "create course version",
                ),
                "Course version",
            )
            self._data(
                self.client.table("courses")
                .update({"active_version_id": version_row["id"]})
                .eq("id", str(course_id))
                .eq("owner_id", str(owner_id)),
                "activate course version",
            )
            if source_ids:
                self._data(
                    self.client.table("course_sources").insert(
                        [
                            {
                                "course_id": str(course_id),
                                "source_document_id": str(source_id),
                                "position": position,
                            }
                            for position, source_id in enumerate(source_ids, start=1)
                        ]
                    ),
                    "attach course sources",
                )
            self._call(
                self.client.rpc(
                    "enqueue_course_planning",
                    {"p_course_id": str(course_id), "p_owner_id": str(owner_id)},
                ),
                "enqueue course planning",
            )
        except HTTPException:
            self._delete_course(owner_id, course_id)
            raise

        return CourseSummary(
            id=course_id,
            title=course_row["title"],
            goal=course_row["goal"],
            status="draft",
            active_version=1,
            updated_at=self._timestamp(course_row["updated_at"]),
            quiz_max_attempts=course_row["quiz_max_attempts"],
            lesson_min=course_row["lesson_min"],
            lesson_max=course_row["lesson_max"],
        )

    def list_courses(self, owner_id: UUID) -> list[CourseSummary]:
        courses = self._data(
            self.client.table("courses")
            .select("id,title,goal,status,active_version_id,updated_at,quiz_max_attempts,lesson_min,lesson_max,language,is_shared")
            .eq("owner_id", str(owner_id))
            .order("updated_at", desc=True),
            "list courses",
        )
        version_ids = [row["active_version_id"] for row in courses if row["active_version_id"]]
        versions = self._versions_for(version_ids)
        progress = self._lesson_progress_for(owner_id, version_ids)
        return [self._summary(row, versions, progress) for row in courses]

    def get_course(self, owner_id: UUID, course_id: UUID) -> CourseSummary:
        course = self._course_for_owner(owner_id, course_id)
        version_ids = [course["active_version_id"]] if course["active_version_id"] else []
        versions = self._versions_for(version_ids)
        progress = self._lesson_progress_for(owner_id, version_ids)
        return self._summary(course, versions, progress)

    def update_course(self, owner_id: UUID, course_id: UUID, request: UpdateCourseRequest) -> CourseSummary:
        self._course_for_owner(owner_id, course_id)
        payload: dict[str, Any] = {}
        if request.title is not None:
            payload["title"] = request.title
        if request.quiz_max_attempts is not None:
            payload["quiz_max_attempts"] = request.quiz_max_attempts
        if request.lesson_min is not None:
            payload["lesson_min"] = request.lesson_min
        if request.lesson_max is not None:
            payload["lesson_max"] = request.lesson_max
        if request.is_shared is not None:
            payload["is_shared"] = request.is_shared
        if payload:
            payload["updated_at"] = datetime.now(UTC).isoformat()
            self._data(
                self.client.table("courses").update(payload).eq("id", str(course_id)).eq("owner_id", str(owner_id)),
                "update course",
            )
        return self.get_course(owner_id, course_id)

    def import_course(self, owner_id: UUID, source_course_id: UUID) -> CourseSummary:
        try:
            result = self.client.rpc(
                "import_shared_course",
                {"p_source_course_id": str(source_course_id), "p_new_owner_id": str(owner_id)},
            ).execute()
        except (APIError, HTTPError) as exc:
            # P0002: the source is missing or not shared -- deliberately indistinguishable, so
            # an unshared id leaks nothing. P0001: it exists but is not finished building.
            code = getattr(exc, "code", None)
            if code == "P0002":
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Shared course not found.") from exc
            if code == "P0001":
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="That course is still being built and cannot be imported yet.",
                ) from exc
            logger.exception("Supabase request failed while attempting to import a shared course")
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="The course service is temporarily unavailable.",
            ) from exc

        new_course_id = result.data
        if isinstance(new_course_id, list):
            new_course_id = new_course_id[0] if new_course_id else None
        if not new_course_id:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Shared course not found.")
        return self.get_course(owner_id, UUID(str(new_course_id)))

    def course_map(self, owner_id: UUID, course_id: UUID) -> CourseMapResponse:
        course = self._course_for_owner(owner_id, course_id)
        version_id = course.get("active_version_id")
        if not version_id:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Course planning has not started.")
        version = self._one(
            self._data(
                self.client.table("course_versions")
                .select("id,version")
                .eq("id", version_id)
                .eq("course_id", str(course_id)),
                "load course version",
            ),
            "Course version",
        )
        modules = self._data(
            self.client.table("modules")
            .select("id,position,title")
            .eq("course_version_id", version_id)
            .order("position"),
            "load course modules",
        )
        concepts = self._data(
            self.client.table("concepts")
            .select("id,slug,title,kind")
            .eq("course_version_id", version_id)
            .order("slug"),
            "load course concepts",
        )
        summaries = self._summary_lookup([row["id"] for row in concepts])
        lesson_definitions = self._data(
            self.client.table("lesson_definitions")
            .select("id,module_id,concept_id")
            .eq("course_version_id", version_id)
            .eq("kind", "lesson"),
            "load lesson definitions",
        )
        module_id_by_concept_id = {row["concept_id"]: row["module_id"] for row in lesson_definitions}
        definition_id_by_concept_id = {row["concept_id"]: row["id"] for row in lesson_definitions}
        completed_definition_ids: set[str] = set()
        definition_ids = [row["id"] for row in lesson_definitions]
        if definition_ids:
            revisions = self._data(
                self.client.table("lesson_revisions")
                .select("id,lesson_definition_id,revision")
                .in_("lesson_definition_id", definition_ids)
                .order("revision", desc=True),
                "load lesson revisions for course map",
            )
            latest_revision_by_definition: dict[str, str] = {}
            for revision in revisions:
                latest_revision_by_definition.setdefault(revision["lesson_definition_id"], revision["id"])
            latest_revision_ids = list(latest_revision_by_definition.values())
            if latest_revision_ids:
                completed_assignments = self._data(
                    self.client.table("learner_lesson_assignments")
                    .select("lesson_revision_id")
                    .eq("user_id", str(owner_id))
                    .eq("status", "completed")
                    .in_("lesson_revision_id", latest_revision_ids),
                    "load completed lessons for course map",
                )
                completed_revisions = {row["lesson_revision_id"] for row in completed_assignments}
                completed_definition_ids = {
                    definition_id
                    for definition_id, revision_id in latest_revision_by_definition.items()
                    if revision_id in completed_revisions
                }

        concepts_by_module_id: dict[str, list[CourseMapConcept]] = {}
        for row in concepts:
            module_id = module_id_by_concept_id.get(row["id"])
            if module_id is None:
                continue
            concepts_by_module_id.setdefault(module_id, []).append(
                CourseMapConcept(
                    slug=row["slug"],
                    title=row["title"],
                    kind=row["kind"],
                    summary_markdown=summaries.get(row["id"], ""),
                    completed=definition_id_by_concept_id.get(row["id"]) in completed_definition_ids,
                )
            )

        return CourseMapResponse(
            course_id=course_id,
            version=version["version"],
            modules=[
                CourseMapModule(
                    title=module["title"],
                    position=module["position"],
                    concepts=sorted(
                        concepts_by_module_id.get(module["id"], []),
                        key=lambda concept: CONCEPT_KIND_PHASE.get(concept.kind, len(CONCEPT_KIND_PHASE)),
                    ),
                )
                for module in modules
            ],
        )

    def course_progress(self, owner_id: UUID, course_id: UUID) -> CourseProgressResponse:
        course = self._course_for_owner(owner_id, course_id)
        version_id = course.get("active_version_id")

        source_rows = self._data(
            self.client.table("course_sources").select("source_document_id").eq("course_id", str(course_id)),
            "load course sources",
        )
        source_ids = [row["source_document_id"] for row in source_rows]
        sources_total = len(source_ids)
        sources_ready = 0
        if source_ids:
            statuses = self._data(
                self.client.table("source_documents").select("status").in_("id", source_ids),
                "load source statuses",
            )
            sources_ready = sum(1 for row in statuses if row["status"] == "ready")

        if not version_id:
            return CourseProgressResponse(
                course_id=course_id, stage="planning",
                sources_ready=sources_ready, sources_total=sources_total,
                lessons_built=0, lessons_total=0,
            )

        version = self._one(
            self._data(
                self.client.table("course_versions").select("status").eq("id", version_id),
                "load course version status",
            ),
            "Course version",
        )
        version_status = version["status"]

        if version_status == "failed":
            return CourseProgressResponse(
                course_id=course_id, stage="failed",
                sources_ready=sources_ready, sources_total=sources_total,
                lessons_built=0, lessons_total=0,
            )

        if version_status in ("planning", "generating"):
            stage = "ingesting_sources" if sources_total > 0 and sources_ready < sources_total else "planning"
            return CourseProgressResponse(
                course_id=course_id, stage=stage,
                sources_ready=sources_ready, sources_total=sources_total,
                lessons_built=0, lessons_total=0,
            )

        lesson_concepts = self._data(
            self.client.table("concepts")
            .select("id,title")
            .eq("course_version_id", version_id),
            "load lesson concepts",
        )
        title_by_concept_id = {row["id"]: row["title"] for row in lesson_concepts}
        lessons_total = 0
        lessons_built = 0
        current_lesson_title: str | None = None
        lesson_rows: list[dict[str, Any]] = []
        if lesson_concepts:
            lesson_rows = self._data(
                self.client.table("lesson_definitions")
                .select("concept_id,build_status")
                .eq("kind", "lesson")
                .in_("concept_id", list(title_by_concept_id)),
                "load lesson build status",
            )
            lessons_total = len(lesson_rows)
            lessons_built = sum(1 for row in lesson_rows if row["build_status"] == "built")
            building_row = next((row for row in lesson_rows if row["build_status"] == "building"), None)
            if building_row:
                current_lesson_title = title_by_concept_id.get(building_row["concept_id"])

        incomplete_rows = [row for row in lesson_rows if row["build_status"] != "built"]
        has_active_or_queued_lesson = any(row["build_status"] in ("pending", "building") for row in incomplete_rows)
        has_terminal_lesson_failure = any(row["build_status"] == "failed" for row in incomplete_rows)
        stage = (
            "building_lessons"
            if lessons_total > 0 and lessons_built < lessons_total and has_active_or_queued_lesson
            else "failed"
            if lessons_total > 0 and lessons_built < lessons_total and has_terminal_lesson_failure
            else "ready"
        )
        return CourseProgressResponse(
            course_id=course_id, stage=stage,
            sources_ready=sources_ready, sources_total=sources_total,
            lessons_built=lessons_built, lessons_total=lessons_total,
            current_lesson_title=current_lesson_title,
        )

    def regenerate_course(self, owner_id: UUID, course_id: UUID) -> CourseSummary:
        self._course_for_owner(owner_id, course_id)
        try:
            self.client.rpc(
                "regenerate_course_planning",
                {"p_course_id": str(course_id), "p_owner_id": str(owner_id)},
            ).execute()
        except APIError as exc:
            if exc.code == "PGRST202":
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail="Course regeneration is not deployed yet. Apply migration 20260716005000_course_regeneration.sql.",
                ) from exc
            logger.exception("Supabase request failed while regenerating the course")
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="The course service is temporarily unavailable.",
            ) from exc
        except HTTPError as exc:
            logger.exception("Supabase request failed while regenerating the course")
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="The course service is temporarily unavailable.",
            ) from exc
        return self.get_course(owner_id, course_id)

    def resume_course_lessons(self, owner_id: UUID, course_id: UUID) -> int:
        self._course_for_owner(owner_id, course_id)
        try:
            response = self.client.rpc(
                "resume_course_lesson_builds",
                {"p_course_id": str(course_id), "p_owner_id": str(owner_id)},
            ).execute()
            return int(response.data or 0)
        except APIError as exc:
            if exc.code == "PGRST202":
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail="Resuming remaining lessons is not deployed yet. Apply migration 20260717120000_resume_remaining_lesson_builds.sql.",
                ) from exc
            logger.exception("Supabase request failed while resuming remaining lessons")
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="The course service is temporarily unavailable.",
            ) from exc
        except HTTPError as exc:
            logger.exception("Supabase request failed while resuming remaining lessons")
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="The course service is temporarily unavailable.",
            ) from exc

    def delete_course(self, owner_id: UUID, course_id: UUID) -> None:
        self._course_for_owner(owner_id, course_id)
        try:
            self.client.rpc(
                "delete_course",
                {"p_course_id": str(course_id), "p_owner_id": str(owner_id)},
            ).execute()
        except APIError as exc:
            if exc.code == "PGRST202":
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail="Course deletion is not deployed yet. Apply migration 20260716010000_course_deletion.sql.",
                ) from exc
            logger.exception("Supabase request failed while attempting to delete a course")
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="The course service is temporarily unavailable.",
            ) from exc
        except HTTPError as exc:
            logger.exception("Supabase request failed while attempting to delete a course")
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="The course service is temporarily unavailable.",
            ) from exc

    def concept_detail(self, owner_id: UUID, course_id: UUID, slug: str) -> ConceptDetailResponse:
        course = self._course_for_owner(owner_id, course_id)
        version_id = course.get("active_version_id")
        if not version_id:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Concept not found.")

        concept = self._one(
            self._data(
                self.client.table("concepts")
                .select("id,slug,title,kind")
                .eq("course_version_id", version_id)
                .eq("slug", slug),
                "load concept",
            ),
            "Concept",
        )
        summary_rows = self._data(
            self.client.table("concept_summaries")
            .select("summary_markdown,citations_json")
            .eq("concept_id", concept["id"]),
            "load concept summary",
        )
        summary_markdown = summary_rows[0]["summary_markdown"] if summary_rows else ""
        citations = summary_rows[0]["citations_json"] if summary_rows else []

        definition_query = (
            self.client.table("lesson_definitions")
            .select("id,build_status,generation_requested_at")
            .eq("course_version_id", version_id)
            .eq("concept_id", concept["id"])
            .eq("kind", "lesson")
        )
        try:
            definition_rows = definition_query.execute().data or []
        except APIError as exc:
            # Keep existing courses readable until the visibility migration is deployed.
            if exc.code != "42703":
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail="The course service is temporarily unavailable.",
                ) from exc
            definition_rows = self._data(
                self.client.table("lesson_definitions")
                .select("id,build_status")
                .eq("course_version_id", version_id)
                .eq("concept_id", concept["id"])
                .eq("kind", "lesson"),
                "load lesson definition",
            )
            for row in definition_rows:
                row["generation_requested_at"] = None
        definition = definition_rows[0] if definition_rows else None
        generation_status = (
            definition["build_status"]
            if definition and (concept["kind"] == "coding" or definition["generation_requested_at"] is not None)
            else None
        )

        lesson: LessonPreview | None = None
        if definition:
            revision_rows = self._data(
                self.client.table("lesson_revisions")
                .select("id,bundle_json")
                .eq("lesson_definition_id", definition["id"])
                .eq("validation_status", "validated")
                .order("revision", desc=True)
                .limit(1),
                "load lesson revision",
            )
            revision_id = revision_rows[0]["id"] if revision_rows else None
            bundle = revision_rows[0]["bundle_json"] if revision_rows else None
            view = bundle_view(bundle) if bundle else None
            # A reading-only activity without a quiz has no learner action to submit.
            # Viewing it is therefore its completion event; coding labs remain gated on
            # a passing submission even when they carry no quiz questions.
            if view and revision_id and concept["kind"] != "coding" and not view.quiz_items:
                assignment = self._ensure_assignment(owner_id, course_id, slug)
                if assignment["status"] != "completed":
                    self._data(
                        self.client.table("learner_lesson_assignments").update({"status": "completed"}).eq("id", assignment["id"]),
                        "complete viewed lesson assignment",
                    )
            # Conceptual concepts from courses planned before conceptual bundles existed
            # have a definition but no build and no bundle; they keep the summary-only view.
            if concept["kind"] == "coding" or generation_status is not None or view is not None:
                quiz_items = view.quiz_items if view else []
                if quiz_items and revision_id:
                    quiz_items = self._hydrate_quiz_progress(owner_id, revision_id, quiz_items)
                lesson = LessonPreview(
                    status=definition["build_status"],
                    title=view.title if view and view.title else concept["title"],
                    explanation_markdown=view.explanation_markdown if view else "",
                    starter_files=view.starter_files if view else [],
                    hints=view.hints if view else [],
                    public_test_files=view.public_test_files if view else [],
                    solution_files=view.solution_files if view else [],
                    worked_examples=view.worked_examples if view else [],
                    quiz_items=quiz_items,
                    quiz_max_attempts=course["quiz_max_attempts"],
                )

        return ConceptDetailResponse(
            slug=concept["slug"],
            title=concept["title"],
            kind=concept["kind"],
            summary_markdown=summary_markdown,
            citations=citations,
            generation_status=generation_status,
            lesson=lesson,
        )

    def lesson_workspace(
        self, owner_id: UUID, course_id: UUID, slug: str
    ) -> tuple[list[LessonWorkspaceFile], list[LessonWorkspaceFile], list[LessonWorkspaceFile], str]:
        view = bundle_view(self._built_lesson_bundle(owner_id, course_id, slug))
        # Read-only context files ride along with the hidden set so the sandbox has
        # them without the learner being required to submit them.
        return (view.starter_files, view.public_test_files, view.context_files + view.hidden_test_files, view.environment_id)

    def quiz_item(self, owner_id: UUID, course_id: UUID, slug: str, item_id: str) -> dict[str, Any]:
        _definition_id, _revision_id, bundle = self._built_lesson(owner_id, course_id, slug)
        items = (bundle.get("assessment") or {}).get("quiz_items") or []
        item = next((entry for entry in items if entry.get("id") == item_id), None)
        if item is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Quiz item not found.")
        return item

    def quiz_progress(self, owner_id: UUID, course_id: UUID, slug: str, item_id: str) -> tuple[int, int, bool]:
        course = self._course_for_owner(owner_id, course_id)
        assignment = self._ensure_assignment(owner_id, course_id, slug)
        responses = self._data(
            self.client.table("quiz_responses")
            .select("result")
            .eq("assignment_id", assignment["id"])
            .eq("quiz_item_id", item_id),
            "load quiz responses",
        )
        already_correct = any(row["result"] == "correct" for row in responses)
        return course["quiz_max_attempts"], len(responses), already_correct

    def record_quiz_response(
        self, owner_id: UUID, course_id: UUID, slug: str, item_id: str, answer: QuizAnswerRequest, grade: QuizGradeResponse
    ) -> int:
        assignment = self._ensure_assignment(owner_id, course_id, slug)
        prior = self._data(
            self.client.table("quiz_responses")
            .select("result")
            .eq("assignment_id", assignment["id"])
            .eq("quiz_item_id", item_id),
            "load quiz responses",
        )
        already_correct = any(row["result"] == "correct" for row in prior)
        self._data(
            self.client.table("quiz_responses").insert(
                {
                    "assignment_id": assignment["id"],
                    "quiz_item_id": item_id,
                    "idempotency_key": str(uuid4()),
                    # Both the raw answer and the full grade reveal are stored so a learner
                    # returning to an already-correct question sees exactly what they
                    # submitted and were shown, not just a bare pass/fail flag.
                    "response_json": {"answer": answer.model_dump(mode="json"), "grade": grade.model_dump(mode="json")},
                    "result": "correct" if grade.correct else "incorrect",
                }
            ),
            "record quiz response",
        )
        attempts_used = len(prior) + 1
        # Every assessed attempt (right or wrong) is one understand-track opportunity for the
        # lesson's concept -- except a replay of a question the learner already got right,
        # which would otherwise inflate mastery for free. See docs/IDEA.md mastery model.
        if not already_correct:
            item_kind = next(
                (
                    entry["kind"]
                    for entry in (assignment["bundle"].get("assessment") or {}).get("quiz_items") or []
                    if entry.get("id") == item_id
                ),
                "mcq",
            )
            concept = self._concept_for(owner_id, course_id, slug)
            self._record_observation(owner_id, concept["id"], assessment_for_quiz_kind(item_kind), grade.correct)
        if grade.correct and assignment["status"] != "completed":
            self._maybe_complete_assignment(assignment)
        return attempts_used

    def practice_session(
        self,
        owner_id: UUID,
        course_id: UUID,
        scope: PracticeScope,
        ids: list[str],
        count: int,
        order: PracticeOrder,
        filter: PracticeFilter,
        seed: int,
    ) -> PracticeSessionResponse:
        course = self._course_for_owner(owner_id, course_id)
        version_id = course.get("active_version_id")
        if not version_id:
            return PracticeSessionResponse(course_id=course_id, questions=[], scope_empty=True)

        concepts = self._practiceable_concepts(owner_id, version_id, scope, ids)
        if not concepts:
            return PracticeSessionResponse(course_id=course_id, questions=[], scope_empty=True)

        concept_by_id = {concept["id"]: concept for concept in concepts}
        rows = self._data(
            self.client.table("practice_items")
            .select("id,concept_id,kind,item_json")
            .in_("concept_id", list(concept_by_id))
            .order("batch")
            .order("created_at"),
            "load practice items",
        )
        # Items must reach the engine in course order: it treats their order as the course's.
        position = {concept["id"]: index for index, concept in enumerate(concepts)}
        rows.sort(key=lambda row: position[row["concept_id"]])
        items = [
            PracticeItem(id=row["id"], concept_id=row["concept_id"], kind=row["kind"])
            for row in rows
        ]
        attempts = self._practice_attempts(owner_id, list(concept_by_id))

        selected = select_practice_items(
            items,
            attempts,
            PracticeSession(count=count, order=order, filter=filter, seed=seed),
        )
        item_by_id = {row["id"]: row for row in rows}
        questions = [
            self._practice_question(item_by_id[item.id], concept_by_id[item.concept_id])
            for item in selected
        ]
        low = concepts_needing_top_up(items, attempts, concept_ids=list(concept_by_id))
        return PracticeSessionResponse(
            course_id=course_id,
            questions=questions,
            concepts_low_on_questions=[concept_by_id[concept_id]["slug"] for concept_id in low],
        )

    def practice_item(self, owner_id: UUID, course_id: UUID, item_id: UUID) -> tuple[dict[str, Any], dict[str, Any]]:
        course = self._course_for_owner(owner_id, course_id)
        version_id = course.get("active_version_id")
        if not version_id:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Practice question not found.")
        # Scoped to the caller's active version, so an item id from someone else's course --
        # or from a version this learner no longer sits on -- is a 404, not a leak.
        row = self._one(
            self._data(
                self.client.table("practice_items")
                .select("id,concept_id,item_json")
                .eq("id", str(item_id))
                .eq("course_version_id", version_id),
                "load practice item",
            ),
            "Practice question",
        )
        concept = self._one(
            self._data(
                self.client.table("concepts").select("id,slug,title,kind").eq("id", row["concept_id"]),
                "load practice concept",
            ),
            "Concept",
        )
        return row["item_json"], concept

    def record_practice_answer(
        self, owner_id: UUID, course_id: UUID, item_id: UUID, concept: dict[str, Any], correct: bool
    ) -> float | None:
        course = self._course_for_owner(owner_id, course_id)
        version_id = course["active_version_id"]
        # Every answer lands in the ledger, right or wrong: it drives non-repeat rotation,
        # weakest-first ordering, and the "retry my misses" filter.
        self._data(
            self.client.table("practice_attempts").insert(
                {
                    "user_id": str(owner_id),
                    "course_version_id": version_id,
                    "concept_id": concept["id"],
                    "practice_item_id": str(item_id),
                    "correct": correct,
                }
            ),
            "record practice attempt",
        )
        self._bump_practice_item_stats(item_id, correct)
        if not correct:
            # Positive-only: a wrong low-stakes answer records no observation, so practising
            # can never lower an estimate. The ledger row above still captures the struggle.
            return None
        self._record_observation(owner_id, concept["id"], "practice", True)
        rows = self._data(
            self.client.table("mastery")
            .select("p_l")
            .eq("user_id", str(owner_id))
            .eq("concept_id", concept["id"])
            .eq("track", "understand"),
            "load practice mastery",
        )
        return rows[0]["p_l"] if rows else None

    def request_practice_top_up(self, owner_id: UUID, course_id: UUID, concept_slugs: list[str]) -> list[str]:
        course = self._course_for_owner(owner_id, course_id)
        version_id = course.get("active_version_id")
        if not version_id or not concept_slugs:
            return []
        concepts = self._data(
            self.client.table("concepts")
            .select("id,slug")
            .eq("course_version_id", version_id)
            .in_("slug", concept_slugs),
            "load concepts for practice top-up",
        )
        if not concepts:
            return []
        definitions = self._data(
            self.client.table("lesson_definitions")
            .select("id,concept_id")
            .eq("course_version_id", version_id)
            .eq("kind", "lesson")
            .eq("build_status", "built")
            .in_("concept_id", [concept["id"] for concept in concepts]),
            "load lesson definitions for practice top-up",
        )
        slug_by_concept = {concept["id"]: concept["slug"] for concept in concepts}
        queued: list[str] = []
        for definition in definitions:
            try:
                self.client.rpc(
                    "enqueue_practice_pool_build",
                    {"p_lesson_definition_id": definition["id"]},
                ).execute()
            except (APIError, HTTPError):
                # Best-effort: a queue hiccup means no new batch this time, not a failed
                # practice session. The learner keeps whatever questions they already had.
                logger.exception(
                    "Could not enqueue a practice pool top-up",
                    extra={"lesson_definition_id": definition["id"]},
                )
                continue
            queued.append(slug_by_concept[definition["concept_id"]])
        return queued

    def _practiceable_concepts(
        self, owner_id: UUID, version_id: str, scope: PracticeScope, ids: list[str]
    ) -> list[dict[str, Any]]:
        """The concepts in scope that the learner has actually started, in course order.

        "Started" means they have an assignment for the lesson -- which is created the first
        time they answer a question or submit a lab. That is the closest thing this schema
        has to a progress marker (there is no ordering column on concepts), and it is what
        keeps practice from serving questions about a lesson the learner has not reached.
        """
        concepts = self._data(
            self.client.table("concepts").select("id,slug,title,kind").eq("course_version_id", version_id),
            "load concepts for practice",
        )
        if not concepts:
            return []
        ordered = self._concepts_in_course_order(version_id, concepts)
        started = self._started_concept_ids(owner_id, version_id)
        practiceable = [concept for concept in ordered if concept["id"] in started]
        if scope == "done":
            return practiceable
        if scope == "concepts":
            wanted = set(ids)
            return [concept for concept in practiceable if concept["slug"] in wanted]
        # scope == "modules": ids are module positions, which is what the course map shows.
        wanted_modules = {value for value in ids if value.isdigit()}
        modules = self._data(
            self.client.table("modules").select("id,position").eq("course_version_id", version_id),
            "load modules for practice",
        )
        module_ids = {module["id"] for module in modules if str(module["position"]) in wanted_modules}
        definitions = self._data(
            self.client.table("lesson_definitions")
            .select("concept_id,module_id")
            .eq("course_version_id", version_id)
            .eq("kind", "lesson"),
            "load lesson modules for practice",
        )
        in_modules = {row["concept_id"] for row in definitions if row["module_id"] in module_ids}
        return [concept for concept in practiceable if concept["id"] in in_modules]

    def _concepts_in_course_order(self, version_id: str, concepts: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Concepts sorted the way the course map presents them: by module position, then by
        the concept-kind phase, then slug. The engine reads this ordering as "course order"."""
        modules = self._data(
            self.client.table("modules").select("id,position").eq("course_version_id", version_id),
            "load modules for practice order",
        )
        position_by_module = {module["id"]: module["position"] for module in modules}
        definitions = self._data(
            self.client.table("lesson_definitions")
            .select("concept_id,module_id")
            .eq("course_version_id", version_id)
            .eq("kind", "lesson"),
            "load lesson definitions for practice order",
        )
        module_by_concept = {row["concept_id"]: row["module_id"] for row in definitions}
        return sorted(
            concepts,
            key=lambda concept: (
                position_by_module.get(module_by_concept.get(concept["id"]), 0),
                CONCEPT_KIND_PHASE.get(concept["kind"], 0),
                concept["slug"],
            ),
        )

    def _started_concept_ids(self, owner_id: UUID, version_id: str) -> set[str]:
        definitions = self._data(
            self.client.table("lesson_definitions")
            .select("id,concept_id")
            .eq("course_version_id", version_id)
            .eq("kind", "lesson"),
            "load lesson definitions for practice scope",
        )
        if not definitions:
            return set()
        revisions = self._data(
            self.client.table("lesson_revisions")
            .select("id,lesson_definition_id")
            .in_("lesson_definition_id", [definition["id"] for definition in definitions]),
            "load lesson revisions for practice scope",
        )
        if not revisions:
            return set()
        assignments = self._data(
            self.client.table("learner_lesson_assignments")
            .select("lesson_revision_id")
            .eq("user_id", str(owner_id))
            .in_("lesson_revision_id", [revision["id"] for revision in revisions]),
            "load assignments for practice scope",
        )
        assigned_revisions = {row["lesson_revision_id"] for row in assignments}
        definition_by_revision = {revision["id"]: revision["lesson_definition_id"] for revision in revisions}
        concept_by_definition = {definition["id"]: definition["concept_id"] for definition in definitions}
        return {
            concept_by_definition[definition_by_revision[revision_id]]
            for revision_id in assigned_revisions
            if revision_id in definition_by_revision
        }

    def _practice_attempts(self, owner_id: UUID, concept_ids: list[str]) -> list[PracticeAttempt]:
        rows = self._data(
            self.client.table("practice_attempts")
            .select("practice_item_id,concept_id,correct,created_at")
            .eq("user_id", str(owner_id))
            .in_("concept_id", concept_ids),
            "load practice attempts",
        )
        return [
            PracticeAttempt(
                item_id=row["practice_item_id"],
                concept_id=row["concept_id"],
                correct=row["correct"],
                created_at=self._timestamp(row["created_at"]),
            )
            for row in rows
        ]

    @staticmethod
    def _practice_question(row: dict[str, Any], concept: dict[str, Any]) -> PracticeQuestion:
        """Strip the stored question down to what the learner may see -- the same cut
        ``bundle_view`` makes for lesson quiz items."""
        item = row["item_json"]
        return PracticeQuestion(
            id=UUID(row["id"]),
            concept_slug=concept["slug"],
            concept_title=concept["title"],
            kind=item["kind"],
            prompt_markdown=item["prompt_markdown"],
            options=[QuizOptionPreview(text=option["text"]) for option in item.get("options") or []],
        )

    def _bump_practice_item_stats(self, item_id: UUID, correct: bool) -> None:
        """Roll this answer into the item's aggregate difficulty counters. Best-effort: the
        ledger row is the real record, and these are only a convenience for later tuning."""
        try:
            rows = (
                self.client.table("practice_items")
                .select("times_served,times_correct")
                .eq("id", str(item_id))
                .execute()
                .data
                or []
            )
            if not rows:
                return
            self.client.table("practice_items").update(
                {
                    "times_served": rows[0]["times_served"] + 1,
                    "times_correct": rows[0]["times_correct"] + (1 if correct else 0),
                }
            ).eq("id", str(item_id)).execute()
        except (APIError, HTTPError):
            logger.exception("Could not update practice item statistics", extra={"practice_item_id": str(item_id)})

    def complete_coding_lesson(self, owner_id: UUID, course_id: UUID, slug: str) -> None:
        assignment = self._ensure_assignment(owner_id, course_id, slug)
        if assignment["status"] != "completed":
            self._data(
                self.client.table("learner_lesson_assignments").update({"status": "completed"}).eq("id", assignment["id"]),
                "complete lesson assignment",
            )

    def record_coding_submission(self, owner_id: UUID, course_id: UUID, slug: str, passed: bool) -> None:
        # A deliberate Submit (visible + hidden suite) is the applied-skill observation --
        # recorded pass or fail so failed attempts count as opportunities, unlike Run.
        concept = self._concept_for(owner_id, course_id, slug)
        self._record_observation(owner_id, concept["id"], "coding_submission", passed)
        if passed:
            self.complete_coding_lesson(owner_id, course_id, slug)

    def course_mastery(self, owner_id: UUID, course_id: UUID) -> CourseMasteryResponse:
        course = self._course_for_owner(owner_id, course_id)
        version_id = course.get("active_version_id")
        if not version_id:
            return CourseMasteryResponse(course_id=course_id, threshold=MASTERY_THRESHOLD, concepts=[])
        concepts = self._data(
            self.client.table("concepts")
            .select("id,slug,title,kind")
            .eq("course_version_id", version_id)
            .order("slug"),
            "load concepts for mastery",
        )
        # Only concepts that actually carry a lesson can be assessed; skip planner-only nodes.
        lesson_concept_ids = {
            row["concept_id"]
            for row in self._data(
                self.client.table("lesson_definitions")
                .select("concept_id")
                .eq("course_version_id", version_id)
                .eq("kind", "lesson"),
                "load lesson definitions for mastery",
            )
        }
        mastery = self._mastery_rows(owner_id, [row["id"] for row in concepts if row["id"] in lesson_concept_ids])
        entries = [
            self._concept_mastery(concept, mastery)
            for concept in concepts
            if concept["id"] in lesson_concept_ids
        ]
        return CourseMasteryResponse(course_id=course_id, threshold=MASTERY_THRESHOLD, concepts=entries)

    def concept_prerequisites(self, owner_id: UUID, course_id: UUID, slug: str) -> PrerequisiteReviewResponse:
        course = self._course_for_owner(owner_id, course_id)
        version_id = course.get("active_version_id")
        concept = self._concept_for(owner_id, course_id, slug)
        # The whole transitive closure, not just direct parents: a lesson genuinely builds on the
        # things its prerequisites build on, so a weakness two hops back is worth flagging too.
        entries = self._ancestor_prerequisites(owner_id, version_id, concept["id"]) if version_id else []
        return PrerequisiteReviewResponse(
            course_id=course_id,
            slug=slug,
            threshold=MASTERY_THRESHOLD,
            review_threshold=REVIEW_THRESHOLD,
            prerequisites=entries,
            review_recommended=any(entry.needs_review for entry in entries),
        )

    def _ancestor_prerequisites(
        self, owner_id: UUID, version_id: str, concept_id: str
    ) -> list[PrerequisiteConcept]:
        """Every transitive prerequisite of a concept -- nearest-first, each carrying the learner's
        mastery and review flag. Loads the version's whole prerequisite graph once, walks the
        acyclic closure from ``concept_id``, then hydrates just the reachable ancestors."""
        version_concept_ids = [
            row["id"]
            for row in self._data(
                self.client.table("concepts").select("id").eq("course_version_id", version_id),
                "load version concepts",
            )
        ]
        if concept_id not in set(version_concept_ids):
            return []
        edges = self._data(
            self.client.table("concept_prerequisites")
            .select("concept_id,prerequisite_concept_id")
            .in_("concept_id", version_concept_ids),
            "load prerequisite edges",
        )
        adjacency: dict[str, list[str]] = {}
        for row in edges:
            adjacency.setdefault(row["concept_id"], []).append(row["prerequisite_concept_id"])
        ancestor_ids = _prerequisite_closure(adjacency, concept_id)
        if not ancestor_ids:
            return []
        by_id = {
            row["id"]: row
            for row in self._data(
                self.client.table("concepts").select("id,slug,title,kind").in_("id", ancestor_ids),
                "load prerequisite concepts",
            )
        }
        mastery = self._mastery_rows(owner_id, ancestor_ids)
        return [self._prerequisite_concept(by_id[cid], mastery) for cid in ancestor_ids if cid in by_id]

    def prerequisite_recommendation(
        self, owner_id: UUID, course_id: UUID, slug: str
    ) -> PrerequisiteRecommendation | None:
        """A prerequisite-review nudge for a learner who is struggling on this concept, or
        ``None`` when they are coping or nothing it builds on is shaky.

        Meant to be called right after a graded answer/submission has rolled mastery forward,
        so it reads the just-updated estimate. It combines two judgements the mastery model
        already makes: is the learner ``concept_struggling`` on *this* concept, and does it
        have a prerequisite that ``needs_review``. Only when both hold is a recommendation
        returned -- and logged as a proposed adaptation event for the audit trail."""
        concept = self._concept_for(owner_id, course_id, slug)
        own = self._mastery_rows(owner_id, [concept["id"]])
        understand = own.get((concept["id"], "understand"))
        apply = own.get((concept["id"], "apply"))
        if not concept_struggling(
            concept["kind"],
            understand["p_l"] if understand else None,
            apply["p_l"] if apply else None,
            understand["opportunities"] if understand else 0,
            apply["opportunities"] if apply else 0,
        ):
            return None
        course = self._course_for_owner(owner_id, course_id)
        version_id = course.get("active_version_id")
        if not version_id:
            return None
        # Walk the full prerequisite closure, then keep the shaky ones weakest-first so the most
        # broken foundation leads -- capped so a deep chain doesn't produce a wall of links.
        weak = [entry for entry in self._ancestor_prerequisites(owner_id, version_id, concept["id"]) if entry.needs_review]
        if not weak:
            return None
        weak.sort(key=_relevant_p)
        weak = weak[:MAX_RECOMMENDED_PREREQS]
        self._log_prerequisite_recommendation(owner_id, course_id, concept, weak)
        names = _join_titles([entry.title for entry in weak])
        return PrerequisiteRecommendation(
            concept_slug=concept["slug"],
            concept_title=concept["title"],
            reason_markdown=(
                f"This builds on {names}, which still looks shaky for you. "
                "A quick review there should make this concept click faster."
            ),
            prerequisites=weak,
        )

    def _log_prerequisite_recommendation(
        self, owner_id: UUID, course_id: UUID, concept: dict[str, Any], weak: list[PrerequisiteConcept]
    ) -> None:
        """Record the recommendation as a ``proposed`` adaptation event, deduped so a learner
        who keeps missing the same concept accrues one open proposal rather than one per
        attempt. Best-effort: a failure here is logged, never surfaced -- the inline nudge does
        not depend on the event being written."""
        try:
            course = self._course_for_owner(owner_id, course_id)
            version_id = course.get("active_version_id")
            if not version_id:
                return
            existing = (
                self.client.table("adaptation_events")
                .select("reason_json")
                .eq("user_id", str(owner_id))
                .eq("course_version_id", version_id)
                .eq("event_type", "prerequisite_review_recommended")
                .eq("decision", "proposed")
                .execute()
                .data
                or []
            )
            if any((row.get("reason_json") or {}).get("concept_slug") == concept["slug"] for row in existing):
                return
            self.client.table("adaptation_events").insert(
                {
                    "user_id": str(owner_id),
                    "course_version_id": version_id,
                    "event_type": "prerequisite_review_recommended",
                    "reason_json": {
                        "concept_slug": concept["slug"],
                        "prerequisite_slugs": [entry.slug for entry in weak],
                    },
                    "decision": "proposed",
                }
            ).execute()
        except (APIError, HTTPError):
            logger.exception(
                "Could not log prerequisite recommendation", extra={"concept_slug": concept["slug"]}
            )

    def list_recommendations(self, owner_id: UUID, course_id: UUID) -> RecommendationsResponse:
        """Open (``proposed``) prerequisite-review recommendations for the learner on this course,
        newest first. Each event stores only the target concept slug; its shaky prerequisites are
        re-resolved against *current* mastery, so a recommendation whose prerequisites have since
        been shored up simply drops out of the list instead of nagging."""
        course = self._course_for_owner(owner_id, course_id)
        version_id = course.get("active_version_id")
        if not version_id:
            return RecommendationsResponse(course_id=course_id, recommendations=[])
        events = self._data(
            self.client.table("adaptation_events")
            .select("id,reason_json,created_at")
            .eq("user_id", str(owner_id))
            .eq("course_version_id", version_id)
            .eq("event_type", "prerequisite_review_recommended")
            .eq("decision", "proposed")
            .order("created_at", desc=True),
            "load recommendations",
        )
        recommendations: list[RecommendationSummary] = []
        seen_concepts: set[str] = set()
        for event in events:
            concept_slug = (event.get("reason_json") or {}).get("concept_slug")
            if not concept_slug or concept_slug in seen_concepts:
                continue
            seen_concepts.add(concept_slug)
            concept_rows = self._data(
                self.client.table("concepts")
                .select("id,slug,title,kind")
                .eq("course_version_id", version_id)
                .eq("slug", concept_slug),
                "load recommendation concept",
            )
            if not concept_rows:
                continue
            concept = concept_rows[0]
            weak = [
                entry
                for entry in self._ancestor_prerequisites(owner_id, version_id, concept["id"])
                if entry.needs_review
            ]
            if not weak:
                continue
            weak.sort(key=_relevant_p)
            recommendations.append(
                RecommendationSummary(
                    id=event["id"],
                    concept_slug=concept["slug"],
                    concept_title=concept["title"],
                    prerequisites=weak,
                    created_at=event["created_at"],
                )
            )
        return RecommendationsResponse(course_id=course_id, recommendations=recommendations)

    def decide_recommendation(
        self, owner_id: UUID, course_id: UUID, event_id: UUID, decision: RecommendationDecision
    ) -> None:
        """Record the learner's verdict on a recommendation (accept / defer / decline). Verifies
        the event is the learner's own before updating so one learner can't act on another's."""
        self._course_for_owner(owner_id, course_id)
        owned = self._data(
            self.client.table("adaptation_events")
            .select("id")
            .eq("id", str(event_id))
            .eq("user_id", str(owner_id)),
            "load recommendation",
        )
        if not owned:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Recommendation not found.")
        self._data(
            self.client.table("adaptation_events").update({"decision": decision}).eq("id", str(event_id)),
            "decide recommendation",
        )

    def citation_excerpt(self, owner_id: UUID, course_id: UUID, citation_id: UUID) -> CitationExcerptResponse:
        self._course_for_owner(owner_id, course_id)
        chunk = self._one(
            self._data(
                self.client.table("source_chunks")
                .select("id,content,section,page_number,document_version_id")
                .eq("id", str(citation_id)),
                "load citation",
            ),
            "Citation",
        )
        version = self._one(
            self._data(
                self.client.table("source_document_versions")
                .select("document_id")
                .eq("id", chunk["document_version_id"]),
                "load citation source",
            ),
            "Citation",
        )
        # The course_sources match (not just source_documents.owner_id) is what proves this
        # citation belongs to *this* course, not merely to a source the caller owns elsewhere.
        attachment = self._one(
            self._data(
                self.client.table("course_sources")
                .select("source_documents(filename)")
                .eq("course_id", str(course_id))
                .eq("source_document_id", version["document_id"]),
                "load citation source attachment",
            ),
            "Citation",
        )
        return CitationExcerptResponse(
            id=citation_id,
            filename=attachment["source_documents"]["filename"],
            section=chunk["section"],
            page_number=chunk["page_number"],
            content=chunk["content"],
        )

    # Flat estimate, not measured time-on-task -- no such tracking exists yet (see
    # docs/product/PEDAGOGY_EVALUATION.md). Framed as "estimated" everywhere it's shown.
    _ESTIMATED_MINUTES_PER_LESSON = 18

    def _certificate_rows(self, course_id: UUID, owner_id: UUID) -> list[dict[str, Any]]:
        return self._data(
            self.client.table("certificates").select("id,issued_at").eq("course_id", str(course_id)).eq("owner_id", str(owner_id)),
            "load certificate record",
        )

    def _get_or_create_certificate_row(self, owner_id: UUID, course_id: UUID) -> dict[str, Any]:
        existing = self._certificate_rows(course_id, owner_id)
        if existing:
            return existing[0]
        try:
            inserted = self.client.table("certificates").insert(
                {"course_id": str(course_id), "owner_id": str(owner_id)}
            ).execute().data
        except APIError as exc:
            if getattr(exc, "code", None) != "23505":  # not a unique-violation
                logger.exception("Supabase request failed while attempting to issue certificate record")
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail="The course service is temporarily unavailable.",
                ) from exc
            inserted = None  # a concurrent call already inserted it -- fall through and re-read
        if inserted:
            return inserted[0]
        return self._one(self._certificate_rows(course_id, owner_id), "Certificate")

    def _build_certificate(self, certificate_row_id: str, course_id: UUID, owner_id: UUID, issued_at: str, course_title: str, course_goal: str) -> CertificateResponse:
        profile = self._one(
            self._data(self.client.table("profiles").select("email,display_name").eq("id", str(owner_id)), "load learner profile"),
            "Profile",
        )
        learner_name = profile.get("display_name") or profile["email"]
        course_map = self.course_map(owner_id, course_id)
        skills = [module.title for module in course_map.modules if module.concepts][:5]
        lessons_total = sum(len(module.concepts) for module in course_map.modules)
        estimated_hours = max(0.5, round(lessons_total * self._ESTIMATED_MINUTES_PER_LESSON / 60 * 2) / 2)
        # Deterministic, short display label -- separate from the durable link, which is
        # keyed on the certificates row id instead so it can't be recomputed/guessed.
        certificate_id = sha256(f"{course_id}:{owner_id}".encode()).hexdigest()[:12].upper()
        accent_color, accent_tint = accent_colors_for(course_title, course_goal)
        return CertificateResponse(
            course_id=course_id,
            course_title=course_title,
            learner_name=learner_name,
            issued_at=self._timestamp(issued_at) if isinstance(issued_at, str) else issued_at,
            certificate_id=certificate_id,
            verify_url=f"{get_settings().public_app_url.rstrip('/')}/certificates/{certificate_row_id}",
            skills=skills,
            estimated_hours=estimated_hours,
            accent_color=accent_color,
            accent_tint=accent_tint,
        )

    def certificate(self, owner_id: UUID, course_id: UUID) -> CertificateResponse:
        summary = self.get_course(owner_id, course_id)
        if summary.lessons_total == 0 or summary.lessons_completed < summary.lessons_total:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="This course is not fully completed yet.")
        row = self._get_or_create_certificate_row(owner_id, course_id)
        return self._build_certificate(row["id"], course_id, owner_id, row["issued_at"], summary.title, summary.goal)

    def public_certificate(self, certificate_id: UUID) -> CertificateResponse:
        row = self._one(
            self._data(
                self.client.table("certificates").select("id,course_id,owner_id,issued_at,courses(title,goal)").eq("id", str(certificate_id)),
                "load certificate record",
            ),
            "Certificate",
        )
        return self._build_certificate(
            row["id"], UUID(row["course_id"]), UUID(row["owner_id"]), row["issued_at"],
            row["courses"]["title"], row["courses"]["goal"],
        )

    def profile(self, owner_id: UUID) -> ProfileResponse:
        row = self._one(
            self._data(self.client.table("profiles").select("email,display_name").eq("id", str(owner_id)), "load profile"),
            "Profile",
        )
        return ProfileResponse(email=row["email"], display_name=row.get("display_name"))

    def update_profile(self, owner_id: UUID, request: UpdateProfileRequest) -> ProfileResponse:
        name = (request.display_name or "").strip() or None
        self._data(
            self.client.table("profiles").update({"display_name": name}).eq("id", str(owner_id)),
            "update profile",
        )
        return self.profile(owner_id)

    def course_sources(self, owner_id: UUID, course_id: UUID) -> list[CourseSourceSummary]:
        self._course_for_owner(owner_id, course_id)
        rows = self._data(
            self.client.table("course_sources")
            .select("position,source_documents(id,filename,mime_type,byte_size,status)")
            .eq("course_id", str(course_id))
            .order("position"),
            "load course sources",
        )
        return [
            CourseSourceSummary(
                id=row["source_documents"]["id"],
                filename=row["source_documents"]["filename"],
                mime_type=row["source_documents"]["mime_type"],
                byte_size=row["source_documents"]["byte_size"],
                status=row["source_documents"]["status"],
                position=row["position"],
            )
            for row in rows
        ]

    def source_download_url(self, owner_id: UUID, course_id: UUID, source_id: UUID) -> SourceDownloadResponse:
        self._course_for_owner(owner_id, course_id)
        # The course_sources match (not just source_documents.owner_id) is what proves this
        # source belongs to *this* course -- same reasoning as citation_excerpt above.
        attachment = self._one(
            self._data(
                self.client.table("course_sources")
                .select("source_documents(filename,mime_type,storage_path)")
                .eq("course_id", str(course_id))
                .eq("source_document_id", str(source_id)),
                "load source attachment",
            ),
            "Source",
        )
        document = attachment["source_documents"]
        try:
            signed = self.client.storage.from_("sources").create_signed_url(document["storage_path"], 300)
        except Exception as exc:
            logger.exception("Could not create a signed source download URL")
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="The source download could not be prepared. Please try again.",
            ) from exc
        return SourceDownloadResponse(filename=document["filename"], mime_type=document["mime_type"], download_url=signed["signedURL"])

    def course_points(self, owner_id: UUID, course_id: UUID) -> CoursePointsResponse:
        course = self._course_for_owner(owner_id, course_id)
        version_id = course.get("active_version_id")
        if not version_id:
            return CoursePointsResponse(course_id=course_id, points_earned=0, points_total=0, points_per_lesson=POINTS_PER_LESSON)

        definitions = self._data(
            self.client.table("lesson_definitions").select("id").eq("course_version_id", version_id).eq("kind", "lesson"),
            "load lesson definitions for points",
        )
        definition_ids = [row["id"] for row in definitions]
        points_total = len(definition_ids) * POINTS_PER_LESSON

        earned_definitions: set[str] = set()
        if definition_ids:
            revisions = self._data(
                self.client.table("lesson_revisions").select("id,lesson_definition_id").in_("lesson_definition_id", definition_ids),
                "load lesson revisions for points",
            )
            definition_by_revision = {row["id"]: row["lesson_definition_id"] for row in revisions}
            if definition_by_revision:
                completed = self._data(
                    self.client.table("learner_lesson_assignments")
                    .select("lesson_revision_id")
                    .eq("user_id", str(owner_id))
                    .eq("status", "completed")
                    .in_("lesson_revision_id", list(definition_by_revision)),
                    "load completed assignments",
                )
                earned_definitions = {
                    definition_by_revision[row["lesson_revision_id"]]
                    for row in completed
                    if row["lesson_revision_id"] in definition_by_revision
                }

        return CoursePointsResponse(
            course_id=course_id,
            points_earned=len(earned_definitions) * POINTS_PER_LESSON,
            points_total=points_total,
            points_per_lesson=POINTS_PER_LESSON,
        )

    def _hydrate_quiz_progress(self, owner_id: UUID, revision_id: str, quiz_items: list[QuizItemPreview]) -> list[QuizItemPreview]:
        """Read-only: shows prior progress if the learner already has an assignment for this
        revision, but never creates one just from viewing -- that happens on first answer."""
        assignment_rows = self._data(
            self.client.table("learner_lesson_assignments")
            .select("id")
            .eq("user_id", str(owner_id))
            .eq("lesson_revision_id", revision_id),
            "load lesson assignment",
        )
        if not assignment_rows:
            return quiz_items
        responses = self._data(
            self.client.table("quiz_responses")
            .select("quiz_item_id,result,response_json")
            .eq("assignment_id", assignment_rows[0]["id"])
            .order("created_at"),
            "load quiz responses",
        )
        attempts_used: dict[str, int] = {}
        correct: dict[str, bool] = {}
        correct_payload: dict[str, dict[str, Any]] = {}
        for row in responses:
            attempts_used[row["quiz_item_id"]] = attempts_used.get(row["quiz_item_id"], 0) + 1
            if row["result"] == "correct":
                correct[row["quiz_item_id"]] = True
                correct_payload[row["quiz_item_id"]] = row["response_json"]
        hydrated: list[QuizItemPreview] = []
        for item in quiz_items:
            update: dict[str, Any] = {"attempts_used": attempts_used.get(item.id, 0), "correct": correct.get(item.id)}
            payload = correct_payload.get(item.id)
            if payload:
                update["previous_answer"] = QuizAnswerRequest.model_validate(payload["answer"])
                update["previous_grade"] = QuizGradeResponse.model_validate(payload["grade"])
            hydrated.append(item.model_copy(update=update))
        return hydrated

    def _ensure_assignment(self, owner_id: UUID, course_id: UUID, slug: str) -> dict[str, Any]:
        """Lazily creates (or reuses) the learner's assignment for this lesson's current
        revision -- the durable anchor that quiz_responses and completion hang off of."""
        definition_id, revision_id, bundle = self._built_lesson(owner_id, course_id, slug)
        existing = self._assignment_rows(owner_id, revision_id)
        if not existing:
            try:
                self.client.table("learner_lesson_assignments").insert(
                    {"user_id": str(owner_id), "lesson_revision_id": revision_id, "route_kind": "canonical", "status": "assigned"}
                ).execute()
            except APIError as exc:
                if exc.code != "23505":  # another request already created it; safe to re-select
                    logger.exception("Supabase request failed while attempting to create lesson assignment")
                    raise HTTPException(
                        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                        detail="The course service is temporarily unavailable.",
                    ) from exc
            existing = self._assignment_rows(owner_id, revision_id)
        assignment = self._one(existing, "Assignment")
        return {"id": assignment["id"], "status": assignment["status"], "definition_id": definition_id, "bundle": bundle}

    def _assignment_rows(self, owner_id: UUID, revision_id: str) -> list[dict[str, Any]]:
        return self._data(
            self.client.table("learner_lesson_assignments")
            .select("id,status")
            .eq("user_id", str(owner_id))
            .eq("lesson_revision_id", revision_id),
            "load lesson assignment",
        )

    def _maybe_complete_assignment(self, assignment: dict[str, Any]) -> None:
        item_ids = {entry["id"] for entry in (assignment["bundle"].get("assessment") or {}).get("quiz_items") or []}
        if not item_ids:
            return
        responses = self._data(
            self.client.table("quiz_responses")
            .select("quiz_item_id")
            .eq("assignment_id", assignment["id"])
            .eq("result", "correct"),
            "load correct quiz responses",
        )
        correct_item_ids = {row["quiz_item_id"] for row in responses}
        if item_ids <= correct_item_ids:
            self._data(
                self.client.table("learner_lesson_assignments").update({"status": "completed"}).eq("id", assignment["id"]),
                "complete lesson assignment",
            )

    def _concept_for(self, owner_id: UUID, course_id: UUID, slug: str) -> dict[str, Any]:
        course = self._course_for_owner(owner_id, course_id)
        version_id = course.get("active_version_id")
        if not version_id:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Concept not found.")
        return self._one(
            self._data(
                self.client.table("concepts")
                .select("id,slug,title,kind")
                .eq("course_version_id", version_id)
                .eq("slug", slug),
                "load concept",
            ),
            "Concept",
        )

    def _record_observation(
        self,
        owner_id: UUID,
        concept_id: str,
        assessment_kind: AssessmentKind,
        correct: bool,
        support_level: str = "independent",
        evidence_id: str | None = None,
    ) -> None:
        """Append one BKT observation and roll the concept's mastery estimate forward.

        Best-effort: the graded answer / submission it derives from is already durable, and
        ``observations`` is an immutable ledger from which ``mastery`` could be recomputed, so
        a bookkeeping hiccup here is logged rather than surfaced as a failed answer."""
        if assessment_kind == "practice" and not correct:
            # Positive-only credit: a wrong answer in a low-stakes drill is how practice is
            # meant to work, so it records nothing at all rather than lowering the estimate.
            # The practice_attempts ledger is where that miss is remembered.
            return
        track = track_for(assessment_kind)
        params = params_for(assessment_kind)
        try:
            existing = (
                self.client.table("mastery")
                .select("p_l,opportunities")
                .eq("user_id", str(owner_id))
                .eq("concept_id", concept_id)
                .eq("track", track)
                .execute()
                .data
                or []
            )
            current_p_l = existing[0]["p_l"] if existing else params.p_l0
            opportunities = (existing[0]["opportunities"] if existing else 0) + 1
            p_l_new = (
                practice_update(current_p_l, params)
                if assessment_kind == "practice"
                else bkt_update(current_p_l, correct, params)
            )
            self.client.table("observations").insert(
                {
                    "user_id": str(owner_id),
                    "concept_id": concept_id,
                    "track": track,
                    "assessment_kind": assessment_kind,
                    "result": "correct" if correct else "incorrect",
                    "support_level": support_level,
                    "evidence_id": evidence_id,
                }
            ).execute()
            self.client.table("mastery").upsert(
                {
                    "user_id": str(owner_id),
                    "concept_id": concept_id,
                    "track": track,
                    "p_l": p_l_new,
                    "opportunities": opportunities,
                    "last_update": datetime.now(UTC).isoformat(),
                },
                on_conflict="user_id,concept_id,track",
            ).execute()
        except (APIError, HTTPError):
            logger.exception(
                "Could not record mastery observation", extra={"concept_id": str(concept_id), "track": track}
            )

    def _mastery_rows(self, owner_id: UUID, concept_ids: Sequence[str]) -> dict[tuple[str, str], dict[str, Any]]:
        """Learner mastery rows keyed by ``(concept_id, track)`` for a set of concepts."""
        if not concept_ids:
            return {}
        rows = self._data(
            self.client.table("mastery")
            .select("concept_id,track,p_l,opportunities")
            .eq("user_id", str(owner_id))
            .in_("concept_id", list(concept_ids)),
            "load mastery",
        )
        return {(row["concept_id"], row["track"]): row for row in rows}

    @staticmethod
    def _concept_mastery(concept: dict[str, Any], mastery: dict[tuple[str, str], dict[str, Any]]) -> ConceptMastery:
        understand = mastery.get((concept["id"], "understand"))
        apply = mastery.get((concept["id"], "apply"))
        p_understand = understand["p_l"] if understand else None
        p_apply = apply["p_l"] if apply else None
        return ConceptMastery(
            slug=concept["slug"],
            title=concept["title"],
            kind=concept["kind"],
            p_understand=p_understand,
            p_apply=p_apply,
            understand_opportunities=understand["opportunities"] if understand else 0,
            apply_opportunities=apply["opportunities"] if apply else 0,
            mastered=concept_mastered(concept["kind"], p_understand, p_apply),
        )

    @staticmethod
    def _prerequisite_concept(concept: dict[str, Any], mastery: dict[tuple[str, str], dict[str, Any]]) -> PrerequisiteConcept:
        understand = mastery.get((concept["id"], "understand"))
        apply = mastery.get((concept["id"], "apply"))
        p_understand = understand["p_l"] if understand else None
        p_apply = apply["p_l"] if apply else None
        return PrerequisiteConcept(
            slug=concept["slug"],
            title=concept["title"],
            kind=concept["kind"],
            p_understand=p_understand,
            p_apply=p_apply,
            mastered=concept_mastered(concept["kind"], p_understand, p_apply),
            needs_review=prerequisite_needs_review(
                concept["kind"],
                p_understand,
                p_apply,
                understand["opportunities"] if understand else 0,
                apply["opportunities"] if apply else 0,
            ),
        )

    def _built_lesson(self, owner_id: UUID, course_id: UUID, slug: str) -> tuple[str, str, dict[str, Any]]:
        course = self._course_for_owner(owner_id, course_id)
        version_id = course.get("active_version_id")
        if not version_id:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lesson not found.")
        rows = self._data(
            self.client.table("lesson_definitions")
            .select("id,build_status,concepts!inner(slug)")
            .eq("course_version_id", version_id)
            .eq("kind", "lesson")
            .eq("concepts.slug", slug),
            "load lesson definition",
        )
        definition = self._one(rows, "Lesson")
        if definition["build_status"] != "built":
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="This lesson is still being built.")
        revisions = self._data(
            self.client.table("lesson_revisions")
            .select("id,bundle_json")
            .eq("lesson_definition_id", definition["id"])
            .eq("validation_status", "validated")
            .order("revision", desc=True)
            .limit(1),
            "load lesson revision",
        )
        revision = self._one(revisions, "Lesson revision")
        return definition["id"], revision["id"], revision["bundle_json"]

    def _built_lesson_bundle(self, owner_id: UUID, course_id: UUID, slug: str) -> dict[str, Any]:
        return self._built_lesson(owner_id, course_id, slug)[2]

    def regenerate_lesson(self, owner_id: UUID, course_id: UUID, slug: str) -> None:
        try:
            self.client.rpc(
                "regenerate_lesson_build",
                {"p_course_id": str(course_id), "p_owner_id": str(owner_id), "p_concept_slug": slug},
            ).execute()
        except APIError as exc:
            if exc.code == "PGRST202":
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail="Lesson regeneration is not deployed yet. Apply migration 20260716007000_lesson_regeneration.sql.",
                ) from exc
            logger.exception("Supabase request failed while attempting to regenerate a lesson")
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="The course service is temporarily unavailable.",
            ) from exc
        except HTTPError as exc:
            logger.exception("Supabase request failed while attempting to regenerate a lesson")
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="The course service is temporarily unavailable.",
            ) from exc

    def clear_demo_progress(self, owner_id: UUID, course_id: UUID, concept_slugs: list[str] | None) -> None:
        course = self._course_for_owner(owner_id, course_id)
        version_id = course.get("active_version_id")
        if not version_id:
            return
        concepts_query = self.client.table("concepts").select("id").eq("course_version_id", version_id)
        if concept_slugs is not None:
            concepts_query = concepts_query.in_("slug", concept_slugs)
        concept_ids = [row["id"] for row in self._data(concepts_query, "load concepts for demo clear")]
        if not concept_ids:
            return
        definition_ids = [
            row["id"]
            for row in self._data(
                self.client.table("lesson_definitions").select("id").in_("concept_id", concept_ids),
                "load lesson definitions for demo clear",
            )
        ]
        if definition_ids:
            revision_ids = [
                row["id"]
                for row in self._data(
                    self.client.table("lesson_revisions").select("id").in_("lesson_definition_id", definition_ids),
                    "load lesson revisions for demo clear",
                )
            ]
            # Deleting the assignment cascades its quiz_responses and submissions rows too
            # (both FKs are ON DELETE CASCADE), so neither needs a separate delete here.
            if revision_ids:
                self._data(
                    self.client.table("learner_lesson_assignments")
                    .delete()
                    .eq("user_id", str(owner_id))
                    .in_("lesson_revision_id", revision_ids),
                    "clear lesson assignments for demo clear",
                )
        self._data(
            self.client.table("observations").delete().eq("user_id", str(owner_id)).in_("concept_id", concept_ids),
            "clear observations for demo clear",
        )
        self._data(
            self.client.table("mastery").delete().eq("user_id", str(owner_id)).in_("concept_id", concept_ids),
            "clear mastery for demo clear",
        )

    def _source_for_owner(self, owner_id: UUID, source_id: UUID) -> dict[str, Any]:
        return self._one(
            self._data(
                self.client.table("source_documents")
                .select("id,filename,mime_type,byte_size,storage_path,status")
                .eq("id", str(source_id))
                .eq("owner_id", str(owner_id)),
                "load source",
            ),
            "Source",
        )

    def _course_for_owner(self, owner_id: UUID, course_id: UUID) -> dict[str, Any]:
        return self._one(
            self._data(
                self.client.table("courses")
                .select("id,title,goal,status,active_version_id,updated_at,quiz_max_attempts,lesson_min,lesson_max,language,is_shared")
                .eq("id", str(course_id))
                .eq("owner_id", str(owner_id)),
                "load course",
            ),
            "Course",
        )

    def _versions_for(self, version_ids: Sequence[str]) -> dict[str, int]:
        if not version_ids:
            return {}
        rows = self._data(
            self.client.table("course_versions").select("id,version").in_("id", list(version_ids)),
            "load course versions",
        )
        return {row["id"]: row["version"] for row in rows}

    def _lesson_progress_for(self, owner_id: UUID, version_ids: Sequence[str]) -> dict[str, tuple[int, int]]:
        """{version_id: (lessons_completed, lessons_total)}, batched into 3 queries total
        regardless of how many courses are being listed -- mirrors course_points()."""
        if not version_ids:
            return {}
        definitions = self._data(
            self.client.table("lesson_definitions")
            .select("id,course_version_id")
            .in_("course_version_id", list(version_ids))
            .eq("kind", "lesson"),
            "load lesson definitions for progress",
        )
        total_by_version: dict[str, int] = {}
        version_by_definition: dict[str, str] = {}
        for row in definitions:
            version_by_definition[row["id"]] = row["course_version_id"]
            total_by_version[row["course_version_id"]] = total_by_version.get(row["course_version_id"], 0) + 1

        completed_by_version: dict[str, int] = {}
        definition_ids = list(version_by_definition)
        if definition_ids:
            revisions = self._data(
                self.client.table("lesson_revisions")
                .select("id,lesson_definition_id")
                .in_("lesson_definition_id", definition_ids),
                "load lesson revisions for progress",
            )
            definition_by_revision = {row["id"]: row["lesson_definition_id"] for row in revisions}
            if definition_by_revision:
                completed = self._data(
                    self.client.table("learner_lesson_assignments")
                    .select("lesson_revision_id")
                    .eq("user_id", str(owner_id))
                    .eq("status", "completed")
                    .in_("lesson_revision_id", list(definition_by_revision)),
                    "load completed assignments for progress",
                )
                seen: set[str] = set()
                for row in completed:
                    definition_id = definition_by_revision.get(row["lesson_revision_id"])
                    if not definition_id or definition_id in seen:
                        continue
                    seen.add(definition_id)
                    version_id = version_by_definition[definition_id]
                    completed_by_version[version_id] = completed_by_version.get(version_id, 0) + 1

        return {
            version_id: (completed_by_version.get(version_id, 0), total)
            for version_id, total in total_by_version.items()
        }

    def _summary_lookup(self, concept_ids: Sequence[str]) -> dict[str, str]:
        if not concept_ids:
            return {}
        rows = self._data(
            self.client.table("concept_summaries")
            .select("concept_id,summary_markdown")
            .in_("concept_id", list(concept_ids)),
            "load concept summaries",
        )
        return {row["concept_id"]: row["summary_markdown"] for row in rows}

    def _delete_course(self, owner_id: UUID, course_id: UUID) -> None:
        try:
            self.client.table("courses").delete().eq("id", str(course_id)).eq("owner_id", str(owner_id)).execute()
        except (APIError, HTTPError):
            logger.exception("Could not clean up failed course creation", extra={"course_id": str(course_id)})

    def _delete_source(self, owner_id: UUID, source_id: UUID) -> None:
        try:
            self.client.table("source_documents").delete().eq("id", str(source_id)).eq("owner_id", str(owner_id)).execute()
        except (APIError, HTTPError):
            logger.exception("Could not clean up failed source creation", extra={"source_id": str(source_id)})

    def _enqueue_source_ingestion(self, owner_id: UUID, source_id: UUID, filename: str) -> SourceSummary:
        self._call(
            self.client.rpc(
                "enqueue_source_ingestion",
                {"p_source_id": str(source_id), "p_owner_id": str(owner_id)},
            ),
            "enqueue source ingestion",
        )
        return SourceSummary(id=source_id, filename=filename, status="ingesting")

    def _list_storage_objects(self, folder: str, filename: str) -> list[dict[str, Any]]:
        try:
            return self.client.storage.from_("sources").list(folder, {"limit": 1, "search": filename})
        except Exception as exc:
            logger.exception("Could not verify a source upload in Storage")
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="The source upload could not be verified. Please try again.",
            ) from exc

    def _data(self, request: Any, action: str) -> list[dict[str, Any]]:
        try:
            return request.execute().data or []
        except (APIError, HTTPError) as exc:
            logger.exception("Supabase request failed while attempting to %s", action)
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="The course service is temporarily unavailable.",
            ) from exc

    @staticmethod
    def _call(request: Any, action: str) -> None:
        try:
            request.execute()
        except (APIError, HTTPError) as exc:
            logger.exception("Supabase request failed while attempting to %s", action)
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="The course service is temporarily unavailable.",
            ) from exc

    @staticmethod
    def _one(rows: list[dict[str, Any]], resource_name: str) -> dict[str, Any]:
        if not rows:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"{resource_name} not found.")
        return rows[0]

    @staticmethod
    def _timestamp(value: str) -> datetime:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))

    @staticmethod
    def _stored_size(metadata: dict[str, Any]) -> int | None:
        value = metadata.get("size")
        try:
            return int(value)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _summary(row: dict[str, Any], versions: dict[str, int], progress: dict[str, tuple[int, int]] | None = None) -> CourseSummary:
        active_version_id = row.get("active_version_id")
        if not active_version_id or active_version_id not in versions:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Course version is unavailable.")
        completed, total = (progress or {}).get(active_version_id, (0, 0))
        return CourseSummary(
            id=UUID(row["id"]),
            title=row["title"],
            goal=row["goal"],
            status=row["status"],
            active_version=versions[active_version_id],
            updated_at=SupabaseCourseRepository._timestamp(row["updated_at"]),
            quiz_max_attempts=row["quiz_max_attempts"],
            lesson_min=row["lesson_min"],
            lesson_max=row["lesson_max"],
            lessons_completed=completed,
            lessons_total=total,
            language=row.get("language", "python"),
            is_shared=row.get("is_shared", False),
        )


_memory_repository = MemoryCourseRepository()


def get_repository() -> CourseRepository:
    if get_settings().repository_backend == "supabase":
        return SupabaseCourseRepository(get_service_client())
    return _memory_repository
