"""DB-backed tests for copilot answer caching."""

import uuid

import pytest
from sqlmodel import Session, delete

from app.core.config import settings
from app.core.database import engine
from app.models.alert import Alert, AlertSeverity, AlertStatus
from app.models.copilot_suggestion import CopilotSuggestion
from app.models.rag_chunk import RagChunk
from app.models.source import Source
from app.services.rag.copilot import get_or_generate_suggestion
from app.services.rag.embedding import embedding_service
from app.services.rag.generation import generation_service

DIM = settings.EMBEDDING_DIM


def _vec(*head: float) -> list[float]:
    return (list(head) + [0.0] * (DIM - len(head)))[:DIM]


@pytest.fixture
def seeded(monkeypatch):
    calls = {"n": 0}

    def fake_generate(**kwargs):
        calls["n"] += 1
        return {
            "diagnosis": "Disk filled by WAL logs",
            "confidence": "high",
            "steps": [{"action": "Clear old WAL logs", "citations": [1]}],
        }

    monkeypatch.setattr(embedding_service, "embed_query", lambda text: _vec(1.0))
    monkeypatch.setattr(generation_service, "generate", fake_generate)

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
                content="[ALERT] Message: Disk full", content_hash="p",
                embedding=_vec(1.0), embedding_model="fake",
            )
        )
        s.commit()

    yield alert_id, precedent_id, calls

    with Session(engine) as s:
        s.exec(delete(CopilotSuggestion).where(CopilotSuggestion.alert_id == alert_id))
        s.exec(delete(RagChunk).where(RagChunk.source_id.in_([precedent_id])))
        s.exec(delete(Alert).where(Alert.id == alert_id))
        s.exec(delete(Source).where(Source.id == source_id))
        s.commit()


def test_second_call_served_from_cache_without_generating(seeded):
    alert_id, _, calls = seeded
    with Session(engine) as s:
        alert = s.get(Alert, alert_id)

        result1, cached1 = get_or_generate_suggestion(s, alert, floor=0.5)
        assert cached1 is False
        assert result1.diagnosis == "Disk filled by WAL logs"
        assert calls["n"] == 1

        result2, cached2 = get_or_generate_suggestion(s, alert, floor=0.5)
        assert cached2 is True               # served from cache
        assert calls["n"] == 1               # generation NOT called again
        assert result2.diagnosis == "Disk filled by WAL logs"
        assert [c.number for c in result2.citations] == [1]


def test_force_bypasses_cache(seeded):
    alert_id, _, calls = seeded
    with Session(engine) as s:
        alert = s.get(Alert, alert_id)

        get_or_generate_suggestion(s, alert, floor=0.5)
        assert calls["n"] == 1

        _, cached = get_or_generate_suggestion(s, alert, floor=0.5, force=True)
        assert cached is False
        assert calls["n"] == 2               # regenerated


def test_content_change_invalidates_cache(seeded):
    alert_id, _, calls = seeded
    with Session(engine) as s:
        alert = s.get(Alert, alert_id)
        get_or_generate_suggestion(s, alert, floor=0.5)
        assert calls["n"] == 1

        # Mutate the alert's queryable content → hash changes → cache miss.
        alert.message = "Completely different alert message"
        s.add(alert)
        s.commit()

        _, cached = get_or_generate_suggestion(s, alert, floor=0.5)
        assert cached is False
        assert calls["n"] == 2
