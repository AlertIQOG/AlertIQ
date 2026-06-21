"""Indexer — turns domain records into embedded rows in ``rag_chunks``.

Idempotent: a record is only re-embedded when its flattened text (content
hash) or the embedding model changed. The ``safe_*`` wrappers are best-effort
hooks for the live triggers — they never raise, so indexing can never break
ingestion or a status update.
"""

import hashlib
import time
import uuid

from sqlalchemy.engine import Engine
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


# Texts embedded per Google/Voyage request during a batched backfill.
_INDEX_BATCH = 100
# Backfill retry/pacing when a provider rate-limits (free-tier quotas).
_RATELIMIT_WAIT_SECONDS = 62
_MAX_RATELIMIT_RETRIES = 30


def _embed_documents_paced(texts: list[str]) -> list[list[float]]:
    """Embed a batch, retrying when the provider rate-limits (free-tier caps).

    Sleeps ~a minute and retries on a rate-limit error so a long backfill can
    self-pace under a per-minute quota instead of crashing.
    """
    for attempt in range(_MAX_RATELIMIT_RETRIES):
        try:
            return embedding_service.embed_documents(texts)
        except Exception as exc:  # noqa: BLE001 — inspect message for rate limits
            msg = str(exc).lower()
            is_rate_limit = (
                "429" in msg
                or "resource_exhausted" in msg
                or "rate limit" in msg
                or "ratelimit" in msg
                or "quota" in msg
            )
            if not is_rate_limit or attempt == _MAX_RATELIMIT_RETRIES - 1:
                raise
            logger.warning(
                "Embedding rate-limited; sleeping %ds then retrying (attempt %d).",
                _RATELIMIT_WAIT_SECONDS,
                attempt + 1,
            )
            time.sleep(_RATELIMIT_WAIT_SECONDS)
    raise RuntimeError("unreachable")  # pragma: no cover


def index_many(
    engine: Engine,
    items: list[tuple[str, uuid.UUID, int, str]],
) -> int:
    """Batch-index many records — ``items`` is ``(source_type, source_id,
    chunk_index, content)``.

    Designed for long backfills against serverless databases: embedding (and the
    rate-limit sleeps) happen with NO open DB transaction, and each batch is
    written in its own short-lived session. That way an idle connection dropped
    during a sleep can't poison the run. Idempotent (hash-skip) and resumable
    (per-batch commits). Returns the number of chunks (re)embedded.
    """
    model_name = embedding_service.model

    # Snapshot which keys are already up to date — plain tuples, no ORM objects
    # held across the long embedding loop.
    with Session(engine) as s:
        existing_hashes = {
            (r.source_type, r.source_id, r.chunk_index): r.content_hash
            for r in s.exec(select(RagChunk)).all()
            if r.embedding_model == model_name
        }

    pending: list[tuple[str, uuid.UUID, int, str, str]] = []
    for source_type, source_id, chunk_index, content in items:
        content_hash = _content_hash(content)
        key = (source_type, source_id, chunk_index)
        if existing_hashes.get(key) == content_hash:
            continue
        pending.append((source_type, source_id, chunk_index, content, content_hash))

    indexed = 0
    for start in range(0, len(pending), _INDEX_BATCH):
        group = pending[start : start + _INDEX_BATCH]
        # Embed (may sleep on rate-limit) BEFORE opening a DB connection.
        embeddings = _embed_documents_paced([g[3] for g in group])

        with Session(engine) as s:
            for (s_type, s_id, c_idx, content, content_hash), emb in zip(
                group, embeddings
            ):
                existing = s.exec(
                    select(RagChunk).where(
                        RagChunk.source_type == s_type,
                        RagChunk.source_id == s_id,
                        RagChunk.chunk_index == c_idx,
                    )
                ).first()
                if existing is not None:
                    existing.content = content
                    existing.content_hash = content_hash
                    existing.embedding = emb
                    existing.embedding_model = model_name
                    s.add(existing)
                else:
                    s.add(
                        RagChunk(
                            source_type=s_type,
                            source_id=s_id,
                            chunk_index=c_idx,
                            content=content,
                            content_hash=content_hash,
                            embedding=emb,
                            embedding_model=model_name,
                        )
                    )
            s.commit()
        indexed += len(group)
        logger.info("Backfill progress: %d/%d embedded", indexed, len(pending))
    return indexed


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
