"""Endpoints for operational notes nested under alerts."""

import uuid

from fastapi import APIRouter, Depends, status

from app.api.v1.dependencies import (
    CurrentUser,
    DbSession,
    PaginationParams,
    ValidAlertId,
)
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
    current_user: CurrentUser,
) -> NoteRead:
    """Add a new operational note, authored by the authenticated user."""
    return note_service.create_for_alert(
        session,
        alert_id=alert_id,
        obj_in=body,
        author=current_user.username,
    )


@router.patch("/{note_id}", response_model=NoteRead)
def update_note(
    *,
    session: DbSession,
    alert_id: ValidAlertId,
    note_id: uuid.UUID,
    body: NoteUpdate,
    current_user: CurrentUser,
) -> NoteRead:
    """Edit an existing note's content. Only its author may edit it."""
    note = note_service.update_for_alert(
        session,
        alert_id=alert_id,
        note_id=note_id,
        obj_in=body,
        author=current_user.username,
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
    current_user: CurrentUser,
) -> None:
    """Permanently delete a note. Only its author may delete it."""
    note = note_service.delete_for_alert(
        session,
        alert_id=alert_id,
        note_id=note_id,
        author=current_user.username,
    )
    if note is None:
        raise NotFoundError("Note", str(note_id))
