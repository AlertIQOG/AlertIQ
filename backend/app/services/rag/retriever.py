"""Retriever — semantic search over the RAG chunk store.

Embeds an alert's own fields as a *query* (``input_type="query"``), runs a
cosine-similarity search over ``rag_chunks``, applies a relevance floor, and
returns the ranked precedents. No LLM is involved — this is pure retrieval.
"""

import uuid
from dataclasses import dataclass

from sqlalchemy import text
from sqlmodel import Session, select

from app.core.config import settings
from app.models.alert import Alert
from app.models.rag_chunk import RagChunk
from app.services.rag.embedding import embedding_service
from app.services.rag.flatten import flatten_alert


@dataclass
class RetrievalHit:
    source_type: str
    source_id: uuid.UUID
    chunk_index: int
    similarity: float
    content: str


def build_query_text(alert: Alert) -> str:
    """Flatten the query alert the same way documents are flattened.

    Notes are intentionally excluded: a query alert is usually unresolved, so
    we search on its message + labels only.
    """
    return flatten_alert(alert, notes=[])


def search(
    session: Session,
    query_text: str,
    *,
    top_k: int,
    floor: float,
    exclude: tuple[str, uuid.UUID] | None = None,
) -> list[RetrievalHit]:
    """Return up to ``top_k`` chunks with similarity >= ``floor``, best first.

    ``exclude`` drops a single ``(source_type, source_id)`` from results so an
    alert never matches its own indexed chunk.
    """
    query_vec = embedding_service.embed_query(query_text)

    # Widen the HNSW search beam for this transaction. The default (40) yields
    # poor recall when the corpus contains many near-duplicate vectors — the
    # greedy walk stalls in that cluster and never reaches the real nearest
    # neighbours. SET LOCAL auto-resets at transaction end, so it can't leak to
    # other requests sharing the pooled connection.
    session.exec(
        text("SET LOCAL hnsw.ef_search = :ef").bindparams(
            ef=settings.RAG_HNSW_EF_SEARCH
        )
    )

    # pgvector cosine_distance is 1 - cosine_similarity. Fetch a few extra rows
    # so that excluding the alert's own chunk still leaves up to top_k results.
    distance = RagChunk.embedding.cosine_distance(query_vec)
    statement = (
        select(RagChunk, distance.label("distance"))
        .order_by(distance)
        .limit(top_k + 1)
    )

    hits: list[RetrievalHit] = []
    for chunk, dist in session.exec(statement).all():
        if exclude is not None and (chunk.source_type, chunk.source_id) == exclude:
            continue
        similarity = 1.0 - float(dist)
        if similarity < floor:
            continue
        hits.append(
            RetrievalHit(
                source_type=chunk.source_type,
                source_id=chunk.source_id,
                chunk_index=chunk.chunk_index,
                similarity=similarity,
                content=chunk.content,
            )
        )
        if len(hits) >= top_k:
            break
    return hits


def find_similar_for_alert(
    session: Session,
    alert: Alert,
    *,
    top_k: int | None = None,
    floor: float | None = None,
) -> tuple[str, list[RetrievalHit]]:
    """Find precedents for an alert. Returns ``(query_text, hits)``.

    An empty ``hits`` list means no precedent cleared the relevance floor.
    """
    query_text = build_query_text(alert)
    hits = search(
        session,
        query_text,
        top_k=top_k if top_k is not None else settings.RAG_TOP_K,
        floor=floor if floor is not None else settings.RAG_RELEVANCE_FLOOR,
        exclude=("alert", alert.id),
    )
    return query_text, hits
