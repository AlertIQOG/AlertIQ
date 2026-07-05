"""DB-backed tests for the retriever: ranking, relevance floor, self-exclusion.

Uses the real Postgres engine (pgvector) with a fake query embedding so no
Voyage key or network is required. Inserted rows are cleaned up afterwards.
"""

import uuid

import pytest
from sqlmodel import Session, delete

from app.core.config import settings
from app.core.database import engine
from app.models.rag_chunk import RagChunk
from app.services.rag import retriever
from app.services.rag.embedding import embedding_service

DIM = settings.EMBEDDING_DIM


def _vec(*head: float) -> list[float]:
    """Build a DIM-length vector from leading values, zero-padded."""
    v = list(head) + [0.0] * (DIM - len(head))
    return v[:DIM]


@pytest.fixture
def query_on_e0(monkeypatch):
    """Query vector = unit e0, so similarity == a chunk's first coordinate."""
    monkeypatch.setattr(embedding_service, "embed_query", lambda text: _vec(1.0))
    yield


def _insert(session: Session, rows: list[RagChunk]) -> None:
    for r in rows:
        session.add(r)
    session.commit()


def _cleanup(session: Session, ids: list[uuid.UUID]) -> None:
    session.exec(delete(RagChunk).where(RagChunk.source_id.in_(ids)))
    session.commit()


def _chunk(source_type: str, source_id: uuid.UUID, embedding: list[float]) -> RagChunk:
    return RagChunk(
        source_type=source_type,
        source_id=source_id,
        chunk_index=0,
        content=f"{source_type} {source_id}",
        content_hash=str(source_id),
        embedding=embedding,
        embedding_model="fake",
    )


def test_ranking_floor_and_self_exclusion(query_on_e0):
    self_id = uuid.uuid4()      # identical to query, but must be excluded
    high_id = uuid.uuid4()      # sim 1.0
    mid_id = uuid.uuid4()       # sim 0.6
    low_id = uuid.uuid4()       # sim 0.0 — below floor
    ids = [self_id, high_id, mid_id, low_id]

    with Session(engine) as session:
        try:
            _insert(
                session,
                [
                    _chunk("alert", self_id, _vec(1.0)),
                    _chunk("alert", high_id, _vec(1.0)),
                    _chunk("incident", mid_id, _vec(0.6, 0.8)),
                    _chunk("alert", low_id, _vec(0.0, 1.0)),
                ],
            )

            hits = retriever.search(
                session,
                "query",
                top_k=5,
                floor=0.5,
                exclude=("alert", self_id),
            )

            returned = [h.source_id for h in hits]
            assert self_id not in returned          # self-exclusion
            assert low_id not in returned            # below floor
            assert returned == [high_id, mid_id]     # ranked by similarity
            assert hits[0].similarity == pytest.approx(1.0, abs=1e-3)
            assert hits[1].similarity == pytest.approx(0.6, abs=1e-3)
        finally:
            _cleanup(session, ids)


def test_no_precedent_returns_empty(query_on_e0):
    low_id = uuid.uuid4()  # sim 0.0, will not clear the floor
    with Session(engine) as session:
        try:
            _insert(session, [_chunk("alert", low_id, _vec(0.0, 1.0))])
            hits = retriever.search(session, "query", top_k=5, floor=0.5)
            assert hits == []
        finally:
            _cleanup(session, [low_id])
