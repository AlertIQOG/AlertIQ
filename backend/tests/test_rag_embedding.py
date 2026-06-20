"""Offline unit tests for the embedding service guard rails (no network)."""

import pytest

from app.core.config import settings
from app.core.exceptions import ConfigurationError
from app.services.rag.embedding import EmbeddingService


def test_is_configured_reflects_voyage_key(monkeypatch):
    monkeypatch.setattr(settings, "EMBEDDING_PROVIDER", "voyage")
    monkeypatch.setattr(settings, "VOYAGE_API_KEY", "")
    assert EmbeddingService().is_configured() is False

    monkeypatch.setattr(settings, "VOYAGE_API_KEY", "vk-test")
    assert EmbeddingService().is_configured() is True


def test_is_configured_reflects_google_key(monkeypatch):
    monkeypatch.setattr(settings, "EMBEDDING_PROVIDER", "google")
    monkeypatch.setattr(settings, "GOOGLE_API_KEY", "")
    assert EmbeddingService().is_configured() is False

    monkeypatch.setattr(settings, "GOOGLE_API_KEY", "gk-test")
    assert EmbeddingService().is_configured() is True


def test_voyage_embed_without_key_raises(monkeypatch):
    monkeypatch.setattr(settings, "EMBEDDING_PROVIDER", "voyage")
    monkeypatch.setattr(settings, "VOYAGE_API_KEY", "")
    service = EmbeddingService()
    with pytest.raises(ConfigurationError):
        service.embed_query("anything")
    with pytest.raises(ConfigurationError):
        service.embed_documents(["anything"])


def test_google_embed_without_key_raises(monkeypatch):
    monkeypatch.setattr(settings, "EMBEDDING_PROVIDER", "google")
    monkeypatch.setattr(settings, "GOOGLE_API_KEY", "")
    service = EmbeddingService()
    with pytest.raises(ConfigurationError):
        service.embed_query("anything")
    with pytest.raises(ConfigurationError):
        service.embed_documents(["anything"])
