"""
Tests for the alert status lifecycle across provider re-fires.

The provider lifecycle is firing → resolved → firing again with the same
fingerprint. ``AlertService.upsert`` must bring a still-firing alert back into
view: a ``SOLVED`` row reopens on an ``OPEN`` re-fire, and so does a member the
correlation engine dismissed into a group (marked ``_correlated_into``) — the
engine then folds it into an open group or starts a fresh one. Statuses a
person set by hand (``IN_PROGRESS``, manual ``DISMISSED``) still survive
re-fires unchanged.

Like the rest of the suite these tests write through ``Session(engine)`` —
``DATABASE_URL`` must point at a disposable database.
"""

import uuid
from datetime import datetime, timezone

import pytest
from sqlmodel import Session, delete

from app.core.database import engine
from app.models.aggregated_alert import AggregatedAlert
from app.models.alert import Alert, AlertSeverity, AlertStatus
from app.models.correlation_rule import CorrelationRule
from app.models.source import Source
from app.schemas.alert import AlertCreate
from app.services.alert import alert_service
from app.services.correlation_engine import correlation_engine
from app.services.events import event_bus


@pytest.fixture
def seeded_source(monkeypatch):
    """A throwaway Source with the event bus silenced; cleans up all rows."""
    monkeypatch.setattr(event_bus, "publish", lambda *a, **kw: None)

    source_id = uuid.uuid4()
    with Session(engine) as s:
        s.add(Source(id=source_id, name="refire-test", provider_type="grafana"))
        s.commit()

    yield source_id

    with Session(engine) as s:
        s.exec(delete(Alert).where(Alert.source_id == source_id))
        s.exec(
            delete(AggregatedAlert).where(AggregatedAlert.rule_name == "refire-rule")
        )
        s.exec(delete(CorrelationRule).where(CorrelationRule.name == "refire-rule"))
        s.exec(delete(Source).where(Source.id == source_id))
        s.commit()


def make_payload(
    source_id: uuid.UUID,
    *,
    status: AlertStatus = AlertStatus.OPEN,
    severity: AlertSeverity = AlertSeverity.WARNING,
) -> AlertCreate:
    return AlertCreate(
        source_id=source_id,
        external_id="refire-fp-1",
        message="Disk pressure",
        region="us-east-1",
        severity=severity,
        status=status,
    )


# ── upsert status rules ───────────────────────────────────────────────


def test_refire_reopens_a_provider_resolved_alert(seeded_source):
    with Session(engine) as s:
        alert, _ = alert_service.upsert(s, obj_in=make_payload(seeded_source))
        alert_service.upsert(
            s, obj_in=make_payload(seeded_source, status=AlertStatus.SOLVED)
        )
        refired, created = alert_service.upsert(s, obj_in=make_payload(seeded_source))

        assert created is False
        assert refired.id == alert.id
        assert refired.status == AlertStatus.OPEN


def test_refire_reopens_an_engine_dismissed_member(seeded_source):
    with Session(engine) as s:
        alert, _ = alert_service.upsert(s, obj_in=make_payload(seeded_source))
        # As sync_summary leaves it after folding the alert into a group.
        alert.status = AlertStatus.DISMISSED
        alert.extra_fields = {
            **(alert.extra_fields or {}),
            "_correlated_into": str(uuid.uuid4()),
        }
        s.commit()

        refired, _ = alert_service.upsert(s, obj_in=make_payload(seeded_source))

        assert refired.status == AlertStatus.OPEN
        # The marker is provider state now — gone until the engine re-dismisses.
        assert "_correlated_into" not in (refired.extra_fields or {})


def test_refire_preserves_a_user_dismissal(seeded_source):
    with Session(engine) as s:
        alert, _ = alert_service.upsert(s, obj_in=make_payload(seeded_source))
        # A person dismissed it from the feed — no correlation marker.
        alert.status = AlertStatus.DISMISSED
        s.commit()

        refired, _ = alert_service.upsert(s, obj_in=make_payload(seeded_source))

        assert refired.status == AlertStatus.DISMISSED


def test_refire_preserves_in_progress(seeded_source):
    with Session(engine) as s:
        alert, _ = alert_service.upsert(s, obj_in=make_payload(seeded_source))
        alert.status = AlertStatus.IN_PROGRESS
        s.commit()

        refired, _ = alert_service.upsert(s, obj_in=make_payload(seeded_source))

        assert refired.status == AlertStatus.IN_PROGRESS


def test_resolved_notification_still_wins(seeded_source):
    with Session(engine) as s:
        alert_service.upsert(s, obj_in=make_payload(seeded_source))
        resolved, _ = alert_service.upsert(
            s, obj_in=make_payload(seeded_source, status=AlertStatus.SOLVED)
        )

        assert resolved.status == AlertStatus.SOLVED


# ── full loop through the correlation engine ──────────────────────────


def test_refired_member_rejoins_or_reopens_its_group(seeded_source):
    """
    The audit scenario end-to-end: an alert is folded into a group (dismissed),
    re-fires while the group is open (re-folded, not recounted), then re-fires
    after the group closed — and must land in a fresh group, not vanish.
    """
    with Session(engine) as s:
        s.add(
            CorrelationRule(
                name="refire-rule",
                scope={},
                conditions=[
                    {"field": "region", "operator": "equals", "value": "us-east-1"}
                ],
                group_by=["region"],
                time_window_minutes=30,
                actions=["aggregate"],
            )
        )
        s.commit()

        now = datetime.now(timezone.utc)
        alert, _ = alert_service.upsert(s, obj_in=make_payload(seeded_source))
        first_group = correlation_engine.process_alert(s, alert, now=now)

        assert first_group is not None
        s.refresh(alert)
        assert alert.status == AlertStatus.DISMISSED
        assert alert.extra_fields["_correlated_into"] == str(first_group.id)

        # Re-fire while the group is open: reopened by upsert, re-folded and
        # re-dismissed by the engine, count unchanged.
        refired, _ = alert_service.upsert(s, obj_in=make_payload(seeded_source))
        assert refired.status == AlertStatus.OPEN
        regrouped = correlation_engine.process_alert(s, refired, now=now)
        assert regrouped is not None and regrouped.id == first_group.id
        assert regrouped.count == 1
        s.refresh(refired)
        assert refired.status == AlertStatus.DISMISSED

        # Re-fire after the group closed: must open a fresh group instead of
        # staying invisible forever.
        correlation_engine.aggregate_service.close(
            s, aggregate=regrouped, reason="window_expired"
        )
        refired_again, _ = alert_service.upsert(s, obj_in=make_payload(seeded_source))
        assert refired_again.status == AlertStatus.OPEN
        fresh_group = correlation_engine.process_alert(s, refired_again, now=now)

        assert fresh_group is not None
        assert fresh_group.id != first_group.id
        assert fresh_group.count == 1
        s.refresh(refired_again)
        assert refired_again.status == AlertStatus.DISMISSED
        assert refired_again.extra_fields["_correlated_into"] == str(fresh_group.id)
