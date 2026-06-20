"""Note-specific service logic."""

import uuid

from sqlmodel import Session

from app.models.alert import Alert, AlertStatus
from app.models.note import Note
from app.schemas.note import NoteCreate
from app.services.base import CRUDBase
from app.services.rag.indexer import safe_index_alert


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
        """Create a new note attached to the given alert.

        If the parent alert is already Solved, its embedded chunk includes the
        resolution notes, so re-index it (best-effort) to pick up the new note.
        """
        db_obj = Note(
            alert_id=alert_id,
            author=obj_in.author,
            content=obj_in.content,
        )
        note = self.create(session, obj_in=db_obj)

        alert = session.get(Alert, alert_id)
        if alert is not None and alert.status == AlertStatus.SOLVED:
            safe_index_alert(session, alert)
        return note


note_service = NoteService(Note)
