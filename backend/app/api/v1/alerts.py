"""Alert endpoints — thin routing layer.

Responsibilities:
  1. Validate input via Pydantic schemas.
  2. Delegate to ``alert_service``.
  3. Return the response using ``AlertRead`` (never the raw DB model).

Domain exceptions (``NotFoundError``, ``ConflictError``) raised by the
service layer are automatically mapped to HTTP responses by the
exception handlers registered in ``app.core.exceptions``.
"""

import uuid

from fastapi import APIRouter, Depends, Query, status

from app.api.v1.dependencies import AlertFilterParams, DbSession, PaginationParams
from app.core.exceptions import NotFoundError
from app.models.alert import Alert
from app.schemas.alert import AggregateRequest, AlertCreate, AlertRead, AlertUpdate
from app.schemas.rag import (
    CopilotCitation,
    CopilotResponse,
    CopilotStep,
    SimilarHit,
    SimilarResponse,
)
from app.services.alert import alert_service
from app.services.rag.copilot import get_or_generate_suggestion
from app.services.rag.retriever import find_similar_for_alert

router = APIRouter()


@router.post("/", response_model=AlertRead, status_code=status.HTTP_201_CREATED)
def create_alert(*, session: DbSession, body: AlertCreate) -> AlertRead:
    """Create a new alert. Rejects duplicates via DB-level constraint."""
    db_obj = Alert.model_validate(body.model_dump())
    created = alert_service.create(session, obj_in=db_obj)
    return created


@router.get("/", response_model=list[AlertRead])
def list_alerts(
    *,
    session: DbSession,
    pagination: PaginationParams = Depends(),
    filters: AlertFilterParams = Depends(),
) -> list[AlertRead]:
    """
    List alerts with optional server-side filtering and pagination.

    All filter parameters are optional and combined with AND logic.
    Pagination (``skip``/``limit``) is applied **after** filtering.
    """
    return alert_service.get_filtered(
        session,
        filters=filters.to_dict(),
        skip=pagination.skip,
        limit=pagination.limit,
    )
@router.post("/aggregate", response_model=AlertRead, status_code=status.HTTP_201_CREATED)
def aggregate_alerts(*, session: DbSession, body: AggregateRequest) -> AlertRead:
    """Group multiple alerts into one aggregated alert and dismiss the originals."""
    return alert_service.aggregate(session, alert_ids=body.alert_ids, title=body.title)


@router.get("/{alert_id}", response_model=AlertRead)
def get_alert(*, session: DbSession, alert_id: uuid.UUID) -> AlertRead:
    """Retrieve a single alert by its UUID."""
    alert = alert_service.get(session, id=alert_id)
    if not alert:
        raise NotFoundError("Alert", str(alert_id))
    return alert


@router.get("/{alert_id}/similar", response_model=SimilarResponse)
def get_similar_alerts(
    *,
    session: DbSession,
    alert_id: uuid.UUID,
    top_k: int | None = Query(
        None, ge=1, le=50, description="Max precedents to return (defaults to config)"
    ),
    floor: float | None = Query(
        None, ge=0.0, le=1.0, description="Min cosine similarity (defaults to config)"
    ),
) -> SimilarResponse:
    """Return past resolved alerts / incidents semantically similar to this one.

    Pure semantic search (no LLM). Returns an empty ``hits`` list with
    ``precedent_found=false`` when nothing clears the relevance floor.
    """
    alert = alert_service.get(session, id=alert_id)
    if not alert:
        raise NotFoundError("Alert", str(alert_id))

    query_text, hits = find_similar_for_alert(
        session, alert, top_k=top_k, floor=floor
    )
    return SimilarResponse(
        alert_id=alert_id,
        query_text=query_text,
        precedent_found=bool(hits),
        hits=[SimilarHit(**vars(h)) for h in hits],
    )


@router.get("/{alert_id}/copilot", response_model=CopilotResponse)
def get_copilot_suggestion(
    *,
    session: DbSession,
    alert_id: uuid.UUID,
    top_k: int | None = Query(
        None, ge=1, le=50, description="Max precedents to ground on (config default)"
    ),
    floor: float | None = Query(
        None, ge=0.0, le=1.0, description="Min cosine similarity (config default)"
    ),
    force: bool = Query(
        False, description="Bypass the cache and regenerate the suggestion"
    ),
) -> CopilotResponse:
    """Return a grounded, cited remediation suggestion for an alert.

    Retrieves similar precedents and asks the configured LLM for a structured
    suggestion citing them. Served from cache when unchanged; returns
    ``precedent_found=false`` (no LLM call) when nothing clears the floor.
    """
    alert = alert_service.get(session, id=alert_id)
    if not alert:
        raise NotFoundError("Alert", str(alert_id))

    result, cached = get_or_generate_suggestion(
        session, alert, top_k=top_k, floor=floor, force=force
    )
    return CopilotResponse(
        alert_id=alert_id,
        precedent_found=result.precedent_found,
        provider=result.provider,
        cached=cached,
        diagnosis=result.diagnosis,
        confidence=result.confidence,
        steps=[CopilotStep(**s) for s in result.steps],
        citations=[CopilotCitation(**vars(c)) for c in result.citations],
    )


@router.patch("/{alert_id}", response_model=AlertRead)
def update_alert(
    *, session: DbSession, alert_id: uuid.UUID, body: AlertUpdate
) -> AlertRead:
    """Partially update an alert (e.g. triage its status)."""
    alert = alert_service.get(session, id=alert_id)
    if not alert:
        raise NotFoundError("Alert", str(alert_id))

    update_data = body.model_dump(exclude_unset=True)
    updated = alert_service.update(session, db_obj=alert, update_data=update_data)
    return updated


@router.delete("/{alert_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_alert(*, session: DbSession, alert_id: uuid.UUID) -> None:
    """Permanently delete an alert."""
    alert = alert_service.remove(session, id=alert_id)
    if not alert:
        raise NotFoundError("Alert", str(alert_id))
