"""
Password hashing and JWT helpers.

Pure crypto/token utilities — no FastAPI, no database access.
Raising and mapping auth errors is handled by the callers
(services / dependencies) via domain exceptions.
"""

import hashlib
import hmac
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
    """Decode and validate a session JWT — returns the payload, or ``None``.

    Single-purpose tokens (``purpose`` claim, e.g. password reset) are
    rejected so they can never double as session tokens.
    """
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[ALGORITHM])
    except jwt.InvalidTokenError:
        return None
    if payload.get("purpose") is not None:
        return None
    return payload


_RESET_PURPOSE = "password_reset"


def password_fingerprint(hashed_password: str) -> str:
    """Short non-reversible digest of a password hash, embedded in reset
    tokens so they stop working once the password changes."""
    return hashlib.sha256(hashed_password.encode()).hexdigest()[:16]


def create_reset_token(user_id: uuid.UUID, hashed_password: str) -> str:
    """Create a short-lived, single-purpose JWT for resetting a password,
    bound to the current password hash (single-use by construction)."""
    expires = datetime.now(timezone.utc) + timedelta(
        minutes=settings.RESET_TOKEN_EXPIRE_MINUTES
    )
    payload = {
        "sub": str(user_id),
        "purpose": _RESET_PURPOSE,
        "pwd": password_fingerprint(hashed_password),
        "exp": expires,
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=ALGORITHM)


def decode_reset_token(token: str) -> tuple[uuid.UUID, str] | None:
    """Return ``(user_id, password_fingerprint)`` from a valid reset token.

    Rejects expired/tampered/wrong-purpose tokens. The caller must check the
    fingerprint against the user's current hash — a mismatch means the link
    is spent.
    """
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[ALGORITHM])
    except jwt.InvalidTokenError:
        return None
    if payload.get("purpose") != _RESET_PURPOSE:
        return None
    sub = payload.get("sub")
    try:
        return uuid.UUID(str(sub)), str(payload.get("pwd") or "")
    except (ValueError, TypeError):
        return None


def fingerprints_match(provided: str, current: str) -> bool:
    """Constant-time comparison for password fingerprints."""
    return hmac.compare_digest(provided, current)
