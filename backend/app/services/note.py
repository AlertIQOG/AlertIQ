"""Note-specific service logic."""

import uuid

from sqlmodel import Session

from app.models.note import Note
from app.schemas.note import NoteCreate
from app.services.base import CRUDBase


class NoteService(CRUDBase[Note]):
    """CRUD service for notes."""

    def get_by_alert(
        self,
        session: Session,
        *,
        alert_id: uuid.UUID,
        skip: int = 0,
        limit: int = 100,
    ) -> list[Note]:
        """Return all notes belonging to a specific alert, ordered by creation time."""
        return self.get_filtered(
            session,
            filters={"alert_id": alert_id},
            skip=skip,
            limit=limit,
            order_by="created_at",
        )

    def create_for_alert(
        self,
        session: Session,
        *,
        alert_id: uuid.UUID,
        obj_in: NoteCreate,
    ) -> Note:
        """Create a new note attached to the given alert."""
        db_obj = Note(
            alert_id=alert_id,
            author=obj_in.author,
            content=obj_in.content,
        )
        return self.create(session, obj_in=db_obj)


note_service = NoteService(Note)
