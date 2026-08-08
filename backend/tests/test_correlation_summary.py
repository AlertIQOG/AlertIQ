"""
Unit tests for the correlation engine's **summary alert** projection.

An ``AggregatedAlert`` lives in a table the alerts feed never reads, so each
aggregate is mirrored by an ordinary ``alerts`` row flagged ``_is_aggregated``
— the same contract a hand-picked group written by ``AlertService.aggregate``
carries. These tests cover the pure projection helpers (no DB): the shape of a
freshly-built summary, how it is re-projected as members join, and that the
frontend-facing keys stay exactly those the feed reads.
"""

import uuid
from datetime import datetime, timedelta, timezone

from app.models.aggregated_alert import AggregatedAlert, AggregatedAlertStatus
from app.models.alert import Alert, AlertSeverity, AlertStatus
from app.services.correlation_engine import (
    SUMMARY_EXTERNAL_ID_PREFIX,
    apply_member,
    apply_summary_alert,
    build_summary_alert,
    summary_external_id,
    summary_message,
)

NOW = datetime(2026, 7, 3, 12, 0, 0, tzinfo=timezone.utc)
SOURCE_ID = uuid.UUID("aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee")
RULE_ID = uuid.UUID("11111111-2222-3333-4444-555555555555")


# ── builders ──────────────────────────────────────────────────────────


def make_member(
    *,
    severity: AlertSeverity = AlertSeverity.WARNING,
    application: str | None = "payments",
    component: str | None = "database",
    region: str | None = "us-east-1",
    source: str | None = "Grafana",
    alert_id: uuid.UUID | None = None,
) -> Alert:
    extra: dict = {}
    if source is not None:
        extra["source"] = source
    return Alert(
        id=alert_id or uuid.uuid4(),
        source_id=SOURCE_ID,
        external_id=str(uuid.uuid4()),
        message="High CPU",
        application=application,
        component=component,
        region=region,
        severity=severity,
        status=AlertStatus.OPEN,
        extra_fields=extra,
    )


def make_aggregate(
    *,
    member: Alert,
    rule_name: str = "DB CPU saturation",
    group_key: str = "region=us-east-1|application=payments",
    group_values: dict | None = None,
) -> AggregatedAlert:
    return AggregatedAlert(
        rule_id=RULE_ID,
        rule_name=rule_name,
        title=f"{rule_name} — {group_key}",
        group_key=group_key,
        group_values=group_values
        or {"region": "us-east-1", "application": "payments"},
        severity=member.severity,
        status=AggregatedAlertStatus.OPEN,
        count=1,
        alert_ids=[str(member.id)],
        first_seen=NOW,
        last_seen=NOW,
        window_ends_at=NOW + timedelta(minutes=30),
    )


# ── identity ──────────────────────────────────────────────────────────


def test_summary_external_id_is_derived_from_the_aggregate():
    member = make_member()
    aggregate = make_aggregate(member=member)

    external_id = summary_external_id(aggregate)

    assert external_id == f"{SUMMARY_EXTERNAL_ID_PREFIX}{aggregate.id}"
    # The aggregate UUID makes it globally unique, so it can never collide with
    # a provider fingerprint on the (source_id, external_id) constraint.
    assert str(aggregate.id) in external_id


def test_summary_message_reports_the_live_count_and_rule():
    member = make_member()
    aggregate = make_aggregate(member=member)
    aggregate.count = 4

    message = summary_message(aggregate)

    assert "4 alerts" in message
    assert "DB CPU saturation" in message
    assert "region=us-east-1|application=payments" in message


# ── build ─────────────────────────────────────────────────────────────


def test_build_summary_carries_the_frontend_contract():
    member = make_member()
    aggregate = make_aggregate(member=member)

    summary = build_summary_alert(aggregate, member)

    # These three keys are what `alertsApi.normalizeAlert` reads to render the
    # AGG badge, and what GET /alerts/{id}/children resolves.
    assert summary.extra_fields["_is_aggregated"] is True
    assert summary.extra_fields["_child_ids"] == [str(member.id)]
    assert summary.extra_fields["_child_count"] == 1


def test_build_summary_inherits_member_context():
    member = make_member(region="eu-west-1", application="checkout")
    aggregate = make_aggregate(member=member)

    summary = build_summary_alert(aggregate, member)

    assert summary.source_id == member.source_id
    assert summary.region == "eu-west-1"
    assert summary.application == "checkout"
    assert summary.component == member.component
    assert summary.status == AlertStatus.OPEN


def test_build_summary_records_correlation_provenance():
    member = make_member()
    aggregate = make_aggregate(member=member)

    provenance = build_summary_alert(aggregate, member).extra_fields["_correlation"]

    assert provenance["aggregate_id"] == str(aggregate.id)
    assert provenance["rule_id"] == str(RULE_ID)
    assert provenance["rule_name"] == "DB CPU saturation"
    assert provenance["group_key"] == aggregate.group_key
    assert provenance["group_values"] == aggregate.group_values


def test_build_summary_keeps_the_provider_tag_for_the_source_filter():
    member = make_member(source="Grafana")
    aggregate = make_aggregate(member=member)

    summary = build_summary_alert(aggregate, member)

    assert summary.extra_fields["source"] == "Grafana"


def test_build_summary_omits_absent_provider_tag():
    member = make_member(source=None)
    aggregate = make_aggregate(member=member)

    summary = build_summary_alert(aggregate, member)

    assert "source" not in summary.extra_fields


def test_build_summary_takes_severity_from_the_aggregate():
    member = make_member(severity=AlertSeverity.WARNING)
    aggregate = make_aggregate(member=member)
    # The aggregate escalates independently of the member that opened it.
    aggregate.severity = AlertSeverity.CRITICAL

    summary = build_summary_alert(aggregate, member)

    assert summary.severity == AlertSeverity.CRITICAL


# ── re-projection ─────────────────────────────────────────────────────


def test_apply_summary_tracks_new_members():
    first = make_member()
    aggregate = make_aggregate(member=first)
    summary = build_summary_alert(aggregate, first)

    second = make_member(severity=AlertSeverity.ERROR)
    apply_member(aggregate, second, NOW)
    apply_summary_alert(summary, aggregate, second)

    assert summary.extra_fields["_child_count"] == 2
    assert summary.extra_fields["_child_ids"] == [str(first.id), str(second.id)]
    assert "2 alerts" in summary.message


def test_apply_summary_escalates_severity_with_the_aggregate():
    first = make_member(severity=AlertSeverity.WARNING)
    aggregate = make_aggregate(member=first)
    summary = build_summary_alert(aggregate, first)

    critical = make_member(severity=AlertSeverity.CRITICAL)
    apply_member(aggregate, critical, NOW)
    apply_summary_alert(summary, aggregate, critical)

    assert summary.severity == AlertSeverity.CRITICAL


def test_apply_summary_reassigns_extra_fields_for_jsonb_flush():
    first = make_member()
    aggregate = make_aggregate(member=first)
    summary = build_summary_alert(aggregate, first)
    original = summary.extra_fields

    second = make_member()
    apply_member(aggregate, second, NOW)
    apply_summary_alert(summary, aggregate, second)

    # A mutated-in-place dict would not be flushed by SQLAlchemy; the helper
    # must hand back a new object.
    assert summary.extra_fields is not original
    assert original["_child_count"] == 1


def test_apply_summary_preserves_unrelated_keys():
    first = make_member()
    aggregate = make_aggregate(member=first)
    summary = build_summary_alert(aggregate, first)
    summary.extra_fields = {**summary.extra_fields, "_notes_hint": "keep me"}

    second = make_member()
    apply_member(aggregate, second, NOW)
    apply_summary_alert(summary, aggregate, second)

    assert summary.extra_fields["_notes_hint"] == "keep me"


def test_duplicate_refire_does_not_recount():
    member = make_member()
    aggregate = make_aggregate(member=member)
    summary = build_summary_alert(aggregate, member)

    # A re-fire of an existing member is reported as not-new by apply_member:
    # the aggregate refreshes severity/last_seen but never double-counts.
    assert apply_member(aggregate, member, NOW) is False
    assert aggregate.count == 1
    assert summary.extra_fields["_child_count"] == 1
