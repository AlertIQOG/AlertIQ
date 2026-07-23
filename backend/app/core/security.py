"""
Password hashing and JWT helpers.

Pure crypto/token utilities — no FastAPI, no database access.
Raising and mapping auth errors is handled by the callers
(services / dependencies) via domain exceptions.
"""

import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

import bcrypt
import jwt

from app.core.config import settings

ALGORITHM = "HS256"


def hash_password(password: str) -> str:
    """Hash a plaintext password with bcrypt (random salt)."""
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(password: str, hashed: str) -> bool:
    """Check a plaintext password against a stored bcrypt hash."""
    try:
        return bcrypt.checkpw(password.encode(), hashed.encode())
    except ValueError:
        # Malformed stored hash — treat as non-matching rather than crash.
        return False


def create_access_token(user_id: uuid.UUID, role: str) -> str:
    """Create a signed JWT for the given user."""
    expires = datetime.now(timezone.utc) + timedelta(
        minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES
    )
    payload = {"sub": str(user_id), "role": role, "exp": expires}
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=ALGORITHM)


def decode_access_token(token: str) -> dict[str, Any] | None:
    """Decode and validate a JWT — returns the payload, or ``None`` if invalid."""
    try:
        return jwt.decode(token, settings.SECRET_KEY, algorithms=[ALGORITHM])
    except jwt.InvalidTokenError:
        return None


_RESET_PURPOSE = "password_reset"


def create_reset_token(user_id: uuid.UUID) -> str:
    """Create a short-lived, single-purpose JWT for resetting a password."""
    expires = datetime.now(timezone.utc) + timedelta(
        minutes=settings.RESET_TOKEN_EXPIRE_MINUTES
    )
    payload = {"sub": str(user_id), "purpose": _RESET_PURPOSE, "exp": expires}
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=ALGORITHM)


def decode_reset_token(token: str) -> uuid.UUID | None:
    """Return the user id from a valid reset token, or ``None`` if unusable.

    Rejects expired/tampered tokens and anything not minted for password reset.
    """
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[ALGORITHM])
    except jwt.InvalidTokenError:
        return None
    if payload.get("purpose") != _RESET_PURPOSE:
        return None
    sub = payload.get("sub")
    try:
        return uuid.UUID(str(sub))
    except (ValueError, TypeError):
        return None
