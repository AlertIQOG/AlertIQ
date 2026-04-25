"""Alert-specific service logic."""

import uuid

from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, select

from app.core.exceptions import ConflictError
from app.models.alert import Alert
from app.services.base import CRUDBase


class AlertService(CRUDBase[Alert]):
    """
    Extends the generic CRUD with alert-specific business rules.

    Key behaviour:
      - ``create`` is overridden to catch unique-constraint violations
        and raise a domain-level ``ConflictError`` (NOT an HTTPException).
      - ``get_by_source`` adds a filtered query for a specific provider.
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
        statement = (
            select(self.model)
            .where(self.model.source_id == source_id)
            .offset(skip)
            .limit(limit)
        )
        return list(session.exec(statement).all())

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


alert_service = AlertService(Alert)
