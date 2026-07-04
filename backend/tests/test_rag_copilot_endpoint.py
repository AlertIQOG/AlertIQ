"""End-to-end test of GET /alerts/{id}/copilot via the wired FastAPI app.

Uses a fake query embedding and a fake generation provider (no keys/network);
seeds a query alert + a precedent chunk in the real DB, then asserts the
structured, cited response.
"""

import uuid

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, delete

from app.core.config import settings
from app.core.database import engine
from app.main import app
from app.models.alert import Alert, AlertSeverity, AlertStatus
from app.models.copilot_suggestion import CopilotSuggestion
from app.models.rag_chunk import RagChunk
from app.models.source import Source
from app.services.rag.embedding import embedding_service
from app.services.rag.generation import generation_service

DIM = settings.EMBEDDING_DIM


def _vec(*head: float) -> list[float]:
    return (list(head) + [0.0] * (DIM - len(head)))[:DIM]


@pytest.fixture
def seeded(monkeypatch):
    monkeypatch.setattr(embedding_service, "embed_query", lambda text: _vec(1.0))
    # Fake generation: cites block 1, plus an uncited generic step.
    monkeypatch.setattr(
        generation_service,
        "generate",
        lambda **kwargs: {
            "diagnosis": "Disk filled by WAL logs",
            "confidence": "high",
            "steps": [
                {"action": "Clear old WAL logs", "citations": [1]},
                {"action": "Check disk usage", "citations": []},
            ],
        },
    )

    source_id = uuid.uuid4()
    alert_id = uuid.uuid4()
    precedent_id = uuid.uuid4()

    with Session(engine) as s:
        s.add(Source(id=source_id, name="t", provider_type="grafana"))
        s.add(
            Alert(
                id=alert_id,
                source_id=source_id,
                external_id=f"q-{alert_id}",
                message="Disk full on payments db",
                severity=AlertSeverity.CRITICAL,
                status=AlertStatus.OPEN,
            )
        )
        s.add(
            RagChunk(
                source_type="alert", source_id=precedent_id, chunk_index=0,
                content="[ALERT] Message: Disk full\nResolution notes:\n- Cleared WAL",
                content_hash="p", embedding=_vec(1.0), embedding_model="fake",
            )
        )
        s.commit()

    yield alert_id, precedent_id

    with Session(engine) as s:
        s.exec(delete(CopilotSuggestion).where(CopilotSuggestion.alert_id == alert_id))
        s.exec(delete(RagChunk).where(RagChunk.source_id.in_([precedent_id])))
        s.exec(delete(Alert).where(Alert.id == alert_id))
        s.exec(delete(Source).where(Source.id == source_id))
        s.commit()


def test_copilot_returns_structured_cited_suggestion(seeded):
    alert_id, precedent_id = seeded
    client = TestClient(app)

    resp = client.get(f"/api/v1/alerts/{alert_id}/copilot?floor=0.5")
    assert resp.status_code == 200

    body = resp.json()
    assert body["precedent_found"] is True
    assert body["diagnosis"] == "Disk filled by WAL logs"
    assert body["confidence"] == "high"
    assert len(body["steps"]) == 2
    assert body["steps"][0]["citations"] == [1]
    assert body["steps"][1]["citations"] == []

    # Block 1 resolved back to the precedent record.
    assert len(body["citations"]) == 1
    citation = body["citations"][0]
    assert citation["number"] == 1
    assert citation["source_id"] == str(precedent_id)
    assert citation["source_type"] == "alert"


def test_copilot_unknown_alert_404():
    client = TestClient(app)
    resp = client.get(f"/api/v1/alerts/{uuid.uuid4()}/copilot")
    assert resp.status_code == 404
