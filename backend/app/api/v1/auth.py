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
from app.schemas.user import GoogleLoginRequest, Token, UserCreate, UserRead
from app.services.user import user_service
from google.auth.transport import requests as google_requests
from google.oauth2 import id_token
from app.core.config import settings

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

@router.post("/google", response_model=Token)
def google_login(
    *,
    session: DbSession,
    payload: GoogleLoginRequest,
) -> Token:
    """Authenticate a user using a Google ID token."""

    if not settings.GOOGLE_CLIENT_ID:
        raise AuthenticationError("Google authentication is not configured")

    try:
        google_user = id_token.verify_oauth2_token(
            payload.credential,
            google_requests.Request(),
            settings.GOOGLE_CLIENT_ID,
        )
    except ValueError as exc:
        raise AuthenticationError("Invalid Google credential") from exc

    email = google_user.get("email")
    email_verified = google_user.get("email_verified", False)
    full_name = google_user.get("name")

    if not email or not email_verified:
        raise AuthenticationError("Google account email is not verified")

    user = user_service.get_or_create_google_user(
        session,
        email=email,
        full_name=full_name,
    )

    if not user.is_active:
        raise AuthenticationError("User account is inactive")

    token = create_access_token(user.id, user.role.value)

    return Token(
        access_token=token,
        user=UserRead.model_validate(user),
    )

@router.get("/me", response_model=UserRead)
def read_current_user(current_user: CurrentUser) -> UserRead:
    """Return the profile of the authenticated user."""
    return UserRead.model_validate(current_user)
