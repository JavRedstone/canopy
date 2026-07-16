from typing import Annotated
from uuid import UUID

from fastapi import Depends, Header, HTTPException, status

from app.settings import get_settings
from app.supabase import get_service_client

DEVELOPMENT_USER_ID = UUID("00000000-0000-0000-0000-000000000001")


def get_current_user(
    x_demo_user_id: Annotated[str | None, Header()] = None,
    authorization: Annotated[str | None, Header()] = None,
) -> UUID:
    settings = get_settings()
    if settings.auth_mode == "development":
        if x_demo_user_id:
            try:
                return UUID(x_demo_user_id)
            except ValueError as exc:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid X-Demo-User-Id.") from exc
        return DEVELOPMENT_USER_ID
    if not authorization:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing bearer token.")
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid bearer token.")

    try:
        response = get_service_client().auth.get_user(token)
        user = response.user
        if user is None:
            raise ValueError("Supabase did not return a user.")
        return UUID(str(user.id))
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired session.") from exc


CurrentUser = Annotated[UUID, Depends(get_current_user)]
