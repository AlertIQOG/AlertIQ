"""
Bridge from a correlation match to a notification.

This is the ONE call the correlation engine makes when a rule fires — it turns a
matched rule + its alerts into a rich message and dispatches it to all channels:

    from app.services.notifications import notify_correlation

    notify_correlation(rule, matched_alerts)              # slack + email
    notify_correlation(rule, matched_alerts, channels=["slack"])

The generic channel layer (service/slack/email) stays domain-agnostic; all
correlation-specific formatting lives here.
"""

from collections.abc import Iterable

from app.models.alert import Alert, AlertSeverity
from app.models.correlation_rule import CorrelationRule
from app.schemas.notification import (
    DEFAULT_CHANNELS,
    ChannelResult,
    NotificationChannelName,
    NotificationMessage,
)
from app.services.notifications.service import notification_service

# Highest-first, so we can pick the most severe alert in a group.
_SEVERITY_ORDER = [
    AlertSeverity.CRITICAL,
    AlertSeverity.ERROR,
    AlertSeverity.WARNING,
    AlertSeverity.INFO,
]
_SEVERITY_EMOJI = {
    AlertSeverity.CRITICAL: "🔴",
    AlertSeverity.ERROR: "🟠",
    AlertSeverity.WARNING: "🟡",
    AlertSeverity.INFO: "🔵",
}

_MAX_ALERTS_LISTED = 10


def _highest_severity(alerts: list[Alert]) -> AlertSeverity:
    for sev in _SEVERITY_ORDER:
        if any(a.severity == sev for a in alerts):
            return sev
    return AlertSeverity.INFO


def _distinct(values: Iterable[str | None]) -> list[str]:
    seen: list[str] = []
    for v in values:
        if v and v not in seen:
            seen.append(v)
    return seen


def build_correlation_message(
    rule: CorrelationRule, alerts: list[Alert]
) -> NotificationMessage:
    """Format a matched correlation rule + its alerts into a NotificationMessage."""
    severity = _highest_severity(alerts)
    emoji = _SEVERITY_EMOJI.get(severity, "🔔")

    services = _distinct(a.application for a in alerts)
    regions = _distinct(a.region for a in alerts)

    title = f"{emoji} Correlation triggered: {rule.name}"

    lines = [
        f'Correlation rule "{rule.name}" matched {len(alerts)} alert(s).',
        "",
        f"Severity:     {severity.value}",
        f"Services:     {', '.join(services) or 'n/a'}",
        f"Regions:      {', '.join(regions) or 'n/a'}",
        f"Time window:  {rule.time_window_minutes} min",
        f"Grouped by:   {', '.join(rule.group_by) or 'n/a'}",
    ]

    if rule.conditions:
        lines += ["", "Matched conditions:"]
        for cond in rule.conditions:
            field = cond.get("field", "?")
            operator = str(cond.get("operator", "?")).replace("_", " ")
            value = cond.get("value")
            suffix = f" {value}" if value is not None else ""
            lines.append(f"  • {field} {operator}{suffix}")

    lines += ["", "Alerts:"]
    for alert in alerts[:_MAX_ALERTS_LISTED]:
        location = "/".join(_distinct([alert.application, alert.region])) or "unknown"
        lines.append(f"  • [{alert.severity.value}] {alert.message}  ({location})")
    if len(alerts) > _MAX_ALERTS_LISTED:
        lines.append(f"  … and {len(alerts) - _MAX_ALERTS_LISTED} more")

    lines += ["", f"Rule ID: {rule.id}"]

    return NotificationMessage(title=title, body="\n".join(lines))


def notify_correlation(
    rule: CorrelationRule,
    alerts: list[Alert],
    *,
    channels: list[NotificationChannelName] | None = None,
    to: str | None = None,
) -> list[ChannelResult]:
    """Build a message from a correlation match and send it. One-call trigger."""
    message = build_correlation_message(rule, alerts)
    return notification_service.send(
        message, channels=channels or list(DEFAULT_CHANNELS), to=to
    )
