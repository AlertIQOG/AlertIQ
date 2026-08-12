"""Alert-specific service logic."""

import uuid
from enum import Enum
from typing import Any

from sqlalchemy import case
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, select

from app.core.exceptions import ConflictError
from app.models.alert import Alert, AlertSeverity, AlertStatus
from app.schemas.alert import AlertCreate
from app.services.base import CRUDBase
from app.services.events import event_bus
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

    # Semantic ordering ranks for the enum columns. Their stored text would
    # otherwise sort alphabetically (e.g. Info before Warning) — meaningless for
    # triage. Sorting these columns orders by these ranks instead.
    _SEMANTIC_ORDER = {"severity", "status"}

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

    # Columns exposed as feed filters whose values come from the data. Each is
    # indexed, so ``SELECT DISTINCT`` runs as an index-only scan (fast on a large
    # table). ``source`` is not a column — it lives in ``extra_fields`` JSONB and
    # is handled separately by ``distinct_sources``.
    _FILTERABLE_COLUMNS = frozenset(
        {"severity", "status", "region", "application", "component"}
    )

    def distinct_column_values(self, session: Session, column: str) -> list[str]:
        """Return the distinct, non-empty values of a filterable column, sorted."""
        if column not in self._FILTERABLE_COLUMNS:
            return []
        col = getattr(Alert, column)
        rows = session.exec(select(col).where(col.is_not(None)).distinct()).all()
        # Enum columns (severity/status) come back as members; use their value.
        values = [v.value if isinstance(v, Enum) else v for v in rows]
        return sorted({v for v in values if v})

    def distinct_sources(self, session: Session) -> list[str]:
        """Return the distinct ingest providers from ``extra_fields.source``.

        Backed by the ``ix_alerts_source`` expression index.
        """
        expr = Alert.extra_fields["source"].astext
        rows = session.exec(select(expr).where(expr.is_not(None)).distinct()).all()
        return sorted({r for r in rows if r})

    def get_filtered(
        self,
        session: Session,
        *,
        filters: dict[str, Any],
        skip: int = 0,
        limit: int = 100,
        order_by: str | None = None,
        order_desc: bool = False,
    ) -> list[Alert]:
        """Filter alerts, ordering severity/status by meaning, not text.

        For every other column this defers to the generic column ordering in
        ``CRUDBase.get_filtered``.
        """
        if order_by not in self._SEMANTIC_ORDER:
            return super().get_filtered(
                session,
                filters=filters,
                skip=skip,
                limit=limit,
                order_by=order_by,
                order_desc=order_desc,
            )

        rank = self._semantic_rank(order_by)
        statement = self._apply_filters(select(Alert), filters)
        # Tiebreakers keep OFFSET pagination stable — severity/status have
        # only four values, so almost every row is tied.
        statement = statement.order_by(
            rank.desc() if order_desc else rank.asc(),
            Alert.created_at.desc(),
            Alert.id,
        )
        statement = statement.offset(skip).limit(limit)
        return list(session.exec(statement).all())

    @staticmethod
    def _semantic_rank(column: str) -> Any:
        """Build the CASE expression that ranks an enum column by triage order."""
        if column == "severity":
            return case(
                (Alert.severity == AlertSeverity.CRITICAL, 4),
                (Alert.severity == AlertSeverity.ERROR, 3),
                (Alert.severity == AlertSeverity.WARNING, 2),
                (Alert.severity == AlertSeverity.INFO, 1),
                else_=0,
            )
        return case(
            (Alert.status == AlertStatus.OPEN, 1),
            (Alert.status == AlertStatus.IN_PROGRESS, 2),
            (Alert.status == AlertStatus.SOLVED, 3),
            (Alert.status == AlertStatus.DISMISSED, 4),
            else_=99,
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
            event_bus.publish("alert.created", obj_in.id)
            return obj_in
        except IntegrityError:
            session.rollback()
            raise ConflictError(
                "An alert with this external_id already exists for this source."
            )

    def _apply_provider_update(
        self,
        session: Session,
        *,
        existing: Alert,
        obj_in: AlertCreate,
    ) -> Alert:
        """
        Apply the latest provider state to an existing alert.

        Provider-controlled fields are refreshed on every delivery while
        operator-controlled workflow states are preserved unless the provider
        explicitly resolves the alert or re-fires a previously resolved /
        correlation-dismissed alert.
        """
        was_correlated = bool(
            (existing.extra_fields or {}).get("_correlated_into")
        )

        existing.severity = obj_in.severity
        existing.extra_fields = obj_in.extra_fields
        existing.impact = obj_in.impact

        if obj_in.status == AlertStatus.SOLVED:
            existing.status = AlertStatus.SOLVED

        elif obj_in.status == AlertStatus.OPEN and (
            existing.status == AlertStatus.SOLVED
            or (
                existing.status == AlertStatus.DISMISSED
                and was_correlated
            )
        ):
            existing.status = AlertStatus.OPEN

        session.add(existing)
        session.commit()
        session.refresh(existing)

        if existing.status == AlertStatus.SOLVED:
            safe_index_alert(session, existing)

        event_bus.publish("alert.updated", existing.id)

        return existing


    def _find_provider_alert(
        self,
        session: Session,
        *,
        source_id: uuid.UUID,
        external_id: str,
    ) -> Alert | None:
        """
        Look up an alert by the provider identity protected by the database
        unique constraint.
        """
        return session.exec(
            select(Alert).where(
                Alert.source_id == source_id,
                Alert.external_id == external_id,
            )
        ).first()
    
    def upsert(
        self,
        session: Session,
        *,
        obj_in: AlertCreate,
    ) -> tuple[Alert, bool]:
        """
        Insert a new alert or update an existing provider alert.

        The database unique constraint remains the final authority for
        deduplication. If two webhook deliveries race to insert the same alert,
        the losing transaction is rolled back and the row created by the winning
        transaction is loaded and updated instead of returning a raw 500.

        Returns:
            tuple[Alert, bool]:
                The persisted alert and whether this call created it.
        """
        existing = self._find_provider_alert(
            session,
            source_id=obj_in.source_id,
            external_id=obj_in.external_id,
        )

        if existing is not None:
            updated = self._apply_provider_update(
                session,
                existing=existing,
                obj_in=obj_in,
            )
            return updated, False

        alert = Alert.model_validate(obj_in.model_dump())
        session.add(alert)

        try:
            session.commit()
            session.refresh(alert)

        except IntegrityError:
            # Another request may have inserted the same provider alert between
            # our initial SELECT and INSERT.
            session.rollback()

            existing = self._find_provider_alert(
                session,
                source_id=obj_in.source_id,
                external_id=obj_in.external_id,
            )

            if existing is None:
                # The integrity failure was caused by something other than the
                # expected source_id/external_id race. Preserve the real failure
                # instead of pretending deduplication succeeded.
                raise

            updated = self._apply_provider_update(
                session,
                existing=existing,
                obj_in=obj_in,
            )

            return updated, False

        if alert.status == AlertStatus.SOLVED:
            safe_index_alert(session, alert)

        event_bus.publish("alert.created", alert.id)

        return alert, True

    def update(
        self, session: Session, *, db_obj: Alert, update_data: dict[str, Any]
    ) -> Alert:
        """Update an alert, indexing it (best-effort) once it becomes Solved."""
        updated = super().update(session, db_obj=db_obj, update_data=update_data)
        if updated.status == AlertStatus.SOLVED:
            safe_index_alert(session, updated)
        event_bus.publish("alert.updated", updated.id)
        return updated

    def remove(self, session: Session, *, id: uuid.UUID) -> Alert | None:
        """Delete an alert, notifying live subscribers on success."""
        removed = super().remove(session, id=id)
        if removed is not None:
            event_bus.publish("alert.deleted", id)
        return removed


    def aggregate(
        self,
        session: Session,
        *,
        alert_ids: list[uuid.UUID],
        title: str | None = None,
    ) -> Alert:
        """
        Group multiple alerts into a single aggregated alert.

        Creates a new alert that summarises all children, marks the
        originals as Dismissed, and stores child IDs in extra_fields.
        """
        children = [self.get(session, id=aid) for aid in alert_ids]
        children = [a for a in children if a is not None]
        if not children:
            from app.core.exceptions import NotFoundError
            raise NotFoundError("Alert", str(alert_ids[0]) if alert_ids else "unknown")

        severity_order = [
            AlertSeverity.CRITICAL,
            AlertSeverity.ERROR,
            AlertSeverity.WARNING,
            AlertSeverity.INFO,
        ]
        highest = next(
            (s for s in severity_order if any(a.severity == s for a in children)),
            AlertSeverity.INFO,
        )

        agg_message = title or f"Aggregated: {len(children)} alerts — {children[0].message[:80]}"

        aggregated = Alert(
            source_id=children[0].source_id,
            external_id=str(uuid.uuid4()),
            message=agg_message,
            application=children[0].application,
            region=children[0].region,
            severity=highest,
            status=AlertStatus.OPEN,
            extra_fields={
                "_is_aggregated": True,
                "_child_ids": [str(a.id) for a in children],
                "_child_count": len(children),
            },
        )
        session.add(aggregated)

        for child in children:
            child.status = AlertStatus.DISMISSED

        session.commit()
        session.refresh(aggregated)
        event_bus.publish("alert.created", aggregated.id)
        return aggregated


alert_service = AlertService(Alert)

