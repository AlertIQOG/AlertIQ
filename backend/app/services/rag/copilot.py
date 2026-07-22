"""Copilot orchestration — retrieval → grounded generation → cited suggestion.

Ties the relevance floor (is there anything to say?) to the grounded prompt
(say it only from the retrieved context). If no precedent clears the floor, no
LLM call is made — the suggestion is "no precedent found".
"""

import hashlib
import uuid
from dataclasses import dataclass, field

from sqlalchemy import func
from sqlmodel import Session, select

from app.models.alert import Alert
from app.models.copilot_suggestion import CopilotSuggestion
from app.models.rag_chunk import RagChunk
from app.services.rag.generation import (
    SYSTEM_PROMPT,
    build_user_prompt,
    generation_service,
)
from app.services.rag.retriever import (
    RetrievalHit,
    build_query_text,
    find_similar_for_alert,
)

_PREVIEW_CHARS = 240


@dataclass
class ResolvedCitation:
    number: int
    source_type: str
    source_id: uuid.UUID
    similarity: float
    preview: str


@dataclass
class CopilotResult:
    precedent_found: bool
    provider: str
    diagnosis: str | None = None
    confidence: str | None = None
    steps: list[dict] = field(default_factory=list)
    citations: list[ResolvedCitation] = field(default_factory=list)


def _resolve_citations(
    steps: list[dict], hits: list[RetrievalHit]
) -> list[ResolvedCitation]:
    """Map block numbers cited across all steps back to their source records.

    Out-of-range numbers (hallucinated by the model) are dropped.
    """
    cited = sorted(
        {n for step in steps for n in step.get("citations", []) if isinstance(n, int)}
    )
    resolved: list[ResolvedCitation] = []
    for number in cited:
        if 1 <= number <= len(hits):
            hit = hits[number - 1]
            resolved.append(
                ResolvedCitation(
                    number=number,
                    source_type=hit.source_type,
                    source_id=hit.source_id,
                    similarity=hit.similarity,
                    preview=hit.content[:_PREVIEW_CHARS],
                )
            )
    return resolved


def generate_suggestion(
    session: Session,
    alert: Alert,
    *,
    top_k: int | None = None,
    floor: float | None = None,
) -> CopilotResult:
    """Produce a grounded, cited remediation suggestion for an alert."""
    query_text, hits = find_similar_for_alert(
        session, alert, top_k=top_k, floor=floor
    )

    # Relevance floor decides whether there is anything to say — no hits, no LLM.
    if not hits:
        return CopilotResult(
            precedent_found=False, provider=generation_service.provider
        )

    user_prompt = build_user_prompt(query_text, hits)
    data = generation_service.generate(system=SYSTEM_PROMPT, user=user_prompt)

    steps = [
        {"action": s["action"], "citations": list(s.get("citations", []))}
        for s in data.get("steps", [])
    ]
    return CopilotResult(
        precedent_found=True,
        provider=generation_service.provider,
        diagnosis=data.get("diagnosis"),
        confidence=data.get("confidence"),
        steps=steps,
        citations=_resolve_citations(steps, hits),
    )


# ── Caching ───────────────────────────────────────────────────────────


def _corpus_fingerprint(session: Session) -> str:
    """A cheap fingerprint of the RAG corpus state.

    Returns ``"<count>:<latest updated_at>"`` over ``rag_chunks``. Re-indexing a
    record updates its chunk in place (bumping ``updated_at``) and new records
    add rows, so this value changes exactly when the searchable corpus changes —
    and is stable when it does not. Folding it into the cache key lets a note or
    precedent edit lazily invalidate suggestions that were grounded on the old
    corpus, without any embedding/LLM cost on a cache hit.
    """
    count, latest = session.exec(
        select(func.count(RagChunk.id), func.max(RagChunk.updated_at))
    ).one()
    return f"{count}:{latest.isoformat() if latest else '0'}"


def _content_hash(session: Session, alert: Alert) -> str:
    """Cache invalidation key: the alert's queryable content + corpus state.

    Combines the query text (so an edit to the alert's own message/labels busts
    the cache) with the corpus fingerprint (so an edit to a precedent or its
    notes busts it too).
    """
    basis = f"{build_query_text(alert)}|corpus={_corpus_fingerprint(session)}"
    return hashlib.sha256(basis.encode("utf-8")).hexdigest()


def _to_payload(result: CopilotResult) -> dict:
    return {
        "precedent_found": result.precedent_found,
        "diagnosis": result.diagnosis,
        "confidence": result.confidence,
        "steps": result.steps,
        "citations": [
            {
                "number": c.number,
                "source_type": c.source_type,
                "source_id": str(c.source_id),
                "similarity": c.similarity,
                "preview": c.preview,
            }
            for c in result.citations
        ],
    }


def _from_payload(payload: dict, provider: str) -> CopilotResult:
    citations = [
        ResolvedCitation(
            number=c["number"],
            source_type=c["source_type"],
            source_id=uuid.UUID(c["source_id"]),
            similarity=c["similarity"],
            preview=c["preview"],
        )
        for c in payload.get("citations", [])
    ]
    return CopilotResult(
        precedent_found=payload["precedent_found"],
        provider=provider,
        diagnosis=payload.get("diagnosis"),
        confidence=payload.get("confidence"),
        steps=payload.get("steps", []),
        citations=citations,
    )


def get_or_generate_suggestion(
    session: Session,
    alert: Alert,
    *,
    top_k: int | None = None,
    floor: float | None = None,
    force: bool = False,
) -> tuple[CopilotResult, bool]:
    """Return ``(result, cached)``.

    Serves a cached suggestion when its content hash and provider match and
    ``force`` is false; otherwise (re)generates and upserts the cache row.
    """
    content_hash = _content_hash(session, alert)
    provider = generation_service.provider

    cached = session.exec(
        select(CopilotSuggestion).where(CopilotSuggestion.alert_id == alert.id)
    ).first()

    if (
        not force
        and cached is not None
        and cached.content_hash == content_hash
        and cached.provider == provider
    ):
        return _from_payload(cached.payload, provider), True

    result = generate_suggestion(session, alert, top_k=top_k, floor=floor)
    payload = _to_payload(result)

    if cached is not None:
        cached.content_hash = content_hash
        cached.provider = provider
        cached.payload = payload
        session.add(cached)
    else:
        session.add(
            CopilotSuggestion(
                alert_id=alert.id,
                content_hash=content_hash,
                provider=provider,
                payload=payload,
            )
        )
    session.commit()
    return result, False
