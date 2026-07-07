"""Endpoints for operational notes nested under alerts."""

import uuid

from fastapi import APIRouter, Depends, status

from app.api.v1.dependencies import DbSession, PaginationParams, ValidAlertId
from app.core.exceptions import NotFoundError
from app.schemas.note import NoteCreate, NoteRead, NoteUpdate
from app.services.note import note_service

router = APIRouter()


@router.get("/", response_model=list[NoteRead])
def list_notes(
    *,
    session: DbSession,
    alert_id: ValidAlertId,
    pagination: PaginationParams = Depends(),
) -> list[NoteRead]:
    """List all notes for a given alert, ordered chronologically."""
    return note_service.get_by_alert(
        session,
        alert_id=alert_id,
        skip=pagination.skip,
        limit=pagination.limit,
    )


@router.post("/", response_model=NoteRead, status_code=status.HTTP_201_CREATED)
def create_note(
    *,
    session: DbSession,
    alert_id: ValidAlertId,
    body: NoteCreate,
) -> NoteRead:
    """Add a new operational note to an alert."""
    return note_service.create_for_alert(
        session,
        alert_id=alert_id,
        obj_in=body,
    )


@router.patch("/{note_id}", response_model=NoteRead)
def update_note(
    *,
    session: DbSession,
    alert_id: ValidAlertId,
    note_id: uuid.UUID,
    body: NoteUpdate,
) -> NoteRead:
    """Edit an existing note's content."""
    note = note_service.update_for_alert(
        session,
        alert_id=alert_id,
        note_id=note_id,
        obj_in=body,
    )
    if note is None:
        raise NotFoundError("Note", str(note_id))
    return note


@router.delete("/{note_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_note(
    *,
    session: DbSession,
    alert_id: ValidAlertId,
    note_id: uuid.UUID,
) -> None:
    """Permanently delete a note from an alert."""
    note = note_service.delete_for_alert(
        session,
        alert_id=alert_id,
        note_id=note_id,
    )
    if note is None:
        raise NotFoundError("Note", str(note_id))
