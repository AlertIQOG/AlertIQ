"""Unit tests for UserService.authenticate (stubbed lookups, no DB)."""

import uuid

from app.core.security import hash_password
from app.models.user import User, UserRole
from app.services.user import user_service


def _user(password: str, *, is_active: bool = True) -> User:
    return User(
        id=uuid.uuid4(),
        username="alice",
        hashed_password=hash_password(password),
        role=UserRole.OPERATOR,
        is_active=is_active,
    )


def test_authenticate_success(monkeypatch):
    user = _user("pw-123456")
    monkeypatch.setattr(
        user_service, "get_by_username", lambda session, *, username: user
    )

    result = user_service.authenticate(None, username="alice", password="pw-123456")
    assert result is user


def test_authenticate_wrong_password(monkeypatch):
    user = _user("pw-123456")
    monkeypatch.setattr(
        user_service, "get_by_username", lambda session, *, username: user
    )

    assert user_service.authenticate(None, username="alice", password="wrong") is None


def test_authenticate_unknown_user(monkeypatch):
    monkeypatch.setattr(
        user_service, "get_by_username", lambda session, *, username: None
    )

    assert user_service.authenticate(None, username="ghost", password="pw") is None


def test_authenticate_inactive_user(monkeypatch):
    user = _user("pw-123456", is_active=False)
    monkeypatch.setattr(
        user_service, "get_by_username", lambda session, *, username: user
    )

    result = user_service.authenticate(None, username="alice", password="pw-123456")
    assert result is None
