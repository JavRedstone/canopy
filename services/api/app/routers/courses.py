from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, status

from app.dependencies import CurrentUser
from app.repository import CourseRepository, get_repository
from app.schemas import CourseMapResponse, CourseSummary, CreateCourseRequest

router = APIRouter(prefix="/courses", tags=["courses"])
Repository = Annotated[CourseRepository, Depends(get_repository)]


@router.get("", response_model=list[CourseSummary])
def list_courses(current_user: CurrentUser, repository: Repository) -> list[CourseSummary]:
    return repository.list_courses(current_user)


@router.post("", response_model=CourseSummary, status_code=status.HTTP_201_CREATED)
def create_course(request: CreateCourseRequest, current_user: CurrentUser, repository: Repository) -> CourseSummary:
    return repository.create_course(current_user, request)


@router.get("/{course_id}/map", response_model=CourseMapResponse)
def get_course_map(course_id: UUID, current_user: CurrentUser, repository: Repository) -> CourseMapResponse:
    return repository.course_map(current_user, course_id)
