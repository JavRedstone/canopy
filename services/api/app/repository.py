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

from app.lesson_bundle import bundle_view
from app.mastery import (
    AssessmentKind,
    assessment_for_quiz_kind,
    bkt_update,
    concept_mastered,
    params_for,
    prerequisite_needs_review,
    track_for,
    MASTERY_THRESHOLD,
    REVIEW_THRESHOLD,
)
from app.schemas import ConceptDetailResponse, ConceptMastery, CoursePointsResponse, CourseMapConcept, CourseMapModule, CourseMapResponse, CourseMasteryResponse, CourseProgressResponse, CourseSummary, CreateCourseRequest, CreateSourceRequest, LessonPreview, LessonWorkspaceFile, PrerequisiteConcept, PrerequisiteReviewResponse, QuizAnswerRequest, QuizGradeResponse, QuizItemPreview, SourceSummary, SourceUploadTarget, UpdateCourseRequest
from app.settings import get_settings
from app.supabase import get_service_client


logger = logging.getLogger(__name__)

# A fixed award per lesson (a coding lab passed via Submit, or every item in a
# conceptual lesson's mastery check answered correctly) -- a coarse, gamified
# completion signal. Not configurable yet; see CourseSummary.quiz_max_attempts for
# the one course-level knob this pass wires up.
POINTS_PER_LESSON = 10


class CourseRepository(Protocol):
    name: str

    def create_source(self, owner_id: UUID, request: CreateSourceRequest) -> SourceUploadTarget: ...

    def complete_source(self, owner_id: UUID, source_id: UUID) -> SourceSummary: ...

    def create_course(self, owner_id: UUID, request: CreateCourseRequest) -> CourseSummary: ...

    def list_courses(self, owner_id: UUID) -> list[CourseSummary]: ...

    def get_course(self, owner_id: UUID, course_id: UUID) -> CourseSummary: ...

    def update_course(self, owner_id: UUID, course_id: UUID, request: UpdateCourseRequest) -> CourseSummary: ...

    def course_map(self, owner_id: UUID, course_id: UUID) -> CourseMapResponse: ...

    def course_progress(self, owner_id: UUID, course_id: UUID) -> CourseProgressResponse: ...

    def regenerate_course(self, owner_id: UUID, course_id: UUID) -> CourseSummary: ...

    def resume_course_lessons(self, owner_id: UUID, course_id: UUID) -> int: ...

    def delete_course(self, owner_id: UUID, course_id: UUID) -> None: ...

    def concept_detail(self, owner_id: UUID, course_id: UUID, slug: str) -> ConceptDetailResponse: ...

    def lesson_workspace(
        self, owner_id: UUID, course_id: UUID, slug: str
    ) -> tuple[list[LessonWorkspaceFile], list[LessonWorkspaceFile], list[LessonWorkspaceFile]]: ...

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

    def course_points(self, owner_id: UUID, course_id: UUID) -> CoursePointsResponse: ...

    def regenerate_lesson(self, owner_id: UUID, course_id: UUID, slug: str) -> None: ...


@dataclass
class SourceRecord:
    id: UUID
    owner_id: UUID
    filename: str
    storage_path: str
    status: str


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


class MemoryCourseRepository:
    """Development-only adapter retained for isolated local tests."""

    name = "memory"

    def __init__(self) -> None:
        self.sources: dict[UUID, SourceRecord] = {}
        self.courses: dict[UUID, CourseRecord] = {}

    def create_source(self, owner_id: UUID, request: CreateSourceRequest) -> SourceUploadTarget:
        source_id = uuid4()
        safe_name = PurePosixPath(request.filename).name
        storage_path = f"{owner_id}/{source_id}/{safe_name}"
        self.sources[source_id] = SourceRecord(source_id, owner_id, safe_name, storage_path, "uploading")
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
        course.updated_at = datetime.now(UTC)
        return self._summary(course)

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
                        CourseMapConcept(slug="core-pattern", title="Apply the core pattern", kind="coding", summary_markdown="The first coding lab will be generated by the lesson worker."),
                        CourseMapConcept(slug="robustness", title="Verify robust behavior", kind="conceptual", summary_markdown="A second lecture connects the pattern to realistic edge cases."),
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
    ) -> tuple[list[LessonWorkspaceFile], list[LessonWorkspaceFile], list[LessonWorkspaceFile]]:
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

    def course_points(self, owner_id: UUID, course_id: UUID) -> CoursePointsResponse:
        course = self._course_for_owner(owner_id, course_id)
        return CoursePointsResponse(course_id=course.id, points_earned=0, points_total=0, points_per_lesson=POINTS_PER_LESSON)

    def regenerate_lesson(self, owner_id: UUID, course_id: UUID, slug: str) -> None:
        self._course_for_owner(owner_id, course_id)
        if slug not in {"core-pattern", "robustness"}:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Concept not found.")

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
        )

    def list_courses(self, owner_id: UUID) -> list[CourseSummary]:
        courses = self._data(
            self.client.table("courses")
            .select("id,title,goal,status,active_version_id,updated_at,quiz_max_attempts")
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
        versions = self._versions_for([course["active_version_id"]] if course["active_version_id"] else [])
        return self._summary(course, versions)

    def update_course(self, owner_id: UUID, course_id: UUID, request: UpdateCourseRequest) -> CourseSummary:
        self._course_for_owner(owner_id, course_id)
        payload: dict[str, Any] = {}
        if request.title is not None:
            payload["title"] = request.title
        if request.quiz_max_attempts is not None:
            payload["quiz_max_attempts"] = request.quiz_max_attempts
        if payload:
            payload["updated_at"] = datetime.now(UTC).isoformat()
            self._data(
                self.client.table("courses").update(payload).eq("id", str(course_id)).eq("owner_id", str(owner_id)),
                "update course",
            )
        return self.get_course(owner_id, course_id)

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
                    concepts=concepts_by_module_id.get(module["id"], []),
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

        stage = "building_lessons" if lessons_total > 0 and lessons_built < lessons_total else "ready"
        return CourseProgressResponse(
            course_id=course_id, stage=stage,
            sources_ready=sources_ready, sources_total=sources_total,
            lessons_built=lessons_built, lessons_total=lessons_total,
            current_lesson_title=current_lesson_title,
        )

    def regenerate_course(self, owner_id: UUID, course_id: UUID) -> CourseSummary:
        self._course_for_owner(owner_id, course_id)
        self._call(
            self.client.rpc(
                "regenerate_course_planning",
                {"p_course_id": str(course_id), "p_owner_id": str(owner_id)},
            ),
            "regenerate course planning",
        )
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
    ) -> tuple[list[LessonWorkspaceFile], list[LessonWorkspaceFile], list[LessonWorkspaceFile]]:
        view = bundle_view(self._built_lesson_bundle(owner_id, course_id, slug))
        # Read-only context files ride along with the hidden set so the sandbox has
        # them without the learner being required to submit them.
        return (view.starter_files, view.public_test_files, view.context_files + view.hidden_test_files)

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
        concept = self._concept_for(owner_id, course_id, slug)
        edges = self._data(
            self.client.table("concept_prerequisites")
            .select("prerequisite_concept_id")
            .eq("concept_id", concept["id"]),
            "load concept prerequisites",
        )
        prerequisite_ids = [row["prerequisite_concept_id"] for row in edges]
        if not prerequisite_ids:
            return PrerequisiteReviewResponse(
                course_id=course_id, slug=slug, threshold=MASTERY_THRESHOLD,
                review_threshold=REVIEW_THRESHOLD, prerequisites=[], review_recommended=False,
            )
        prerequisites = self._data(
            self.client.table("concepts")
            .select("id,slug,title,kind")
            .in_("id", prerequisite_ids)
            .order("slug"),
            "load prerequisite concepts",
        )
        mastery = self._mastery_rows(owner_id, prerequisite_ids)
        entries = [self._prerequisite_concept(prerequisite, mastery) for prerequisite in prerequisites]
        return PrerequisiteReviewResponse(
            course_id=course_id,
            slug=slug,
            threshold=MASTERY_THRESHOLD,
            review_threshold=REVIEW_THRESHOLD,
            prerequisites=entries,
            review_recommended=any(entry.needs_review for entry in entries),
        )

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
            p_l_new = bkt_update(current_p_l, correct, params)
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
                .select("id,title,goal,status,active_version_id,updated_at,quiz_max_attempts")
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
            lessons_completed=completed,
            lessons_total=total,
        )


_memory_repository = MemoryCourseRepository()


def get_repository() -> CourseRepository:
    if get_settings().repository_backend == "supabase":
        return SupabaseCourseRepository(get_service_client())
    return _memory_repository
