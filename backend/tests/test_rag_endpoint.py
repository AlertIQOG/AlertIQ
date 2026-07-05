"""End-to-end test of GET /alerts/{id}/similar via the wired FastAPI app.

Uses a fake query embedding (no Voyage key/network); seeds a source, a query
alert, and two precedent chunks in the real DB, then asserts the response.
"""

import uuid

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, delete

from app.core.config import settings
from app.core.database import engine
from app.main import app
from app.models.alert import Alert, AlertSeverity, AlertStatus
from app.models.rag_chunk import RagChunk
from app.models.source import Source
from app.services.rag.embedding import embedding_service

DIM = settings.EMBEDDING_DIM


def _vec(*head: float) -> list[float]:
    return (list(head) + [0.0] * (DIM - len(head)))[:DIM]


@pytest.fixture
def seeded(monkeypatch):
    monkeypatch.setattr(embedding_service, "embed_query", lambda text: _vec(1.0))
    monkeypatch.setattr(embedding_service, "is_configured", lambda: True)

    source_id = uuid.uuid4()
    query_alert_id = uuid.uuid4()
    precedent_id = uuid.uuid4()
    low_id = uuid.uuid4()

    with Session(engine) as s:
        s.add(Source(id=source_id, name="t", provider_type="grafana"))
        s.add(
            Alert(
                id=query_alert_id,
                source_id=source_id,
                external_id=f"q-{query_alert_id}",
                message="Disk full on payments db",
                severity=AlertSeverity.CRITICAL,
                status=AlertStatus.OPEN,
            )
        )
        # The query alert's own chunk (must be excluded), a strong precedent,
        # and a low-similarity chunk (below the default floor).
        s.add(
            RagChunk(
                source_type="alert", source_id=query_alert_id, chunk_index=0,
                content="self", content_hash="self", embedding=_vec(1.0),
                embedding_model="fake",
            )
        )
        s.add(
            RagChunk(
                source_type="alert", source_id=precedent_id, chunk_index=0,
                content="precedent", content_hash="p", embedding=_vec(1.0),
                embedding_model="fake",
            )
        )
        s.add(
            RagChunk(
                source_type="incident", source_id=low_id, chunk_index=0,
                content="unrelated", content_hash="l", embedding=_vec(0.0, 1.0),
                embedding_model="fake",
            )
        )
        s.commit()

    yield query_alert_id, precedent_id

    with Session(engine) as s:
        s.exec(
            delete(RagChunk).where(
                RagChunk.source_id.in_([query_alert_id, precedent_id, low_id])
            )
        )
        s.exec(delete(Alert).where(Alert.id == query_alert_id))
        s.exec(delete(Source).where(Source.id == source_id))
        s.commit()


def test_similar_endpoint_returns_ranked_precedent(seeded):
    query_alert_id, precedent_id = seeded
    client = TestClient(app)

    resp = client.get(f"/api/v1/alerts/{query_alert_id}/similar?floor=0.5")
    assert resp.status_code == 200

    body = resp.json()
    assert body["precedent_found"] is True
    assert body["alert_id"] == str(query_alert_id)
    returned = [h["source_id"] for h in body["hits"]]
    assert str(query_alert_id) not in returned   # self excluded
    assert str(precedent_id) in returned          # strong precedent present
    assert all(h["similarity"] >= 0.5 for h in body["hits"])  # floor respected


def test_similar_endpoint_unknown_alert_404():
    client = TestClient(app)
    resp = client.get(f"/api/v1/alerts/{uuid.uuid4()}/similar")
    assert resp.status_code == 404
