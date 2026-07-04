"""Unit tests for prompt assembly and copilot orchestration (mocked provider)."""

import uuid

from app.core.config import settings
from app.services.rag import copilot as copilot_mod
from app.services.rag.copilot import generate_suggestion
from app.services.rag.generation import build_context_blocks, generation_service
from app.services.rag.retriever import RetrievalHit


def _hit(label: str, source_type: str = "alert") -> RetrievalHit:
    return RetrievalHit(
        source_type=source_type,
        source_id=uuid.uuid4(),
        chunk_index=0,
        similarity=0.91,
        content=f"content {label}",
    )


def test_build_context_blocks_numbers_hits_from_one():
    text = build_context_blocks([_hit("A"), _hit("B")])
    assert "[1]" in text and "[2]" in text
    assert "content A" in text and "content B" in text


def test_is_configured_reflects_provider_key(monkeypatch):
    monkeypatch.setattr(settings, "LLM_PROVIDER", "anthropic")
    monkeypatch.setattr(settings, "ANTHROPIC_API_KEY", "")
    assert generation_service.is_configured() is False
    monkeypatch.setattr(settings, "ANTHROPIC_API_KEY", "sk-test")
    assert generation_service.is_configured() is True

    monkeypatch.setattr(settings, "LLM_PROVIDER", "google")
    monkeypatch.setattr(settings, "GOOGLE_API_KEY", "")
    assert generation_service.is_configured() is False


def test_no_precedent_short_circuits_without_calling_llm(monkeypatch):
    calls = {"n": 0}

    def fake_generate(**kwargs):
        calls["n"] += 1
        return {}

    monkeypatch.setattr(generation_service, "generate", fake_generate)
    monkeypatch.setattr(
        copilot_mod, "find_similar_for_alert", lambda s, a, **k: ("query", [])
    )

    result = generate_suggestion(None, object())
    assert result.precedent_found is False
    assert result.steps == [] and result.citations == []
    assert calls["n"] == 0  # the floor gated generation — no LLM call


def test_citation_resolution_maps_numbers_and_drops_out_of_range(monkeypatch):
    h1, h2 = _hit("A", "alert"), _hit("B", "incident")
    monkeypatch.setattr(
        copilot_mod, "find_similar_for_alert", lambda s, a, **k: ("query", [h1, h2])
    )
    fake = {
        "diagnosis": "Disk filled by WAL logs",
        "confidence": "high",
        "steps": [
            {"action": "Clear old WAL logs", "citations": [1, 99]},  # 99 hallucinated
            {"action": "Generic: check disk usage", "citations": []},  # uncited
        ],
    }
    monkeypatch.setattr(generation_service, "generate", lambda **k: fake)

    result = generate_suggestion(None, object())
    assert result.precedent_found is True
    assert result.diagnosis == "Disk filled by WAL logs"
    assert result.confidence == "high"
    assert len(result.steps) == 2
    # Only block 1 resolves; 99 is out of range and dropped; step 2 cites nothing.
    assert [c.number for c in result.citations] == [1]
    assert result.citations[0].source_type == "alert"
    assert result.citations[0].source_id == h1.source_id
