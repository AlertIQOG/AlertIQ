"""Note-specific service logic."""

import uuid

from sqlmodel import Session

from app.core.exceptions import AuthorizationError
from app.models.alert import Alert, AlertStatus
from app.models.note import Note
from app.schemas.note import NoteCreate, NoteUpdate
from app.services.base import CRUDBase
from app.services.events import event_bus
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
        author: str,
    ) -> Note:
        """Create a new note attached to the given alert.

        ``author`` is supplied by the caller from the authenticated user, so a
        client cannot post a note under someone else's name.

        If the parent alert is already Solved, its embedded chunk includes the
        resolution notes, so re-index it (best-effort) to pick up the new note.
        """
        db_obj = Note(
            alert_id=alert_id,
            author=author,
            content=obj_in.content,
        )
        note = self.create(session, obj_in=db_obj)
        self._reindex_if_solved(session, alert_id)
        # Notes render inside the alert details panel, so signal the alert.
        event_bus.publish("note.created", alert_id)
        return note

    def update_for_alert(
        self,
        session: Session,
        *,
        alert_id: uuid.UUID,
        note_id: uuid.UUID,
        obj_in: NoteUpdate,
        author: str,
    ) -> Note | None:
        """Edit a note's content, re-indexing the parent alert if Solved.

        Returns ``None`` if the note does not exist or belongs to a different
        alert (guards against editing another alert's note via a spoofed URL).
        Raises ``AuthorizationError`` if ``author`` is not the note's author.
        """
        note = self.get(session, id=note_id)
        if note is None or note.alert_id != alert_id:
            return None
        self._assert_author(note, author)

        updated = self.update(
            session, db_obj=note, update_data={"content": obj_in.content}
        )
        self._reindex_if_solved(session, alert_id)
        event_bus.publish("note.updated", alert_id)
        return updated

    def delete_for_alert(
        self,
        session: Session,
        *,
        alert_id: uuid.UUID,
        note_id: uuid.UUID,
        author: str,
    ) -> Note | None:
        """Delete a note, re-indexing the parent alert if Solved.

        Returns ``None`` if the note does not exist or belongs to a different
        alert. Raises ``AuthorizationError`` if ``author`` is not the note's
        author.
        """
        note = self.get(session, id=note_id)
        if note is None or note.alert_id != alert_id:
            return None
        self._assert_author(note, author)

        removed = self.remove(session, id=note_id)
        self._reindex_if_solved(session, alert_id)
        event_bus.publish("note.deleted", alert_id)
        return removed

    @staticmethod
    def _assert_author(note: Note, author: str) -> None:
        """Reject any mutation attempted by someone other than the note's author."""
        if note.author != author:
            raise AuthorizationError("Only the note's author can edit or delete it")

    def _reindex_if_solved(self, session: Session, alert_id: uuid.UUID) -> None:
        """Re-embed the parent alert (best-effort) when it is already Solved.

        A Solved alert's RAG chunk bundles its resolution notes, so any note
        mutation must refresh that chunk. Non-Solved alerts are not embedded
        yet, so there is nothing to update.
        """
        alert = session.get(Alert, alert_id)
        if alert is not None and alert.status == AlertStatus.SOLVED:
            safe_index_alert(session, alert)


note_service = NoteService(Note)
