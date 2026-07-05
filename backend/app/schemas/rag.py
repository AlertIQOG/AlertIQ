"""Pydantic schemas for the Resolution Copilot (RAG) responses."""

import uuid

from pydantic import BaseModel, Field


class SimilarHit(BaseModel):
    """One retrieved chunk, ranked by similarity to the query alert."""

    source_type: str = Field(description="Origin kind: 'alert' or 'incident'")
    source_id: uuid.UUID = Field(description="ID of the origin record")
    chunk_index: int
    similarity: float = Field(
        description="Cosine similarity in [0, 1]; higher is more relevant"
    )
    content: str = Field(description="Flattened text of the chunk (preview)")


class SimilarResponse(BaseModel):
    """Ranked semantic-search results for a given alert."""

    alert_id: uuid.UUID
    query_text: str = Field(description="The text embedded as the search query")
    precedent_found: bool = Field(
        description="False when no hit cleared the relevance floor"
    )
    hits: list[SimilarHit] = Field(default_factory=list)


class CopilotStep(BaseModel):
    """One ordered remediation step with the block numbers that support it."""

    action: str
    citations: list[int] = Field(
        default_factory=list,
        description="Cited context block numbers; empty for generic-triage steps",
    )


class CopilotCitation(BaseModel):
    """A cited context block resolved back to its source record."""

    number: int
    source_type: str
    source_id: uuid.UUID
    similarity: float
    preview: str


class CopilotResponse(BaseModel):
    """Structured, cited remediation suggestion for an alert."""

    alert_id: uuid.UUID
    precedent_found: bool = Field(
        description="False when no precedent cleared the floor (no LLM call made)"
    )
    provider: str = Field(description="Generation provider used (anthropic/google)")
    cached: bool = Field(
        default=False, description="True when served from the cache (no LLM call)"
    )
    diagnosis: str | None = None
    confidence: str | None = Field(
        default=None, description="high | medium | low"
    )
    steps: list[CopilotStep] = Field(default_factory=list)
    citations: list[CopilotCitation] = Field(default_factory=list)
