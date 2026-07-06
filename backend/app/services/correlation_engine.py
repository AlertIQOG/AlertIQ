"""
Correlation & aggregation engine.

Given a freshly-normalized :class:`~app.models.alert.Alert`, this module decides
whether the alert should stand on its own or be folded into an
:class:`~app.models.aggregated_alert.AggregatedAlert`.

The flow (see ``docs/correlation-aggregation.md`` for the diagram):

    normalized alert
        └─▶ for each ACTIVE correlation rule (in priority order):
              1. rule scope + conditions match the alert?      (rule_matches)
              2. build the group key from the rule's group_by  (compute_group)
              3. is there an OPEN, non-expired aggregate for
                 this (rule, group_key)?                        (find_open)
                   • yes → fold the alert in                   (add_member)
                   • no  → open a new aggregate                (create_from_alert)
            (first matching rule wins; if no rule matches the alert is left
             as a standalone alert.)

Design note
-----------
All *decision* logic lives in module-level **pure functions** — they take plain
model instances and return values, touching no database.  The
:class:`CorrelationEngine` only orchestrates them and delegates persistence to
:data:`app.services.aggregated_alert.aggregated_alert_service`.  This keeps the
interesting behaviour (operators, grouping, severity merge, window expiry,
de-duplication) trivially unit-testable without a live DB.
"""

import logging
from datetime import datetime, timezone
from enum import Enum
from typing import TYPE_CHECKING, Any

from app.models.alert import Alert, AlertSeverity, AlertStatus
from app.models.correlation_rule import CorrelationRule

if TYPE_CHECKING:
    from sqlmodel import Session

    from app.models.aggregated_alert import AggregatedAlert

logger = logging.getLogger("alertiq.correlation")


# ── Field resolution ──────────────────────────────────────────────────
# A rule may reference a promoted top-level column (``application``,
# ``region``, ``severity`` …) or a raw provider label nested under
# ``extra_fields`` (``service``, ``host``, ``environment`` …).  ``resolve_field``
# hides that distinction and returns a comparable scalar (or ``None`` if the
# field is absent).

_MISSING = object()


def resolve_field(alert: Alert, field: str) -> Any | None:
    """
    Look up ``field`` on an alert, searching (in order):

    1. a promoted top-level column (``alert.<field>``);
    2. ``extra_fields[field]``;
    3. ``extra_fields["labels"][field]``   (Prometheus/Grafana labels);
    4. ``extra_fields["annotations"][field]``.

    Enum values (e.g. ``severity``) are unwrapped to their string value so
    conditions can compare against plain strings.  Returns ``None`` when the
    field is absent anywhere.
    """
    if field in Alert.model_fields:
        value = getattr(alert, field, None)
        return value.value if isinstance(value, Enum) else value

    extra = alert.extra_fields or {}

    value = extra.get(field, _MISSING)
    if value is not _MISSING:
        return value

    for nested_key in ("labels", "annotations"):
        nested = extra.get(nested_key)
        if isinstance(nested, dict) and field in nested:
            return nested[field]

    return None


# ── Condition evaluation ──────────────────────────────────────────────


def _to_number(value: Any) -> float | None:
    """Best-effort numeric coercion; ``None`` when the value is not numeric."""
    if isinstance(value, bool):  # avoid True == 1.0 surprises
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def evaluate_condition(alert: Alert, condition: dict[str, Any]) -> bool:
    """
    Evaluate a single ``{field, operator, value}`` condition against an alert.

    A missing field (``None``) fails every operator except ``is_present``
    (which returns ``False``).  Unknown operators fail closed.
    """
    field = condition.get("field", "")
    operator = condition.get("operator", "")
    expected = condition.get("value")

    actual = resolve_field(alert, field)

    if operator == "is_present":
        return actual is not None

    if actual is None:
        return False

    if operator == "equals":
        return str(actual) == str(expected)
    if operator == "not_equals":
        return str(actual) != str(expected)
    if operator == "contains":
        return str(expected) in str(actual)

    if operator in {"greater_than", "less_than", "greater_or_equal", "less_or_equal"}:
        a, b = _to_number(actual), _to_number(expected)
        if a is None or b is None:
            return False
        if operator == "greater_than":
            return a > b
        if operator == "less_than":
            return a < b
        if operator == "greater_or_equal":
            return a >= b
        return a <= b  # less_or_equal

    logger.warning("Unknown correlation operator %r — condition fails closed", operator)
    return False


def _scope_matches(alert: Alert, scope: dict[str, Any]) -> bool:
    """Every ``scope`` key must equal the alert's value (empty scope = match-all)."""
    for field, expected in (scope or {}).items():
        if str(resolve_field(alert, field)) != str(expected):
            return False
    return True


def rule_matches(alert: Alert, rule: CorrelationRule) -> bool:
    """
    ``True`` when the alert falls within the rule's ``scope`` **and** satisfies
    **all** of its ``conditions`` (logical AND).
    """
    if not _scope_matches(alert, rule.scope):
        return False
    return all(evaluate_condition(alert, cond) for cond in rule.conditions)


# ── Grouping ──────────────────────────────────────────────────────────


def compute_group(
    alert: Alert, group_by: list[str]
) -> tuple[str, dict[str, Any]] | None:
    """
    Build a deterministic group key from the rule's ``group_by`` fields.

    Returns ``(group_key, group_values)`` — e.g.
    ``("service=payments|host=web-01", {"service": "payments", "host": "web-01"})``
    — or ``None`` if **any** group-by field is missing on the alert (that alert
    cannot be grouped by this rule and is skipped).
    """
    values: dict[str, Any] = {}
    for field in group_by:
        resolved = resolve_field(alert, field)
        if resolved is None:
            return None
        values[field] = resolved

    group_key = "|".join(f"{field}={values[field]}" for field in group_by)
    return group_key, values


# ── Severity merge & window expiry ────────────────────────────────────

# Highest → lowest.
_SEVERITY_RANK: dict[AlertSeverity, int] = {
    AlertSeverity.CRITICAL: 3,
    AlertSeverity.ERROR: 2,
    AlertSeverity.WARNING: 1,
    AlertSeverity.INFO: 0,
}


def merge_severity(current: AlertSeverity, incoming: AlertSeverity) -> AlertSeverity:
    """Return the more severe of two severities (the aggregate escalates, never de-escalates)."""
    return incoming if _SEVERITY_RANK[incoming] > _SEVERITY_RANK[current] else current


def is_window_expired(window_ends_at: datetime, now: datetime) -> bool:
    """``True`` once the correlation window has elapsed."""
    return now > window_ends_at


# ── Aggregate mutation (pure) ─────────────────────────────────────────


def build_aggregate(
    rule: CorrelationRule,
    alert: Alert,
    group_key: str,
    group_values: dict[str, Any],
    now: datetime,
) -> "AggregatedAlert":
    """Construct a brand-new (unpersisted) aggregate seeded with its first member."""
    from datetime import timedelta

    from app.models.aggregated_alert import AggregatedAlert, AggregatedAlertStatus

    return AggregatedAlert(
        rule_id=rule.id,
        rule_name=rule.name,
        title=f"{rule.name} — {group_key}",
        group_key=group_key,
        group_values=group_values,
        severity=alert.severity,
        status=AggregatedAlertStatus.OPEN,
        count=1,
        alert_ids=[str(alert.id)],
        first_seen=now,
        last_seen=now,
        window_ends_at=now + timedelta(minutes=rule.time_window_minutes),
    )


def apply_member(aggregate: "AggregatedAlert", alert: Alert, now: datetime) -> bool:
    """
    Fold ``alert`` into an existing aggregate, mutating it in place.

    Always refreshes ``severity`` (escalate-only) and ``last_seen``.  Returns
    ``True`` when the alert is a new member (``count`` incremented) or ``False``
    when it is a **duplicate re-fire** already tracked by the aggregate — in
    which case ``count`` is intentionally left unchanged.

    Lists are reassigned (not mutated in place) so SQLAlchemy detects the JSONB
    change and flushes it.
    """
    aggregate.severity = merge_severity(aggregate.severity, alert.severity)
    aggregate.last_seen = now

    alert_key = str(alert.id)
    if alert_key in aggregate.alert_ids:
        return False

    aggregate.alert_ids = [*aggregate.alert_ids, alert_key]
    aggregate.count += 1
    return True


# ── Orchestration ─────────────────────────────────────────────────────


class CorrelationEngine:
    """
    Wires the pure decision functions to persistence.

    Dependencies are injected so the orchestration can be unit-tested with
    in-memory fakes.  When left unset they are resolved lazily to the real
    service singletons — this keeps the engine module free of any import-time
    dependency on the service layer (which imports this module's pure helpers),
    avoiding a circular import.
    """

    def __init__(
        self, rule_service: Any | None = None, aggregate_service: Any | None = None
    ) -> None:
        self._rule_service = rule_service
        self._aggregate_service = aggregate_service

    @property
    def rule_service(self) -> Any:
        if self._rule_service is None:
            from app.services.correlation_rule import correlation_rule_service

            self._rule_service = correlation_rule_service
        return self._rule_service

    @property
    def aggregate_service(self) -> Any:
        if self._aggregate_service is None:
            from app.services.aggregated_alert import aggregated_alert_service

            self._aggregate_service = aggregated_alert_service
        return self._aggregate_service

    def process_alert(
        self,
        session: "Session",
        alert: Alert,
        *,
        now: datetime | None = None,
    ) -> "AggregatedAlert | None":
        """
        Run the alert through every active rule and aggregate it if one matches.

        Returns the :class:`AggregatedAlert` the alert landed in, or ``None``
        when no rule matched (the alert remains standalone).

        Edge cases handled:
          - **resolved/dismissed alerts** are never correlated;
          - **missing group-by fields** skip the rule (cannot be grouped);
          - **expired window** closes the stale aggregate and opens a fresh one;
          - **duplicate re-fires** refresh severity/last_seen without recounting.
        """
        now = now or datetime.now(timezone.utc)

        # Only actively-firing alerts are correlated. A provider-resolved alert
        # (or one already triaged away) must not open or grow an aggregate.
        if alert.status != AlertStatus.OPEN:
            return None

        for rule in self.rule_service.get_active(session):
            if not rule_matches(alert, rule):
                continue

            grouping = compute_group(alert, rule.group_by)
            if grouping is None:
                logger.info(
                    "Correlation skip — alert=%s missing group-by field(s) %s for rule=%s",
                    alert.id,
                    rule.group_by,
                    rule.name,
                )
                continue
            group_key, group_values = grouping

            existing = self.aggregate_service.find_open(
                session, rule_id=rule.id, group_key=group_key
            )

            # A matching aggregate whose window has elapsed is retired; the
            # current alert then starts a fresh window.
            if existing is not None and is_window_expired(existing.window_ends_at, now):
                self.aggregate_service.close(
                    session, aggregate=existing, reason="window_expired"
                )
                existing = None

            if existing is not None:
                result = self.aggregate_service.add_member(
                    session, aggregate=existing, alert=alert, now=now
                )
                logger.info(
                    "Correlation match — alert=%s folded into aggregate=%s "
                    "(rule=%s, count=%d)",
                    alert.id,
                    result.id,
                    rule.name,
                    result.count,
                )
                return result

            result = self.aggregate_service.create_from_alert(
                session,
                rule=rule,
                alert=alert,
                group_key=group_key,
                group_values=group_values,
                now=now,
            )
            logger.info(
                "Correlation match — alert=%s opened aggregate=%s (rule=%s, group=%s)",
                alert.id,
                result.id,
                rule.name,
                group_key,
            )
            return result

        return None


# Real singleton used by the ingest flow. Its service dependencies are resolved
# lazily on first use (see the properties above).
correlation_engine = CorrelationEngine()
