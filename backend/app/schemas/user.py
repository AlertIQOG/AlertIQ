"""Pydantic schemas for the User resource and auth tokens."""

import uuid
from datetime import datetime

from pydantic import BaseModel, Field

from app.models.user import UserRole


class UserCreate(BaseModel):
    """Payload accepted when creating a new user."""

    username: str = Field(min_length=3, max_length=64)
    password: str = Field(min_length=8, max_length=128)
    full_name: str | None = None
    role: UserRole = UserRole.OPERATOR


class UserRead(BaseModel):
    """Schema returned to the client — never exposes the password hash."""

    model_config = {"from_attributes": True}

    id: uuid.UUID
    username: str
    full_name: str | None = None
    role: UserRole
    is_active: bool
    created_at: datetime | None = None

class GoogleLoginRequest(BaseModel):
    """Google ID token received from the frontend."""

    credential: str = Field(min_length=1)
    
class Token(BaseModel):
    """OAuth2-style bearer-token response returned by ``/auth/login``."""

    access_token: str
    token_type: str = "bearer"
    user: UserRead
