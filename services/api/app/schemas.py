from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field


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


class CreateCourseRequest(BaseModel):
    title: str = Field(min_length=1, max_length=120)
    goal: str = Field(min_length=1, max_length=2000)
    source_ids: list[UUID] = Field(default_factory=list)
    lesson_min: int = Field(default=8, ge=4, le=24)
    lesson_max: int = Field(default=16, ge=4, le=24)
    quiz_max_attempts: int = Field(default=3, ge=1, le=10)


class UpdateCourseRequest(BaseModel):
    """Fields safe to change without invalidating already-generated content."""

    title: str | None = Field(default=None, min_length=1, max_length=120)
    quiz_max_attempts: int | None = Field(default=None, ge=1, le=10)


class CourseSummary(BaseModel):
    id: UUID
    title: str
    goal: str
    status: CourseStatus
    active_version: int
    updated_at: datetime
    quiz_max_attempts: int = 3


class CoursePointsResponse(BaseModel):
    """Mastery points: a fixed award per lesson (coding lab passed, or every quiz item in
    a mastery check answered correctly) -- a coarse, gamified completion signal, distinct
    from the continuous BKT mastery estimate in the `mastery` table."""

    course_id: UUID
    points_earned: int
    points_total: int
    points_per_lesson: int


class CourseMapConcept(BaseModel):
    slug: str
    title: str
    kind: Literal["conceptual", "coding", "assessment"]
    summary_markdown: str


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
