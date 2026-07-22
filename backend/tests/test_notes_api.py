"""End-to-end tests for the notes CRUD endpoints nested under alerts.

Verifies the full lifecycle (create / list / edit / delete) plus the two
behaviours that matter for the Resolution Copilot:

  * a Solved parent alert is re-indexed on every note mutation, so the RAG
    chunk stays in sync with its resolution notes;
  * a note can only be edited/deleted through its own parent alert (no
    cross-alert access via a spoofed URL);
  * a note can only be edited/deleted by the user who wrote it, and its
    author is taken from the token rather than the request body.

The embedding step is stubbed, so this needs no Voyage key or pgvector.
"""

import uuid
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, delete

import app.services.note as note_module
from app.api.v1.dependencies import get_current_user
from app.core.database import engine
from app.main import app
from app.models.alert import Alert, AlertSeverity, AlertStatus
from app.models.note import Note
from app.models.source import Source


@pytest.fixture
def seeded(monkeypatch):
    # Count re-index calls instead of hitting the real embedder / pgvector.
    calls: list[uuid.UUID] = []
    monkeypatch.setattr(
        note_module, "safe_index_alert", lambda session, alert: calls.append(alert.id)
    )
    # Stub the bearer auth; reassign username to act as somebody else.
    session_user = SimpleNamespace(username="ops")
    app.dependency_overrides[get_current_user] = lambda: session_user

    source_id = uuid.uuid4()
    solved_id = uuid.uuid4()
    other_id = uuid.uuid4()

    with Session(engine) as s:
        s.add(Source(id=source_id, name="t", provider_type="grafana"))
        s.add(
            Alert(
                id=solved_id, source_id=source_id, external_id=f"s-{solved_id}",
                message="Disk full", severity=AlertSeverity.CRITICAL,
                status=AlertStatus.SOLVED,
            )
        )
        s.add(
            Alert(
                id=other_id, source_id=source_id, external_id=f"o-{other_id}",
                message="Unrelated", severity=AlertSeverity.WARNING,
                status=AlertStatus.OPEN,
            )
        )
        s.commit()

    yield solved_id, other_id, calls, session_user

    app.dependency_overrides.clear()
    with Session(engine) as s:
        s.exec(delete(Note).where(Note.alert_id.in_([solved_id, other_id])))
        s.exec(delete(Alert).where(Alert.id.in_([solved_id, other_id])))
        s.exec(delete(Source).where(Source.id == source_id))
        s.commit()


def test_note_lifecycle_reindexes_solved_alert(seeded):
    solved_id, _other_id, calls, _user = seeded
    client = TestClient(app)
    base = f"/api/v1/alerts/{solved_id}/notes/"

    # Create
    resp = client.post(base, json={"content": "Cleared WAL logs"})
    assert resp.status_code == 201
    note = resp.json()
    assert note["author"] == "ops"
    assert note["content"] == "Cleared WAL logs"
    note_id = note["id"]

    # List
    listed = client.get(base).json()
    assert [n["id"] for n in listed] == [note_id]

    # Edit
    resp = client.patch(f"{base}{note_id}", json={"content": "Cleared WAL + resized"})
    assert resp.status_code == 200
    assert resp.json()["content"] == "Cleared WAL + resized"

    # Delete
    assert client.delete(f"{base}{note_id}").status_code == 204
    assert client.get(base).json() == []

    # A Solved alert is re-embedded on create, edit, and delete → 3 calls.
    assert calls == [solved_id, solved_id, solved_id]


def test_note_edit_delete_unknown_returns_404(seeded):
    solved_id, _other_id, _calls, _user = seeded
    client = TestClient(app)
    base = f"/api/v1/alerts/{solved_id}/notes/"
    ghost = uuid.uuid4()

    assert client.patch(f"{base}{ghost}", json={"content": "x"}).status_code == 404
    assert client.delete(f"{base}{ghost}").status_code == 404


def test_note_cannot_be_touched_via_wrong_alert(seeded):
    solved_id, other_id, _calls, _user = seeded
    client = TestClient(app)

    created = client.post(
        f"/api/v1/alerts/{solved_id}/notes/",
        json={"content": "belongs to solved"},
    ).json()
    note_id = created["id"]

    # Same note id, but addressed under a different (existing) alert → 404.
    wrong = f"/api/v1/alerts/{other_id}/notes/{note_id}"
    assert client.patch(wrong, json={"content": "hijack"}).status_code == 404
    assert client.delete(wrong).status_code == 404

    # The note is untouched under its real parent.
    still = client.get(f"/api/v1/alerts/{solved_id}/notes/").json()
    assert [n["content"] for n in still] == ["belongs to solved"]


def test_author_comes_from_token_not_body(seeded):
    solved_id, _other_id, _calls, _user = seeded
    client = TestClient(app)

    created = client.post(
        f"/api/v1/alerts/{solved_id}/notes/",
        json={"author": "somebody-else", "content": "x"},
    ).json()
    assert created["author"] == "ops"


def test_only_the_author_can_edit_or_delete(seeded):
    solved_id, _other_id, _calls, session_user = seeded
    client = TestClient(app)
    base = f"/api/v1/alerts/{solved_id}/notes/"

    note_id = client.post(base, json={"content": "ops wrote this"}).json()["id"]

    # Someone else is refused.
    session_user.username = "intruder"
    assert client.patch(f"{base}{note_id}", json={"content": "hijack"}).status_code == 403
    assert client.delete(f"{base}{note_id}").status_code == 403
    assert [n["content"] for n in client.get(base).json()] == ["ops wrote this"]

    # The author still can.
    session_user.username = "ops"
    assert client.patch(f"{base}{note_id}", json={"content": "edited"}).status_code == 200
    assert client.delete(f"{base}{note_id}").status_code == 204
