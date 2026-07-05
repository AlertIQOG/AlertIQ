"""
Auth endpoints — registration, login, and current-user introspection.

Uses the OAuth2 password flow so the interactive /docs "Authorize"
button works out of the box.
"""

from typing import Annotated

from fastapi import APIRouter, Depends
from fastapi.security import OAuth2PasswordRequestForm

from app.api.v1.dependencies import CurrentUser, DbSession
from app.core.exceptions import AuthenticationError
from app.core.security import create_access_token
from app.schemas.user import Token, UserCreate, UserRead
from app.services.user import user_service

router = APIRouter()


@router.post("/register", response_model=Token, status_code=201)
def register(
    *,
    session: DbSession,
    payload: UserCreate,
) -> Token:
    """Create a new account and return a bearer token (auto-login on signup)."""
    user = user_service.create_user(session, obj_in=payload)
    token = create_access_token(user.id, user.role.value)
    return Token(access_token=token, user=UserRead.model_validate(user))


@router.post("/login", response_model=Token)
def login(
    *,
    session: DbSession,
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
) -> Token:
    """Exchange username + password for a bearer token."""
    user = user_service.authenticate(
        session, username=form_data.username, password=form_data.password
    )
    if user is None:
        raise AuthenticationError("Incorrect username or password")

    token = create_access_token(user.id, user.role.value)
    return Token(access_token=token, user=UserRead.model_validate(user))


@router.get("/me", response_model=UserRead)
def read_current_user(current_user: CurrentUser) -> UserRead:
    """Return the profile of the authenticated user."""
    return UserRead.model_validate(current_user)
