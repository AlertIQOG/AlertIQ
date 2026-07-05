"""Unit tests for password hashing and JWT helpers (pure logic, no DB)."""

import uuid

from app.core import security
from app.core.config import settings


def test_hash_password_roundtrip():
    hashed = security.hash_password("s3cret-password")
    assert hashed != "s3cret-password"
    assert security.verify_password("s3cret-password", hashed)


def test_verify_password_rejects_wrong_password():
    hashed = security.hash_password("correct-password")
    assert not security.verify_password("wrong-password", hashed)


def test_verify_password_handles_malformed_hash():
    assert not security.verify_password("anything", "not-a-bcrypt-hash")


def test_hashes_are_salted():
    assert security.hash_password("same") != security.hash_password("same")


def test_create_and_decode_access_token():
    user_id = uuid.uuid4()
    token = security.create_access_token(user_id, "Admin")

    payload = security.decode_access_token(token)
    assert payload is not None
    assert payload["sub"] == str(user_id)
    assert payload["role"] == "Admin"
    assert "exp" in payload


def test_decode_rejects_garbage_token():
    assert security.decode_access_token("not.a.jwt") is None


def test_decode_rejects_token_signed_with_other_key():
    import jwt

    forged = jwt.encode(
        {"sub": str(uuid.uuid4()), "role": "Admin"},
        "some-other-secret",
        algorithm=security.ALGORITHM,
    )
    assert security.decode_access_token(forged) is None


def test_decode_rejects_expired_token(monkeypatch):
    monkeypatch.setattr(settings, "ACCESS_TOKEN_EXPIRE_MINUTES", -5)
    token = security.create_access_token(uuid.uuid4(), "Operator")
    assert security.decode_access_token(token) is None
