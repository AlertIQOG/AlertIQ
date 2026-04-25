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

from fastapi import APIRouter, Depends, status

from app.api.v1.dependencies import DbSession, PaginationParams
from app.core.exceptions import NotFoundError
from app.models.alert import Alert
from app.schemas.alert import AlertCreate, AlertRead, AlertUpdate
from app.services.alert import alert_service

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
    source_id: uuid.UUID | None = None,
) -> list[AlertRead]:
    """List alerts with optional ``source_id`` filter and pagination."""
    if source_id:
        return alert_service.get_by_source(
            session,
            source_id=source_id,
            skip=pagination.skip,
            limit=pagination.limit,
        )
    return alert_service.get_multi(
        session, skip=pagination.skip, limit=pagination.limit
    )
@router.get("/{alert_id}", response_model=AlertRead)
def get_alert(*, session: DbSession, alert_id: uuid.UUID) -> AlertRead:
    """Retrieve a single alert by its UUID."""
    alert = alert_service.get(session, id=alert_id)
    if not alert:
        raise NotFoundError("Alert", str(alert_id))
    return alert


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
