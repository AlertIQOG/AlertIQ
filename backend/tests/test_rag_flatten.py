"""Offline unit tests for RAG text flattening (no DB, no network)."""

import uuid

from app.models.alert import Alert, AlertSeverity, AlertStatus
from app.models.incident import Incident, IncidentPriority, IncidentStage
from app.models.note import Note
from app.services.rag.flatten import flatten_alert, flatten_incident


def _alert(**overrides) -> Alert:
    defaults = dict(
        source_id=uuid.uuid4(),
        external_id="abc",
        message="Disk usage above 90%",
        application="payments",
        component="db",
        region="eu-west-1",
        impact="Checkout latency",
        severity=AlertSeverity.CRITICAL,
        status=AlertStatus.SOLVED,
    )
    defaults.update(overrides)
    return Alert(**defaults)


def test_flatten_alert_has_header_message_and_labels():
    text = flatten_alert(_alert(), notes=[])
    assert text.startswith("[ALERT]")
    assert "Message: Disk usage above 90%" in text
    assert "Application: payments" in text
    assert "Severity: Critical" in text
    assert "Impact: Checkout latency" in text


def test_flatten_alert_includes_resolution_notes():
    notes = [
        Note(alert_id=uuid.uuid4(), author="ops", content="Cleared old WAL logs"),
        Note(alert_id=uuid.uuid4(), author="ops", content="Resized the volume"),
    ]
    text = flatten_alert(_alert(), notes=notes)
    assert "Resolution notes:" in text
    assert "- Cleared old WAL logs" in text
    assert "- Resized the volume" in text


def test_flatten_alert_omits_empty_labels():
    text = flatten_alert(_alert(application=None, impact=None), notes=[])
    assert "Application:" not in text
    assert "Impact:" not in text


def test_flatten_incident():
    incident = Incident(
        title="Payments outage",
        priority=IncidentPriority.P1,
        stage=IncidentStage.RESOLVED,
        affected_services=["checkout", "billing"],
        notes="Rolled back deploy",
    )
    text = flatten_incident(incident)
    assert text.startswith("[INCIDENT]")
    assert "Title: Payments outage" in text
    assert "Priority: P1" in text
    assert "Affected services: checkout, billing" in text
    assert "Notes: Rolled back deploy" in text
