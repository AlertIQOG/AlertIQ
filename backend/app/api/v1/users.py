from typing import List

from fastapi import APIRouter

from app.api.v1.dependencies import CurrentUser, DbSession
from app.schemas.user import UserRead
from app.services.user import user_service

router = APIRouter()


@router.get("/", response_model=List[UserRead])
def read_users(
    *,
    session: DbSession,
    current_user: CurrentUser,
) -> List[UserRead]:
    """
    Retrieve all system users.
    Requires an authenticated user to access.
    """
    users = user_service.get_multi(session)
    return users