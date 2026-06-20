"""Alert-specific service logic."""

import uuid
from typing import Any

from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, select

from app.core.exceptions import ConflictError
from app.models.alert import Alert, AlertStatus
from app.schemas.alert import AlertCreate
from app.services.base import CRUDBase
from app.services.rag.indexer import safe_index_alert


class AlertService(CRUDBase[Alert]):
    """
    Extends the generic CRUD with alert-specific business rules.

    Key behaviour:
      - ``create`` is overridden to catch unique-constraint violations
        and raise a domain-level ``ConflictError`` (NOT an HTTPException).
      - ``upsert`` creates a new alert or updates mutable fields on an existing one.
      - ``get_by_source`` adds a filtered query for a specific provider.
      - Inherits ``get_filtered`` from ``CRUDBase`` for dynamic,
        introspection-based server-side filtering.
    """

    def get_by_source(
        self,
        session: Session,
        *,
        source_id: uuid.UUID,
        skip: int = 0,
        limit: int = 100,
    ) -> list[Alert]:
        """Return alerts belonging to a specific source (provider)."""
        return self.get_filtered(
            session,
            filters={"source_id": source_id},
            skip=skip,
            limit=limit,
        )

    def create(self, session: Session, *, obj_in: Alert) -> Alert:
        """
        Insert an alert, catching the DB-level deduplication constraint.

        Raises ``ConflictError`` instead of letting the raw IntegrityError
        bubble up to the router.
        """
        session.add(obj_in)
        try:
            session.commit()
            session.refresh(obj_in)
            return obj_in
        except IntegrityError:
            session.rollback()
            raise ConflictError(
                "An alert with this external_id already exists for this source."
            )

    def upsert(self, session: Session, *, obj_in: AlertCreate) -> tuple[Alert, bool]:
        """
        Insert a new alert or update mutable fields on an existing one.

        Returns ``(alert, created)`` where ``created=True`` means a new row was
        inserted and ``False`` means an existing alert was updated.

        Update rules for existing alerts:
        - ``severity``, ``extra_fields``, ``impact`` are always overwritten with
          the latest values from the provider.
        - ``status`` is only overwritten when the incoming status is ``SOLVED``
          (i.e. the provider resolved the alert).  User-set workflow states like
          ``IN_PROGRESS`` or ``DISMISSED`` are preserved on re-fires.
        - ``created_at`` is never touched; ``updated_at`` is managed by the DB.
        """
        existing = session.exec(
            select(Alert).where(
                Alert.source_id == obj_in.source_id,
                Alert.external_id == obj_in.external_id,
            )
        ).first()

        if existing is not None:
            existing.severity = obj_in.severity
            existing.extra_fields = obj_in.extra_fields
            existing.impact = obj_in.impact
            # Resolved always wins; OPEN does not override user workflow states
            if obj_in.status == AlertStatus.SOLVED:
                existing.status = obj_in.status
            session.commit()
            session.refresh(existing)
            if existing.status == AlertStatus.SOLVED:
                safe_index_alert(session, existing)
            return existing, False

        alert = Alert.model_validate(obj_in.model_dump())
        session.add(alert)
        session.commit()
        session.refresh(alert)
        if alert.status == AlertStatus.SOLVED:
            safe_index_alert(session, alert)
        return alert, True

    def update(
        self, session: Session, *, db_obj: Alert, update_data: dict[str, Any]
    ) -> Alert:
        """Update an alert, indexing it (best-effort) once it becomes Solved."""
        updated = super().update(session, db_obj=db_obj, update_data=update_data)
        if updated.status == AlertStatus.SOLVED:
            safe_index_alert(session, updated)
        return updated


alert_service = AlertService(Alert)

