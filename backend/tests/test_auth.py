"""
Unit tests for the auth layer — login endpoint, bearer-token protection,
and webhook-secret verification on ingest.

Follows the repo's testing convention: TestClient + monkeypatched service
singletons, no database fixture (the DB is never touched by these tests).
"""

import uuid

from fastapi.testclient import TestClient

from app.core.security import create_access_token
from app.main import app
from app.models.source import Source
from app.models.user import User, UserRole
from app.services.source import source_service
from app.services.user import user_service

client = TestClient(app)


def _fake_user(**overrides) -> User:
    defaults = dict(
        id=uuid.uuid4(),
        username="tester",
        hashed_password="irrelevant",
        full_name="Test User",
        role=UserRole.OPERATOR,
        is_active=True,
    )
    defaults.update(overrides)
    return User(**defaults)


# ── /auth/login ────────────────────────────────────────────────────


def test_login_success_returns_token_and_user(monkeypatch):
    user = _fake_user()
    monkeypatch.setattr(
        user_service, "authenticate", lambda session, *, username, password: user
    )

    response = client.post(
        "/api/v1/auth/login", data={"username": "tester", "password": "pw"}
    )

    assert response.status_code == 200
    body = response.json()
    assert body["token_type"] == "bearer"
    assert body["access_token"]
    assert body["user"]["username"] == "tester"
    assert "hashed_password" not in body["user"]


def test_login_bad_credentials_returns_401(monkeypatch):
    monkeypatch.setattr(
        user_service, "authenticate", lambda session, *, username, password: None
    )

    response = client.post(
        "/api/v1/auth/login", data={"username": "tester", "password": "nope"}
    )

    assert response.status_code == 401
    assert response.headers["WWW-Authenticate"] == "Bearer"


# ── Bearer-token protection on API routes ──────────────────────────


def test_protected_route_without_token_is_401():
    response = client.get("/api/v1/alerts/")
    assert response.status_code == 401
    assert response.headers["WWW-Authenticate"] == "Bearer"


def test_protected_route_with_garbage_token_is_401():
    response = client.get(
        "/api/v1/alerts/", headers={"Authorization": "Bearer not.a.jwt"}
    )
    assert response.status_code == 401


def test_health_stays_public():
    response = client.get("/api/v1/health")
    assert response.status_code == 200


def test_me_returns_current_user(monkeypatch):
    user = _fake_user(username="me-user")

    class _StubSession:
        def get(self, model, pk):
            assert model is User
            return user if pk == user.id else None

    from app.core.database import get_session

    app.dependency_overrides[get_session] = lambda: _StubSession()
    try:
        token = create_access_token(user.id, user.role.value)
        response = client.get(
            "/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"}
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["username"] == "me-user"


def test_token_for_inactive_user_is_401(monkeypatch):
    user = _fake_user(is_active=False)

    class _StubSession:
        def get(self, model, pk):
            return user

    from app.core.database import get_session

    app.dependency_overrides[get_session] = lambda: _StubSession()
    try:
        token = create_access_token(user.id, user.role.value)
        response = client.get(
            "/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"}
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 401


# ── Webhook-secret verification on /ingest ─────────────────────────

_EMPTY_WEBHOOK = {"receiver": "alertiq", "status": "firing", "alerts": []}


def _fake_source(secret: str | None) -> Source:
    return Source(
        id=uuid.uuid4(),
        name="Mock",
        provider_type="prometheus",
        is_active=True,
        webhook_secret=secret,
    )


def _ingest(source: Source, headers: dict | None = None):
    return client.post(
        f"/api/v1/ingest/prometheus/{source.id}",
        json=_EMPTY_WEBHOOK,
        headers=headers or {},
    )


def test_ingest_without_token_is_401(monkeypatch):
    source = _fake_source("expected-secret")
    monkeypatch.setattr(source_service, "get", lambda session, *, id: source)

    assert _ingest(source).status_code == 401


def test_ingest_with_wrong_token_is_401(monkeypatch):
    source = _fake_source("expected-secret")
    monkeypatch.setattr(source_service, "get", lambda session, *, id: source)

    response = _ingest(source, {"X-Webhook-Token": "wrong"})
    assert response.status_code == 401


def test_ingest_with_correct_token_is_accepted(monkeypatch):
    source = _fake_source("expected-secret")
    monkeypatch.setattr(source_service, "get", lambda session, *, id: source)

    response = _ingest(source, {"X-Webhook-Token": "expected-secret"})
    assert response.status_code == 202
    assert response.json() == {"created": 0, "updated": 0, "aggregated": 0}


def test_ingest_source_without_secret_is_401(monkeypatch):
    source = _fake_source(None)
    monkeypatch.setattr(source_service, "get", lambda session, *, id: source)

    response = _ingest(source, {"X-Webhook-Token": "anything"})
    assert response.status_code == 401


def test_ingest_unknown_source_is_404(monkeypatch):
    monkeypatch.setattr(source_service, "get", lambda session, *, id: None)

    response = client.post(
        f"/api/v1/ingest/prometheus/{uuid.uuid4()}",
        json=_EMPTY_WEBHOOK,
        headers={"X-Webhook-Token": "anything"},
    )
    assert response.status_code == 404
