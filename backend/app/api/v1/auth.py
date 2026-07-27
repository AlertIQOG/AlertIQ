"""
Auth endpoints — registration, login, and current-user introspection.

Uses the OAuth2 password flow so the interactive /docs "Authorize"
button works out of the box.
"""

from typing import Annotated

from fastapi import APIRouter, Depends
from fastapi.security import OAuth2PasswordRequestForm

from app.api.v1.dependencies import CurrentUser, DbSession
from app.core.exceptions import AuthenticationError, NotificationError
from app.core.logging import logger
from app.core.security import (
    create_access_token,
    create_reset_token,
    decode_reset_token,
)
from app.schemas.notification import NotificationMessage
from app.schemas.user import (
    ForgotPasswordRequest,
    GoogleLoginRequest,
    ResetPasswordRequest,
    Token,
    UserCreate,
    UserRead,
)
from app.services.notifications.email_smtp import email_channel
from app.services.user import user_service
from google.auth.transport import requests as google_requests
from google.oauth2 import id_token
from app.core.config import settings

router = APIRouter()

_RESET_ACK = {
    "detail": "If an account with that email exists, a reset link has been sent."
}


def _send_reset_email(email: str, token: str) -> None:
    link = f"{settings.FRONTEND_URL}/reset-password?token={token}"
    message = NotificationMessage(
        title="AlertIQ password reset",
        body=(
            "We received a request to reset your AlertIQ password.\n\n"
            f"Reset it here (valid for {settings.RESET_TOKEN_EXPIRE_MINUTES} "
            f"minutes):\n{link}\n\n"
            "If you didn't request this, you can ignore this email."
        ),
    )
    email_channel.send(message, to=email)


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

@router.post("/forgot-password")
def forgot_password(*, session: DbSession, payload: ForgotPasswordRequest) -> dict[str, str]:
    """Email a reset link if the address belongs to an active account.

    Always responds the same way so it can't be used to probe which emails
    are registered.
    """
    user = user_service.get_by_email(session, email=payload.email)
    if user is not None and user.is_active and user.email:
        token = create_reset_token(user.id)
        try:
            _send_reset_email(user.email, token)
        except NotificationError as exc:
            logger.error("Failed to send reset email: %s", exc)
    return _RESET_ACK


@router.post("/reset-password", response_model=Token)
def reset_password(*, session: DbSession, payload: ResetPasswordRequest) -> Token:
    """Set a new password from a valid reset token, then log the user in."""
    user_id = decode_reset_token(payload.token)
    if user_id is None:
        raise AuthenticationError("This reset link is invalid or has expired")

    user = user_service.get(session, id=user_id)
    if user is None or not user.is_active:
        raise AuthenticationError("This reset link is invalid or has expired")

    user = user_service.set_password(session, user=user, new_password=payload.new_password)
    token = create_access_token(user.id, user.role.value)
    return Token(access_token=token, user=UserRead.model_validate(user))


@router.get("/me", response_model=UserRead)
def read_current_user(current_user: CurrentUser) -> UserRead:
    """Return the profile of the authenticated user."""
    return UserRead.model_validate(current_user)
