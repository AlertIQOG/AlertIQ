"""Source endpoints — thin routing layer.

Same conventions as ``alerts.py``:
  - Validate input with Pydantic schemas.
  - Delegate to ``source_service``.
  - Return ``SourceRead``, never the raw DB model.
"""

import secrets
import uuid

from fastapi import APIRouter, Depends, status

from app.api.v1.dependencies import DbSession, PaginationParams
from app.core.exceptions import NotFoundError
from app.models.source import Source
from app.schemas.source import SourceCreate, SourceRead, SourceUpdate
from app.services.source import source_service

router = APIRouter()


@router.post("/", response_model=SourceRead, status_code=status.HTTP_201_CREATED)
def create_source(*, session: DbSession, body: SourceCreate) -> SourceRead:
    """Register a new alert-source provider.

    A webhook secret is generated server-side; configure the provider to
    send it as the ``X-Webhook-Token`` header on ingest requests.
    """
    db_obj = Source.model_validate(body.model_dump())
    db_obj.webhook_secret = secrets.token_urlsafe(32)
    created = source_service.create(session, obj_in=db_obj)
    return created


@router.get("/", response_model=list[SourceRead])
def list_sources(
    *, session: DbSession, pagination: PaginationParams = Depends()
) -> list[SourceRead]:
    """List all source providers with pagination."""
    return source_service.get_multi(
        session, skip=pagination.skip, limit=pagination.limit
    )


@router.get("/{source_id}", response_model=SourceRead)
def get_source(*, session: DbSession, source_id: uuid.UUID) -> SourceRead:
    """Retrieve a single source by its UUID."""
    source = source_service.get(session, id=source_id)
    if not source:
        raise NotFoundError("Source", str(source_id))
    return source


@router.patch("/{source_id}", response_model=SourceRead)
def update_source(
    *, session: DbSession, source_id: uuid.UUID, body: SourceUpdate
) -> SourceRead:
    """Partially update a source provider."""
    source = source_service.get(session, id=source_id)
    if not source:
        raise NotFoundError("Source", str(source_id))

    update_data = body.model_dump(exclude_unset=True)
    updated = source_service.update(session, db_obj=source, update_data=update_data)
    return updated


@router.delete("/{source_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_source(*, session: DbSession, source_id: uuid.UUID) -> None:
    """Delete a source and cascade-delete all its attached alerts."""
    source = source_service.remove(session, id=source_id)
    if not source:
        raise NotFoundError("Source", str(source_id))
