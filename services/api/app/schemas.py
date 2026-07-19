from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field, model_validator


SourceStatus = Literal["uploading", "uploaded", "ingesting", "ready", "failed"]
CourseStatus = Literal["draft", "ready", "archived"]
SourceMimeType = Literal["application/pdf", "text/markdown", "text/plain"]
MAX_SOURCE_BYTES = 6 * 1024 * 1024


class HealthResponse(BaseModel):
    status: Literal["ok"]
    environment: str
    repository: str


class CreateSourceRequest(BaseModel):
    filename: str = Field(min_length=1, max_length=255)
    mime_type: SourceMimeType
    byte_size: int = Field(ge=1, le=MAX_SOURCE_BYTES)


class SourceUploadTarget(BaseModel):
    id: UUID
    storage_path: str
    upload_token: str = Field(min_length=1)
    status: SourceStatus


class SourceSummary(BaseModel):
    id: UUID
    filename: str
    status: SourceStatus


CourseLanguage = Literal["python", "python-ml", "cpp"]


class CreateCourseRequest(BaseModel):
    title: str = Field(min_length=1, max_length=120)
    goal: str = Field(min_length=1, max_length=2000)
    source_ids: list[UUID] = Field(default_factory=list)
    lesson_min: int = Field(default=12, ge=6, le=24)
    lesson_max: int = Field(default=20, ge=6, le=24)
    quiz_max_attempts: int = Field(default=3, ge=1, le=10)
    # Fixed at creation -- not on UpdateCourseRequest, since changing it after generation
    # would leave a course with mixed-language labs. Coding labs target this language;
    # conceptual/assessment concepts are unaffected either way.
    language: CourseLanguage = "python"


class UpdateCourseRequest(BaseModel):
    """Fields safe to change without invalidating already-generated content. lesson_min/max
    are the exception in spirit -- they don't retroactively touch existing lessons, but do
    change what the next regeneration targets."""

    title: str | None = Field(default=None, min_length=1, max_length=120)
    quiz_max_attempts: int | None = Field(default=None, ge=1, le=10)
    lesson_min: int | None = Field(default=None, ge=6, le=24)
    lesson_max: int | None = Field(default=None, ge=6, le=24)
    # Google-Docs-style link sharing: on means anyone with the course id can import a copy.
    is_shared: bool | None = None

    @model_validator(mode="after")
    def lesson_range_is_complete_and_ordered(self) -> "UpdateCourseRequest":
        if (self.lesson_min is None) != (self.lesson_max is None):
            raise ValueError("lesson_min and lesson_max must be set together.")
        if self.lesson_min is not None and self.lesson_max is not None and self.lesson_min > self.lesson_max:
            raise ValueError("Minimum lessons cannot exceed maximum lessons.")
        return self


class CourseSummary(BaseModel):
    id: UUID
    title: str
    goal: str
    status: CourseStatus
    active_version: int
    updated_at: datetime
    quiz_max_attempts: int = 3
    lesson_min: int = 12
    lesson_max: int = 20
    lessons_completed: int = 0
    lessons_total: int = 0
    language: CourseLanguage = "python"
    # True when the owner has turned on link sharing for this course.
    is_shared: bool = False


class ImportCourseRequest(BaseModel):
    """Import a copy of a shared course's content by its id (its share token)."""

    course_id: UUID


class CoursePointsResponse(BaseModel):
    """Mastery points: a fixed award per lesson (coding lab passed, or every quiz item in
    a mastery check answered correctly) -- a coarse, gamified completion signal, distinct
    from the continuous BKT mastery estimate in the `mastery` table."""

    course_id: UUID
    points_earned: int
    points_total: int
    points_per_lesson: int


class ConceptMastery(BaseModel):
    """Per-concept dual-track mastery: continuous BKT estimates, distinct from the coarse
    completion/points signal. ``p_understand`` (quiz-fed) and ``p_apply`` (coding-fed) are
    ``None`` until that track has at least one observation, so the UI can show "no data yet"
    rather than a misleading zero."""

    slug: str
    title: str
    kind: Literal["conceptual", "coding", "assessment"]
    p_understand: float | None = None
    p_apply: float | None = None
    understand_opportunities: int = 0
    apply_opportunities: int = 0
    mastered: bool = False


class CourseMasteryResponse(BaseModel):
    course_id: UUID
    threshold: float
    concepts: list[ConceptMastery]


class PrerequisiteConcept(BaseModel):
    """A concept the current one builds on, with the learner's mastery on it. ``needs_review``
    means it was practiced but is shaky, so reviewing it should help the current concept."""

    slug: str
    title: str
    kind: Literal["conceptual", "coding", "assessment"]
    p_understand: float | None = None
    p_apply: float | None = None
    mastered: bool = False
    needs_review: bool = False


class PrerequisiteReviewResponse(BaseModel):
    course_id: UUID
    slug: str
    threshold: float
    review_threshold: float
    prerequisites: list[PrerequisiteConcept]
    # True when at least one prerequisite is shaky enough to recommend reviewing first.
    review_recommended: bool = False


class PrerequisiteRecommendation(BaseModel):
    """Surfaced inline the moment a learner is struggling on a concept: the shaky
    prerequisites that concept builds on, so the UI can nudge them to review first. A ``None``
    value on a graded response means no recommendation -- either they are not struggling yet,
    the concept has no prerequisites, or every prerequisite is already solid."""

    concept_slug: str
    concept_title: str
    reason_markdown: str
    prerequisites: list[PrerequisiteConcept]


RecommendationDecision = Literal["accepted", "deferred", "declined"]


class RecommendationSummary(BaseModel):
    """One open prerequisite-review recommendation on the course-level panel: the concept the
    learner is stuck on and the shaky prerequisites it builds on, resolved against *current*
    mastery so an already-shored-up prerequisite drops off on its own."""

    id: UUID
    concept_slug: str
    concept_title: str
    prerequisites: list[PrerequisiteConcept]
    created_at: datetime


class RecommendationsResponse(BaseModel):
    course_id: UUID
    recommendations: list[RecommendationSummary]


class RecommendationDecisionRequest(BaseModel):
    # The learner's verdict on a recommendation: commit to it, snooze it, or dismiss it.
    decision: RecommendationDecision


class CourseMapConcept(BaseModel):
    slug: str
    title: str
    kind: Literal["conceptual", "coding", "assessment"]
    summary_markdown: str
    completed: bool = False


class CourseMapModule(BaseModel):
    title: str
    position: int
    concepts: list[CourseMapConcept]


class CourseMapResponse(BaseModel):
    course_id: UUID
    version: int
    modules: list[CourseMapModule]


CourseProgressStage = Literal["ingesting_sources", "planning", "building_lessons", "ready", "failed"]


class CourseProgressResponse(BaseModel):
    course_id: UUID
    stage: CourseProgressStage
    sources_ready: int
    sources_total: int
    lessons_built: int
    lessons_total: int
    current_lesson_title: str | None = None


class LessonWorkspaceFile(BaseModel):
    path: str
    content: str


LessonBuildStatus = Literal["pending", "building", "built", "failed"]


class WorkedExamplePreview(BaseModel):
    title: str
    body_markdown: str


class QuizOptionPreview(BaseModel):
    text: str


QuizKind = Literal["mcq", "multi_select", "fill", "short_answer"]


class QuizAnswerRequest(BaseModel):
    """The learner's response; exactly the field matching the item's kind must be set."""

    selected_option_index: int | None = Field(default=None, ge=0)
    selected_option_indices: list[int] | None = Field(default=None, max_length=6)
    answer_text: str | None = Field(default=None, max_length=4000)


class QuizOptionGrade(BaseModel):
    text: str
    explanation_markdown: str
    correct: bool


class QuizGradeResponse(BaseModel):
    """Full feedback, revealed only after the learner has answered."""

    item_id: str
    correct: bool
    explanation_markdown: str
    options: list[QuizOptionGrade] = Field(default_factory=list)
    correct_answers: list[str] = Field(default_factory=list)
    feedback_markdown: str | None = None
    attempts_used: int = 0
    attempts_remaining: int = 0
    # Set when this answer leaves the learner struggling on a concept with shaky prerequisites.
    prerequisite_recommendation: PrerequisiteRecommendation | None = None


class QuizItemPreview(BaseModel):
    """A quiz item with grading fields (correct answers, rubric, explanations) stripped,
    unless the learner already answered it correctly -- previous_answer/previous_grade
    then replay exactly what they submitted and were shown, so returning to a finished
    mastery check still reads as the real thing instead of resetting to a blank question."""

    id: str
    kind: QuizKind
    prompt_markdown: str
    options: list[QuizOptionPreview] = Field(default_factory=list)
    attempts_used: int = 0
    correct: bool | None = None
    previous_answer: QuizAnswerRequest | None = None
    previous_grade: QuizGradeResponse | None = None


class LessonPreview(BaseModel):
    status: LessonBuildStatus
    title: str
    explanation_markdown: str
    starter_files: list[LessonWorkspaceFile]
    hints: list[str]
    public_test_files: list[LessonWorkspaceFile] = Field(default_factory=list)
    solution_files: list[LessonWorkspaceFile] = Field(default_factory=list)
    worked_examples: list[WorkedExamplePreview] = Field(default_factory=list)
    quiz_items: list[QuizItemPreview] = Field(default_factory=list)
    quiz_max_attempts: int = 3


class RunLessonRequest(BaseModel):
    files: list[LessonWorkspaceFile] = Field(min_length=1, max_length=10)


class RunLessonResponse(BaseModel):
    passed: bool
    output: str
    timed_out: bool
    # Set on a graded Submit that leaves the learner struggling with shaky prerequisites.
    # Always None for a plain Run, which records no observation.
    prerequisite_recommendation: PrerequisiteRecommendation | None = None


class RunScriptRequest(BaseModel):
    files: list[LessonWorkspaceFile] = Field(min_length=1, max_length=10)
    script: LessonWorkspaceFile


class RunScriptResponse(BaseModel):
    output: str
    exit_code: int
    timed_out: bool


class ConceptDetailResponse(BaseModel):
    slug: str
    title: str
    kind: Literal["conceptual", "coding", "assessment"]
    summary_markdown: str
    citations: list[str]
    generation_status: LessonBuildStatus | None = None
    lesson: LessonPreview | None = None


class CitationExcerptResponse(BaseModel):
    id: UUID
    filename: str
    section: str | None
    page_number: int | None
    content: str


class CertificateResponse(BaseModel):
    """A completion certificate -- only issuable once every lesson in the course is done
    (``lessons_completed == lessons_total``, both > 0). ``issued_at`` is the fixed moment
    the ``certificates`` row was first created, not recomputed on every view.
    ``certificate_id`` is a short, deterministic display label (derived from course_id +
    owner_id); ``verify_url`` is the durable, shareable public link (keyed on the
    ``certificates`` row id, not on that label)."""

    course_id: UUID
    course_title: str
    learner_name: str
    issued_at: datetime
    certificate_id: str
    verify_url: str
    # Module titles from the course map -- the closest existing proxy to discrete "skills"
    # without a dedicated skill-tagging model.
    skills: list[str]
    # Estimated, not measured: no time-on-task tracking exists yet (see
    # docs/product/PEDAGOGY_EVALUATION.md), so this is lessons_total times a flat
    # per-lesson estimate, the same honesty tradeoff course-catalog sites make.
    estimated_hours: float
    # Computed once, server-side, from the course's title/goal (app/course_category.py) --
    # so the PDF and the web view theme identically instead of each guessing separately.
    accent_color: str
    accent_tint: str


class ProfileResponse(BaseModel):
    email: str
    display_name: str | None = None


class UpdateProfileRequest(BaseModel):
    # Empty/whitespace-only clears it back to null (falls back to the email everywhere
    # a name is shown) rather than persisting a blank string.
    display_name: str | None = Field(default=None, max_length=80)


class CourseSourceSummary(BaseModel):
    id: UUID
    filename: str
    mime_type: SourceMimeType
    byte_size: int
    status: SourceStatus
    position: int


class SourceDownloadResponse(BaseModel):
    filename: str
    mime_type: SourceMimeType
    download_url: str


class LessonHelperRequest(BaseModel):
    question: str = Field(min_length=1, max_length=1200)
    selected_text: str | None = Field(default=None, max_length=6000)
    request_revision: bool = False
    workspace_files: list[LessonWorkspaceFile] = Field(default_factory=list, max_length=10)
    quiz_item_id: str | None = Field(default=None, max_length=100)


class LessonHelperResponse(BaseModel):
    answer_markdown: str = Field(min_length=1, max_length=4000)
    replacement_markdown: str | None = Field(default=None, max_length=2400)


class DemoAutoCompleteRequest(BaseModel):
    """Dev-only: drive some or all of a course to completion as an LLM standing in for
    the learner, through the real grading/sandbox paths -- for demoing mastery, points,
    and completion state without grinding through a course by hand."""

    # "mastered": answer everything correctly -- the fastest path to a fully completed
    # course. "mixed": aim for correct_rate correct and the rest deliberately wrong, so
    # the mastery meters show a realistic, partially-mastered snapshot instead of 100%.
    target: Literal["mastered", "mixed"] = "mastered"
    correct_rate: float = Field(default=0.6, ge=0.0, le=1.0)
    # None means every concept in the course; otherwise only these slugs are touched --
    # lets a demo target one struggling concept, one module, or the whole course.
    concept_slugs: list[str] | None = None
    include_quizzes: bool = True
    include_labs: bool = True


class DemoConceptResult(BaseModel):
    concept_slug: str
    concept_title: str
    kind: Literal["conceptual", "coding", "assessment"]
    quiz_items_correct: int = 0
    quiz_items_incorrect: int = 0
    quiz_items_skipped: int = 0
    lab_passed: bool | None = None
    error: str | None = None


class DemoJobStatus(BaseModel):
    """Polled while a demo auto-complete run is in progress. Runs in a background
    thread inside the API process (dev-only, in-memory -- lost on restart, which is fine
    for a local debug tool) so the client can see real per-concept progress and cancel
    between concepts, instead of one opaque request that blocks until the whole course
    is done."""

    job_id: str
    course_id: UUID
    state: Literal["running", "completed", "cancelled", "failed"]
    total: int
    completed: int
    current_concept_title: str | None = None
    results: list[DemoConceptResult] = Field(default_factory=list)
    error: str | None = None
