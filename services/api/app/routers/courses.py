from typing import Annotated
from uuid import UUID

import docker
from fastapi import APIRouter, Depends, HTTPException, status

from app.dependencies import CurrentUser
from app.repository import CourseRepository, get_repository
from app.sandbox import DockerSandbox, SandboxError, SandboxFile
from app.schemas import ConceptDetailResponse, CourseMapResponse, CourseProgressResponse, CourseSummary, CreateCourseRequest, RunLessonRequest, RunLessonResponse
from app.settings import get_settings

router = APIRouter(prefix="/courses", tags=["courses"])
Repository = Annotated[CourseRepository, Depends(get_repository)]


def get_lesson_sandbox() -> DockerSandbox:
    return DockerSandbox(docker.from_env(), timeout_seconds=get_settings().sandbox_timeout_seconds)


LessonSandbox = Annotated[DockerSandbox, Depends(get_lesson_sandbox)]


@router.get("", response_model=list[CourseSummary])
def list_courses(current_user: CurrentUser, repository: Repository) -> list[CourseSummary]:
    return repository.list_courses(current_user)


@router.post("", response_model=CourseSummary, status_code=status.HTTP_201_CREATED)
def create_course(request: CreateCourseRequest, current_user: CurrentUser, repository: Repository) -> CourseSummary:
    return repository.create_course(current_user, request)


@router.get("/{course_id}", response_model=CourseSummary)
def get_course(course_id: UUID, current_user: CurrentUser, repository: Repository) -> CourseSummary:
    return repository.get_course(current_user, course_id)


@router.get("/{course_id}/map", response_model=CourseMapResponse)
def get_course_map(course_id: UUID, current_user: CurrentUser, repository: Repository) -> CourseMapResponse:
    return repository.course_map(current_user, course_id)


@router.get("/{course_id}/progress", response_model=CourseProgressResponse)
def get_course_progress(course_id: UUID, current_user: CurrentUser, repository: Repository) -> CourseProgressResponse:
    return repository.course_progress(current_user, course_id)


@router.post("/{course_id}/regenerate", response_model=CourseSummary)
def regenerate_course(course_id: UUID, current_user: CurrentUser, repository: Repository) -> CourseSummary:
    return repository.regenerate_course(current_user, course_id)


@router.get("/{course_id}/concepts/{slug}", response_model=ConceptDetailResponse)
def get_concept_detail(course_id: UUID, slug: str, current_user: CurrentUser, repository: Repository) -> ConceptDetailResponse:
    return repository.concept_detail(current_user, course_id, slug)


@router.post("/{course_id}/concepts/{slug}/run", response_model=RunLessonResponse)
def run_lesson(
    course_id: UUID,
    slug: str,
    request: RunLessonRequest,
    current_user: CurrentUser,
    repository: Repository,
    sandbox: LessonSandbox,
) -> RunLessonResponse:
    starter_files, test_files = repository.lesson_workspace(current_user, course_id, slug)
    expected_paths = {file.path for file in starter_files}
    submitted = {file.path: file.content for file in request.files}
    if len(submitted) != len(request.files) or set(submitted) != expected_paths:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail="Submit exactly the lesson starter files.")
    try:
        result = sandbox.run_pytest(
            [SandboxFile(path, submitted[path]) for path in sorted(submitted)]
            + [SandboxFile(file.path, file.content) for file in test_files]
        )
    except (SandboxError, ValueError) as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="The exercise runner is unavailable.") from exc
    return RunLessonResponse(passed=result.passed, output=result.output, timed_out=result.timed_out)


@router.post("/{course_id}/concepts/{slug}/regenerate", status_code=status.HTTP_202_ACCEPTED)
def regenerate_lesson(course_id: UUID, slug: str, current_user: CurrentUser, repository: Repository) -> None:
    repository.regenerate_lesson(current_user, course_id, slug)
