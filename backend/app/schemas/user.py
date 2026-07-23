"""Pydantic schemas for the User resource and auth tokens."""

import uuid
from datetime import datetime

from pydantic import BaseModel, Field, field_validator

from app.models.user import UserRole


def _validate_email(value: str | None) -> str | None:
    if value is None:
        return None
    value = value.strip().lower()
    if "@" not in value or "." not in value.split("@")[-1]:
        raise ValueError("Invalid email address")
    return value


class UserCreate(BaseModel):
    """Payload accepted when creating a new user."""

    username: str = Field(min_length=3, max_length=64)
    email: str | None = None
    password: str = Field(min_length=8, max_length=128)
    full_name: str | None = None
    role: UserRole = UserRole.OPERATOR

    _check_email = field_validator("email")(_validate_email)


class UserRead(BaseModel):
    """Schema returned to the client — never exposes the password hash."""

    model_config = {"from_attributes": True}

    id: uuid.UUID
    username: str
    email: str | None = None
    full_name: str | None = None
    role: UserRole
    is_active: bool
    created_at: datetime | None = None


class ForgotPasswordRequest(BaseModel):
    """Request a password-reset link for an account's email."""

    email: str

    _check_email = field_validator("email")(_validate_email)


class ResetPasswordRequest(BaseModel):
    """Set a new password using a token from the reset email."""

    token: str = Field(min_length=1)
    new_password: str = Field(min_length=8, max_length=128)

class GoogleLoginRequest(BaseModel):
    """Google ID token received from the frontend."""

    credential: str = Field(min_length=1)
    
class Token(BaseModel):
    """OAuth2-style bearer-token response returned by ``/auth/login``."""

    access_token: str
    token_type: str = "bearer"
    user: UserRead
