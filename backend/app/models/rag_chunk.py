"""RagChunk model — the unified vector store for the Resolution Copilot.

One row per searchable chunk. A chunk points back to its origin record
(``source_type`` + ``source_id``), carries the flattened text that was
embedded, a content hash for idempotent re-indexing, and the embedding
vector itself (pgvector). Retrieval (Phase 2) runs a cosine-similarity
search over the ``embedding`` column.
"""

import uuid
from datetime import datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import Column, DateTime, Index, Text, UniqueConstraint, func
from sqlmodel import Field, SQLModel

from app.core.config import settings


class RagChunk(SQLModel, table=True):
    __tablename__ = "rag_chunks"

    __table_args__ = (
        # One chunk per (origin record, chunk position) — re-indexing updates in place.
        UniqueConstraint(
            "source_type", "source_id", "chunk_index", name="uq_rag_chunk_source"
        ),
        # Approximate-nearest-neighbour index for cosine similarity search.
        Index(
            "ix_rag_chunks_embedding_hnsw",
            "embedding",
            postgresql_using="hnsw",
            postgresql_with={"m": 16, "ef_construction": 64},
            postgresql_ops={"embedding": "vector_cosine_ops"},
        ),
    )

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    # "alert" | "incident"  (runbook reserved for a future phase)
    source_type: str = Field(index=True)
    source_id: uuid.UUID = Field(index=True)
    # 0 for single-chunk sources; reserved for multi-chunk documents later.
    chunk_index: int = Field(default=0)

    content: str = Field(sa_column=Column(Text, nullable=False))
    content_hash: str = Field(index=True)

    embedding: list[float] = Field(
        sa_column=Column(Vector(settings.EMBEDDING_DIM), nullable=False)
    )
    embedding_model: str

    created_at: datetime | None = Field(
        default=None,
        sa_column=Column(
            DateTime(timezone=True), server_default=func.now(), nullable=False
        ),
    )
    updated_at: datetime | None = Field(
        default=None,
        sa_column=Column(
            DateTime(timezone=True),
            server_default=func.now(),
            onupdate=func.now(),
            nullable=False,
        ),
    )
