"""
Persistence layer for :class:`~app.models.aggregated_alert.AggregatedAlert`.

This service is a thin wrapper around the DB: the *decision* logic (how an
aggregate is built and mutated) lives in the pure helpers
``build_aggregate`` / ``apply_member`` in
:mod:`app.services.correlation_engine`.  Here we only run queries and flush the
mutations those helpers produce.

It also maintains each aggregate's **summary alert** — an ordinary ``alerts``
row flagged ``_is_aggregated`` that mirrors the aggregate into the alerts feed,
exactly like a hand-picked group made through ``AlertService.aggregate``. The
aggregate stays the source of truth; the summary is a projection kept in step
on every new member.
"""

import logging
import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import text
from sqlmodel import Session, select

from app.models.aggregated_alert import AggregatedAlert, AggregatedAlertStatus
from app.models.alert import Alert, AlertStatus
from app.models.correlation_rule import CorrelationRule
from app.services.base import CRUDBase
from app.services.correlation_engine import (
    apply_member,
    apply_summary_alert,
    build_aggregate,
    build_summary_alert,
    summary_external_id,
)
from app.services.events import event_bus

logger = logging.getLogger("alertiq.correlation")


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
        """Open an aggregate, safely handling concurrent webhook delivery.

        Only one transaction may create an OPEN aggregate for a given
        ``(rule_id, group_key)`` pair at a time. If another request created
        the aggregate while this request was waiting, the alert is folded
        into that existing aggregate instead.
        """

        lock_key = f"aggregate:{rule.id}:{group_key}"

        session.execute(
            text(
                "SELECT pg_advisory_xact_lock("
                "hashtextextended(:lock_key, 0)"
                ")"
            ),
            {"lock_key": lock_key},
        )

        # Re-check after acquiring the lock. Another webhook may have created
        # this aggregate after the caller's initial find_open().
        existing = self.find_open(
            session,
            rule_id=rule.id,
            group_key=group_key,
        )

        if existing is not None:
            logger.info(
                "Concurrent aggregate creation avoided — "
                "rule=%s group_key=%s existing=%s",
                rule.name,
                group_key,
                existing.id,
            )

            return self.add_member(
                session,
                aggregate=existing,
                alert=alert,
                now=now,
            )

        aggregate = build_aggregate(
            rule,
            alert,
            group_key,
            group_values,
            now,
        )

        session.add(aggregate)
        session.commit()
        session.refresh(aggregate)

        self.sync_summary(
            session,
            aggregate=aggregate,
            member=alert,
        )

        event_bus.publish(
            "aggregate.created",
            aggregate.id,
        )

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
        are refreshed but ``count`` is not incremented). The summary is synced
        on every fold — a re-fire may have escalated the aggregate's severity,
        and ``upsert`` reopens re-fired members, so the sync also re-dismisses
        them behind their group.
        """
        apply_member(aggregate, alert, now)
        session.add(aggregate)
        session.commit()
        session.refresh(aggregate)
        self.sync_summary(session, aggregate=aggregate, member=alert)
        event_bus.publish("aggregate.updated", aggregate.id)
        return aggregate

    # ── Summary alert (feed projection) ───────────────────────────────

    def find_summary(
        self, session: Session, *, aggregate: AggregatedAlert
    ) -> Alert | None:
        """
        Return the aggregate's summary alert, or ``None`` if it has none.

        Looks up the recorded id first, then falls back to the deterministic
        ``external_id``. The fallback matters when a previous run recorded the
        summary but failed before committing ``summary_alert_id`` — without it
        we would insert a second summary for the same aggregate.
        """
        if aggregate.summary_alert_id is not None:
            summary = session.get(Alert, aggregate.summary_alert_id)
            if summary is not None:
                return summary

        statement = select(Alert).where(
            Alert.external_id == summary_external_id(aggregate)
        )
        return session.exec(statement).first()

    def sync_summary(
        self,
        session: Session,
        *,
        aggregate: AggregatedAlert,
        member: Alert,
    ) -> Alert | None:
        """
        Create or refresh the aggregate's summary alert and dismiss ``member``.

        Dismissing members mirrors ``AlertService.aggregate``: the group speaks
        for its members, so they stop competing for attention in the feed while
        staying reachable through ``GET /alerts/{id}/children``.

        Best-effort — a failure here must never cost us the aggregate itself,
        which is already committed by the time this runs.
        """
        try:
            summary = self.find_summary(session, aggregate=aggregate)
            created = summary is None

            if summary is None:
                summary = build_summary_alert(aggregate, member)
                session.add(summary)
            else:
                apply_summary_alert(summary, aggregate, member)
                session.add(summary)

            member.status = AlertStatus.DISMISSED
            # Stamp how the dismissal happened: AlertService.upsert uses this
            # to tell engine-dismissed members (which a re-fire may reopen)
            # apart from alerts a person dismissed (which must stay dismissed).
            # Reassigned, not mutated, so SQLAlchemy flushes the JSONB change.
            member.extra_fields = {
                **(member.extra_fields or {}),
                "_correlated_into": str(aggregate.id),
            }
            session.add(member)
            session.commit()
            session.refresh(summary)

            if aggregate.summary_alert_id != summary.id:
                aggregate.summary_alert_id = summary.id
                session.add(aggregate)
                session.commit()

            event_bus.publish(
                "alert.created" if created else "alert.updated", summary.id
            )
            event_bus.publish("alert.updated", member.id)
            return summary
        except Exception:  # noqa: BLE001 — the aggregate must survive this
            session.rollback()
            logger.exception(
                "Summary alert sync failed — aggregate=%s member=%s",
                aggregate.id,
                member.id,
            )
            return None

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
