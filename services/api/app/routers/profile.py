from typing import Annotated

from fastapi import APIRouter, Depends

from app.dependencies import CurrentUser
from app.repository import CourseRepository, get_repository
from app.schemas import ProfileResponse, UpdateProfileRequest

router = APIRouter(prefix="/profile", tags=["profile"])
Repository = Annotated[CourseRepository, Depends(get_repository)]


@router.get("", response_model=ProfileResponse)
def get_profile(current_user: CurrentUser, repository: Repository) -> ProfileResponse:
    return repository.profile(current_user)


@router.patch("", response_model=ProfileResponse)
def update_profile(request: UpdateProfileRequest, current_user: CurrentUser, repository: Repository) -> ProfileResponse:
    """Sets (or, with an empty/whitespace string, clears) the learner's display name --
    shown instead of a bare email everywhere a name appears, e.g. a certificate."""
    return repository.update_profile(current_user, request)
