"""
Unit tests for the correlation & aggregation engine.

Two layers are covered:

  * the pure decision helpers (field resolution, operators, grouping, severity
    merge, window expiry, aggregate mutation) — tested directly, no DB;
  * the ``CorrelationEngine.process_alert`` orchestration — tested with
    in-memory fakes that reuse the real pure helpers, so branching (create /
    grow / duplicate / expired-window / missing-field / no-match) is verified
    without a live database.
"""

import uuid
from datetime import datetime, timedelta, timezone

import pytest

from app.models.aggregated_alert import AggregatedAlert, AggregatedAlertStatus
from app.models.alert import Alert, AlertSeverity, AlertStatus
from app.models.correlation_rule import CorrelationRule
from app.services.correlation_engine import (
    CorrelationEngine,
    apply_member,
    build_aggregate,
    compute_group,
    evaluate_condition,
    is_window_expired,
    merge_severity,
    resolve_field,
    rule_matches,
)

NOW = datetime(2026, 7, 3, 12, 0, 0, tzinfo=timezone.utc)
SOURCE_ID = uuid.UUID("aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee")


# ── builders ──────────────────────────────────────────────────────────


def make_alert(
    *,
    severity: AlertSeverity = AlertSeverity.WARNING,
    status: AlertStatus = AlertStatus.OPEN,
    message: str = "HighCPU",
    application: str | None = None,
    region: str | None = None,
    labels: dict | None = None,
    annotations: dict | None = None,
    extra: dict | None = None,
    alert_id: uuid.UUID | None = None,
) -> Alert:
    extra_fields: dict = dict(extra or {})
    if labels is not None:
        extra_fields["labels"] = labels
    if annotations is not None:
        extra_fields["annotations"] = annotations
    return Alert(
        id=alert_id or uuid.uuid4(),
        source_id=SOURCE_ID,
        external_id=str(uuid.uuid4()),
        message=message,
        application=application,
        region=region,
        severity=severity,
        status=status,
        extra_fields=extra_fields,
    )


def make_rule(
    *,
    name: str = "rule",
    scope: dict | None = None,
    conditions: list[dict] | None = None,
    group_by: list[str] | None = None,
    time_window_minutes: int = 5,
    actions: list[str] | None = None,
    email_recipients: list[str] | None = None,
) -> CorrelationRule:
    return CorrelationRule(
        name=name,
        scope=scope or {},
        conditions=conditions or [{"field": "severity", "operator": "is_present"}],
        group_by=group_by or ["service"],
        time_window_minutes=time_window_minutes,
        actions=actions if actions is not None else ["aggregate"],
        email_recipients=email_recipients or [],
    )


# ── resolve_field ─────────────────────────────────────────────────────


def test_resolve_top_level_column():
    alert = make_alert(application="billing")
    assert resolve_field(alert, "application") == "billing"


def test_resolve_unwraps_enum_severity():
    alert = make_alert(severity=AlertSeverity.CRITICAL)
    assert resolve_field(alert, "severity") == "Critical"


def test_resolve_nested_label():
    alert = make_alert(labels={"service": "payments", "host": "web-01"})
    assert resolve_field(alert, "service") == "payments"
    assert resolve_field(alert, "host") == "web-01"


def test_resolve_nested_annotation():
    alert = make_alert(annotations={"runbook": "wiki/cpu"})
    assert resolve_field(alert, "runbook") == "wiki/cpu"


def test_resolve_top_level_extra_field():
    alert = make_alert(extra={"team": "sre"})
    assert resolve_field(alert, "team") == "sre"


def test_resolve_missing_returns_none():
    assert resolve_field(make_alert(), "nope") is None


# ── evaluate_condition ────────────────────────────────────────────────


def test_condition_equals_and_not_equals():
    alert = make_alert(labels={"env": "prod"})
    assert evaluate_condition(alert, {"field": "env", "operator": "equals", "value": "prod"})
    assert not evaluate_condition(alert, {"field": "env", "operator": "equals", "value": "dev"})
    assert evaluate_condition(alert, {"field": "env", "operator": "not_equals", "value": "dev"})


def test_condition_contains():
    alert = make_alert(message="disk space low on /var")
    assert evaluate_condition(alert, {"field": "message", "operator": "contains", "value": "disk space"})
    assert not evaluate_condition(alert, {"field": "message", "operator": "contains", "value": "cpu"})


def test_condition_numeric_operators():
    alert = make_alert(labels={"cpu": "95"})
    assert evaluate_condition(alert, {"field": "cpu", "operator": "greater_than", "value": 90})
    assert evaluate_condition(alert, {"field": "cpu", "operator": "greater_or_equal", "value": 95})
    assert not evaluate_condition(alert, {"field": "cpu", "operator": "less_than", "value": 90})
    assert evaluate_condition(alert, {"field": "cpu", "operator": "less_or_equal", "value": 95})


def test_condition_numeric_on_nonnumeric_fails():
    alert = make_alert(labels={"cpu": "high"})
    assert not evaluate_condition(alert, {"field": "cpu", "operator": "greater_than", "value": 90})


def test_condition_is_present():
    alert = make_alert(labels={"service": "api"})
    assert evaluate_condition(alert, {"field": "service", "operator": "is_present"})
    assert not evaluate_condition(alert, {"field": "missing", "operator": "is_present"})


def test_condition_missing_field_fails_non_presence_ops():
    alert = make_alert()
    assert not evaluate_condition(alert, {"field": "x", "operator": "equals", "value": "y"})


def test_condition_unknown_operator_fails_closed():
    alert = make_alert(labels={"a": "b"})
    assert not evaluate_condition(alert, {"field": "a", "operator": "regex", "value": "b"})


# ── rule_matches (scope + AND conditions) ─────────────────────────────


def test_rule_matches_all_conditions_and():
    alert = make_alert(labels={"service": "api", "env": "prod"})
    rule = make_rule(
        conditions=[
            {"field": "service", "operator": "equals", "value": "api"},
            {"field": "env", "operator": "equals", "value": "prod"},
        ]
    )
    assert rule_matches(alert, rule)


def test_rule_fails_if_one_condition_fails():
    alert = make_alert(labels={"service": "api", "env": "dev"})
    rule = make_rule(
        conditions=[
            {"field": "service", "operator": "equals", "value": "api"},
            {"field": "env", "operator": "equals", "value": "prod"},
        ]
    )
    assert not rule_matches(alert, rule)


def test_rule_scope_prefilter():
    rule = make_rule(
        scope={"application": "billing"},
        conditions=[{"field": "service", "operator": "is_present"}],
    )
    match = make_alert(application="billing", labels={"service": "api"})
    miss = make_alert(application="shipping", labels={"service": "api"})
    assert rule_matches(match, rule)
    assert not rule_matches(miss, rule)


# ── compute_group ─────────────────────────────────────────────────────


def test_compute_group_happy_path():
    alert = make_alert(labels={"service": "payments", "host": "web-01"})
    result = compute_group(alert, ["service", "host"])
    assert result is not None
    key, values = result
    assert key == "service=payments|host=web-01"
    assert values == {"service": "payments", "host": "web-01"}


def test_compute_group_missing_field_returns_none():
    alert = make_alert(labels={"service": "payments"})  # no host
    assert compute_group(alert, ["service", "host"]) is None


def test_compute_group_order_is_deterministic():
    alert = make_alert(labels={"service": "payments", "host": "web-01"})
    assert compute_group(alert, ["service", "host"])[0] == "service=payments|host=web-01"
    assert compute_group(alert, ["host", "service"])[0] == "host=web-01|service=payments"


# ── merge_severity / window expiry ────────────────────────────────────


def test_merge_severity_escalates_only():
    assert merge_severity(AlertSeverity.WARNING, AlertSeverity.CRITICAL) == AlertSeverity.CRITICAL
    assert merge_severity(AlertSeverity.CRITICAL, AlertSeverity.INFO) == AlertSeverity.CRITICAL
    assert merge_severity(AlertSeverity.INFO, AlertSeverity.INFO) == AlertSeverity.INFO


def test_window_expiry():
    ends = NOW + timedelta(minutes=5)
    assert not is_window_expired(ends, NOW)
    assert not is_window_expired(ends, NOW + timedelta(minutes=5))
    assert is_window_expired(ends, NOW + timedelta(minutes=5, seconds=1))


# ── build_aggregate / apply_member ────────────────────────────────────


def test_build_aggregate_seeds_first_member():
    rule = make_rule(time_window_minutes=10)
    alert = make_alert(severity=AlertSeverity.ERROR)
    agg = build_aggregate(rule, alert, "service=api", {"service": "api"}, NOW)
    assert agg.count == 1
    assert agg.alert_ids == [str(alert.id)]
    assert agg.severity == AlertSeverity.ERROR
    assert agg.status == AggregatedAlertStatus.OPEN
    assert agg.first_seen == NOW
    assert agg.window_ends_at == NOW + timedelta(minutes=10)


def test_apply_member_adds_new_alert():
    rule = make_rule()
    first = make_alert(severity=AlertSeverity.WARNING)
    agg = build_aggregate(rule, first, "service=api", {"service": "api"}, NOW)

    second = make_alert(severity=AlertSeverity.CRITICAL)
    later = NOW + timedelta(minutes=1)
    added = apply_member(agg, second, later)

    assert added is True
    assert agg.count == 2
    assert agg.severity == AlertSeverity.CRITICAL  # escalated
    assert agg.last_seen == later
    assert str(second.id) in agg.alert_ids


def test_apply_member_duplicate_does_not_recount():
    rule = make_rule()
    alert = make_alert(severity=AlertSeverity.WARNING)
    agg = build_aggregate(rule, alert, "service=api", {"service": "api"}, NOW)

    # Same alert id re-fires with escalated severity.
    refire = make_alert(severity=AlertSeverity.CRITICAL, alert_id=alert.id)
    later = NOW + timedelta(minutes=2)
    added = apply_member(agg, refire, later)

    assert added is False
    assert agg.count == 1  # not double counted
    assert agg.severity == AlertSeverity.CRITICAL  # still refreshed
    assert agg.last_seen == later


# ── orchestration fakes ───────────────────────────────────────────────


class FakeRuleService:
    def __init__(self, rules: list[CorrelationRule]):
        self.rules = rules

    def get_active(self, session):
        return self.rules


class FakeAggregateService:
    """In-memory stand-in that reuses the real pure helpers."""

    def __init__(self):
        self.store: list[AggregatedAlert] = []
        self.closed: list[AggregatedAlert] = []

    def find_open(self, session, *, rule_id, group_key):
        for agg in self.store:
            if (
                agg.rule_id == rule_id
                and agg.group_key == group_key
                and agg.status == AggregatedAlertStatus.OPEN
            ):
                return agg
        return None

    def create_from_alert(self, session, *, rule, alert, group_key, group_values, now):
        agg = build_aggregate(rule, alert, group_key, group_values, now)
        self.store.append(agg)
        return agg

    def add_member(self, session, *, aggregate, alert, now):
        apply_member(aggregate, alert, now)
        return aggregate

    def close(self, session, *, aggregate, reason):
        aggregate.status = AggregatedAlertStatus.CLOSED
        aggregate.close_reason = reason
        self.closed.append(aggregate)
        return aggregate


@pytest.fixture
def aggregates() -> FakeAggregateService:
    return FakeAggregateService()


class FakeNotifier:
    """Captures every (rule, alerts, channels) dispatch the engine performs."""

    def __init__(self):
        self.calls: list[dict] = []

    def __call__(self, rule, alerts, *, channels=None, to=None):
        self.calls.append(
            {"rule": rule, "alerts": alerts, "channels": channels, "to": to}
        )
        return []


@pytest.fixture
def notifier() -> FakeNotifier:
    return FakeNotifier()


def build_engine(
    rules: list[CorrelationRule],
    aggregates: FakeAggregateService,
    notifier: "FakeNotifier | None" = None,
) -> CorrelationEngine:
    return CorrelationEngine(
        rule_service=FakeRuleService(rules),
        aggregate_service=aggregates,
        notifier=notifier,
    )


# ── orchestration behaviour ───────────────────────────────────────────


def test_process_no_rules_leaves_standalone(aggregates):
    engine = build_engine([], aggregates)
    assert engine.process_alert(None, make_alert(), now=NOW) is None
    assert aggregates.store == []


def test_process_no_match_leaves_standalone(aggregates):
    rule = make_rule(conditions=[{"field": "env", "operator": "equals", "value": "prod"}])
    engine = build_engine([rule], aggregates)
    alert = make_alert(labels={"env": "dev", "service": "api"})
    assert engine.process_alert(None, alert, now=NOW) is None


def test_process_creates_new_aggregate(aggregates):
    rule = make_rule(group_by=["service"])
    engine = build_engine([rule], aggregates)
    alert = make_alert(labels={"service": "payments"}, severity=AlertSeverity.ERROR)

    agg = engine.process_alert(None, alert, now=NOW)

    assert agg is not None
    assert agg.count == 1
    assert agg.group_key == "service=payments"
    assert len(aggregates.store) == 1


def test_process_grows_existing_aggregate(aggregates):
    rule = make_rule(group_by=["service"], time_window_minutes=10)
    engine = build_engine([rule], aggregates)

    a1 = make_alert(labels={"service": "payments"}, severity=AlertSeverity.WARNING)
    a2 = make_alert(labels={"service": "payments"}, severity=AlertSeverity.CRITICAL)

    engine.process_alert(None, a1, now=NOW)
    agg = engine.process_alert(None, a2, now=NOW + timedelta(minutes=1))

    assert len(aggregates.store) == 1  # same aggregate
    assert agg.count == 2
    assert agg.severity == AlertSeverity.CRITICAL


def test_process_duplicate_refire_does_not_recount(aggregates):
    rule = make_rule(group_by=["service"], time_window_minutes=10)
    engine = build_engine([rule], aggregates)

    alert = make_alert(labels={"service": "payments"})
    engine.process_alert(None, alert, now=NOW)
    # Same alert id comes back (upsert re-fire).
    agg = engine.process_alert(None, alert, now=NOW + timedelta(minutes=1))

    assert agg.count == 1
    assert len(aggregates.store) == 1


def test_process_expired_window_opens_fresh_aggregate(aggregates):
    rule = make_rule(group_by=["service"], time_window_minutes=5)
    engine = build_engine([rule], aggregates)

    a1 = make_alert(labels={"service": "payments"})
    a2 = make_alert(labels={"service": "payments"})

    engine.process_alert(None, a1, now=NOW)
    # 6 minutes later — the first window has expired.
    agg2 = engine.process_alert(None, a2, now=NOW + timedelta(minutes=6))

    assert len(aggregates.store) == 2  # a new aggregate was opened
    assert len(aggregates.closed) == 1  # the stale one was closed
    assert aggregates.closed[0].close_reason == "window_expired"
    assert agg2.count == 1


def test_process_missing_group_field_is_skipped(aggregates):
    rule = make_rule(group_by=["service", "host"])
    engine = build_engine([rule], aggregates)
    alert = make_alert(labels={"service": "payments"})  # no host

    assert engine.process_alert(None, alert, now=NOW) is None
    assert aggregates.store == []


def test_process_skips_resolved_alerts(aggregates):
    rule = make_rule(group_by=["service"])
    engine = build_engine([rule], aggregates)
    alert = make_alert(labels={"service": "payments"}, status=AlertStatus.SOLVED)

    assert engine.process_alert(None, alert, now=NOW) is None
    assert aggregates.store == []


def test_process_first_matching_rule_wins(aggregates):
    rule_a = make_rule(name="A", group_by=["service"])
    rule_b = make_rule(name="B", group_by=["service"])
    engine = build_engine([rule_a, rule_b], aggregates)

    alert = make_alert(labels={"service": "payments"})
    agg = engine.process_alert(None, alert, now=NOW)

    assert agg.rule_name == "A"
    assert len(aggregates.store) == 1


# ── action-driven behaviour ───────────────────────────────────────────


def test_aggregate_action_does_not_send_email(aggregates, notifier):
    rule = make_rule(group_by=["service"], actions=["aggregate"])
    engine = build_engine([rule], aggregates, notifier)

    engine.process_alert(None, make_alert(labels={"service": "payments"}), now=NOW)

    assert len(aggregates.store) == 1
    assert notifier.calls == []  # no email action → no notification


def test_email_action_dispatches_email_notification(aggregates, notifier):
    rule = make_rule(
        group_by=["service"],
        actions=["aggregate", "email"],
        email_recipients=["ops@acme.com", "oncall@acme.com"],
    )
    engine = build_engine([rule], aggregates, notifier)

    alert = make_alert(labels={"service": "payments"})
    engine.process_alert(None, alert, now=NOW)

    assert len(aggregates.store) == 1  # still aggregates
    assert len(notifier.calls) == 1
    call = notifier.calls[0]
    assert call["rule"] is rule
    assert call["alerts"] == [alert]
    assert call["channels"] == ["email"]
    # The rule's recipients are passed through as a comma-separated To.
    assert call["to"] == "ops@acme.com,oncall@acme.com"


def test_email_dispatch_falls_back_to_global_when_no_recipients(aggregates, notifier):
    """No per-rule recipients → to=None, so the channel uses EMAIL_DEFAULT_TO."""
    rule = make_rule(group_by=["service"], actions=["aggregate", "email"])
    engine = build_engine([rule], aggregates, notifier)

    engine.process_alert(None, make_alert(labels={"service": "payments"}), now=NOW)

    assert notifier.calls[0]["to"] is None


def test_email_only_action_sends_email_without_aggregating(aggregates, notifier):
    rule = make_rule(group_by=["service"], actions=["email"])
    engine = build_engine([rule], aggregates, notifier)

    result = engine.process_alert(None, make_alert(labels={"service": "payments"}), now=NOW)

    assert result is None  # email-only rule does not open an aggregate
    assert aggregates.store == []
    assert len(notifier.calls) == 1
    assert notifier.calls[0]["channels"] == ["email"]


def test_email_not_sent_when_rule_does_not_match(aggregates, notifier):
    rule = make_rule(
        conditions=[{"field": "env", "operator": "equals", "value": "prod"}],
        actions=["email"],
    )
    engine = build_engine([rule], aggregates, notifier)

    alert = make_alert(labels={"env": "dev", "service": "api"})
    engine.process_alert(None, alert, now=NOW)

    assert notifier.calls == []


def test_email_action_failure_does_not_break_correlation(aggregates):
    def boom(rule, alerts, *, channels=None, to=None):
        raise RuntimeError("smtp down")

    rule = make_rule(group_by=["service"], actions=["aggregate", "email"])
    engine = build_engine([rule], aggregates, boom)

    # The aggregate must still be created even though the email raised.
    agg = engine.process_alert(None, make_alert(labels={"service": "payments"}), now=NOW)

    assert agg is not None
    assert len(aggregates.store) == 1
