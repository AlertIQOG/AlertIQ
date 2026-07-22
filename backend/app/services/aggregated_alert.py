"""
Persistence layer for :class:`~app.models.aggregated_alert.AggregatedAlert`.

This service is a thin wrapper around the DB: the *decision* logic (how an
aggregate is built and mutated) lives in the pure helpers
``build_aggregate`` / ``apply_member`` in
:mod:`app.services.correlation_engine`.  Here we only run queries and flush the
mutations those helpers produce.
"""

import uuid
from datetime import datetime
from typing import Any

from sqlmodel import Session, select

from app.models.aggregated_alert import AggregatedAlert, AggregatedAlertStatus
from app.models.alert import Alert
from app.models.correlation_rule import CorrelationRule
from app.services.base import CRUDBase
from app.services.correlation_engine import apply_member, build_aggregate
from app.services.events import event_bus


class AggregatedAlertService(CRUDBase[AggregatedAlert]):
    """CRUD + correlation-specific persistence for aggregated alerts."""

    def find_open(
        self,
        session: Session,
        *,
        rule_id: uuid.UUID,
        group_key: str,
    ) -> AggregatedAlert | None:
        """
        Return the single OPEN aggregate for a ``(rule, group_key)`` pair, or
        ``None``.  At most one open aggregate exists per pair at a time; if
        several somehow exist we take the most recent by ``first_seen``.
        """
        statement = (
            select(AggregatedAlert)
            .where(
                AggregatedAlert.rule_id == rule_id,
                AggregatedAlert.group_key == group_key,
                AggregatedAlert.status == AggregatedAlertStatus.OPEN,
            )
            .order_by(AggregatedAlert.first_seen.desc())
        )
        return session.exec(statement).first()

    def list_open(self, session: Session, *, limit: int = 500) -> list[AggregatedAlert]:
        """Return all currently-open aggregates, newest activity first."""
        statement = (
            select(AggregatedAlert)
            .where(AggregatedAlert.status == AggregatedAlertStatus.OPEN)
            .order_by(AggregatedAlert.last_seen.desc())
            .limit(limit)
        )
        return list(session.exec(statement).all())

    def create_from_alert(
        self,
        session: Session,
        *,
        rule: CorrelationRule,
        alert: Alert,
        group_key: str,
        group_values: dict[str, Any],
        now: datetime,
    ) -> AggregatedAlert:
        """Open a new aggregate seeded with ``alert`` as its first member."""
        aggregate = build_aggregate(rule, alert, group_key, group_values, now)
        session.add(aggregate)
        session.commit()
        session.refresh(aggregate)
        event_bus.publish("aggregate.created", aggregate.id)
        return aggregate

    def add_member(
        self,
        session: Session,
        *,
        aggregate: AggregatedAlert,
        alert: Alert,
        now: datetime,
    ) -> AggregatedAlert:
        """
        Fold ``alert`` into an existing aggregate and persist the change.

        Duplicate re-fires are handled by ``apply_member`` (severity/last_seen
        are refreshed but ``count`` is not incremented).
        """
        apply_member(aggregate, alert, now)
        session.add(aggregate)
        session.commit()
        session.refresh(aggregate)
        event_bus.publish("aggregate.updated", aggregate.id)
        return aggregate

    def close(
        self,
        session: Session,
        *,
        aggregate: AggregatedAlert,
        reason: str,
    ) -> AggregatedAlert:
        """Mark an aggregate CLOSED (e.g. its correlation window expired)."""
        aggregate.status = AggregatedAlertStatus.CLOSED
        aggregate.close_reason = reason
        session.add(aggregate)
        session.commit()
        session.refresh(aggregate)
        event_bus.publish("aggregate.updated", aggregate.id)
        return aggregate


aggregated_alert_service = AggregatedAlertService(AggregatedAlert)
