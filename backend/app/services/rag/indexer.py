"""Indexer — turns domain records into embedded rows in ``rag_chunks``.

Idempotent: a record is only re-embedded when its flattened text (content
hash) or the embedding model changed. The ``safe_*`` wrappers are best-effort
hooks for the live triggers — they never raise, so indexing can never break
ingestion or a status update.
"""

import hashlib
import uuid

from sqlmodel import Session, select

from app.core.logging import logger
from app.models.alert import Alert
from app.models.incident import Incident
from app.models.rag_chunk import RagChunk
from app.services.rag.embedding import embedding_service
from app.services.rag.flatten import flatten_alert, flatten_incident


def _content_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _upsert_chunk(
    session: Session,
    *,
    source_type: str,
    source_id: uuid.UUID,
    chunk_index: int,
    content: str,
) -> tuple[RagChunk, bool]:
    """Insert or update one chunk. Returns ``(chunk, changed)``.

    ``changed=False`` means the content+model were unchanged and no embedding
    call was made (idempotent skip).
    """
    content_hash = _content_hash(content)
    model_name = embedding_service.model

    existing = session.exec(
        select(RagChunk).where(
            RagChunk.source_type == source_type,
            RagChunk.source_id == source_id,
            RagChunk.chunk_index == chunk_index,
        )
    ).first()

    if (
        existing is not None
        and existing.content_hash == content_hash
        and existing.embedding_model == model_name
    ):
        return existing, False

    embedding = embedding_service.embed_documents([content])[0]

    if existing is not None:
        existing.content = content
        existing.content_hash = content_hash
        existing.embedding = embedding
        existing.embedding_model = model_name
        session.add(existing)
        session.commit()
        session.refresh(existing)
        return existing, True

    chunk = RagChunk(
        source_type=source_type,
        source_id=source_id,
        chunk_index=chunk_index,
        content=content,
        content_hash=content_hash,
        embedding=embedding,
        embedding_model=model_name,
    )
    session.add(chunk)
    session.commit()
    session.refresh(chunk)
    return chunk, True


def index_alert(session: Session, alert: Alert) -> tuple[RagChunk, bool]:
    """Embed a resolved alert (message + labels + its resolution notes)."""
    content = flatten_alert(alert, list(alert.notes))
    return _upsert_chunk(
        session,
        source_type="alert",
        source_id=alert.id,
        chunk_index=0,
        content=content,
    )


def index_incident(session: Session, incident: Incident) -> tuple[RagChunk, bool]:
    """Embed a resolved incident."""
    content = flatten_incident(incident)
    return _upsert_chunk(
        session,
        source_type="incident",
        source_id=incident.id,
        chunk_index=0,
        content=content,
    )


# ── Best-effort live triggers ─────────────────────────────────────────
# Wrapped so a missing key or a Voyage outage logs and is swallowed rather
# than failing the surrounding ingestion / status-update request.


def safe_index_alert(session: Session, alert: Alert) -> None:
    if not embedding_service.is_configured():
        return
    try:
        index_alert(session, alert)
    except Exception as exc:  # noqa: BLE001 — best-effort: never break the caller
        session.rollback()
        logger.warning("RAG indexing failed for alert %s: %s", alert.id, exc)


def safe_index_incident(session: Session, incident: Incident) -> None:
    if not embedding_service.is_configured():
        return
    try:
        index_incident(session, incident)
    except Exception as exc:  # noqa: BLE001 — best-effort: never break the caller
        session.rollback()
        logger.warning("RAG indexing failed for incident %s: %s", incident.id, exc)
