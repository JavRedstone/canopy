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


class CourseSummary(BaseModel):
    id: UUID
    title: str
    goal: str
    status: CourseStatus
    active_version: int
    updated_at: datetime


class CourseMapConcept(BaseModel):
    slug: str
    title: str
    kind: Literal["conceptual", "coding"]
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
