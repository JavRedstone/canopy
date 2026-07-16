from uuid import UUID

from typing import Annotated

from fastapi import APIRouter, Depends, status

from app.dependencies import CurrentUser
from app.repository import CourseRepository, get_repository
from app.schemas import CreateSourceRequest, SourceSummary, SourceUploadTarget

router = APIRouter(prefix="/sources", tags=["sources"])
Repository = Annotated[CourseRepository, Depends(get_repository)]


@router.post("", response_model=SourceUploadTarget, status_code=status.HTTP_201_CREATED)
def create_source(request: CreateSourceRequest, current_user: CurrentUser, repository: Repository) -> SourceUploadTarget:
    return repository.create_source(current_user, request)


@router.post("/{source_id}/complete", response_model=SourceSummary)
def complete_source(source_id: UUID, current_user: CurrentUser, repository: Repository) -> SourceSummary:
    return repository.complete_source(current_user, source_id)
