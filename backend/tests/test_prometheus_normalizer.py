"""Unit tests for the Prometheus Alertmanager normalizer."""

import uuid

import pytest

from app.models.alert import AlertSeverity, AlertStatus
from app.providers.prometheus import PrometheusNormalizer, PrometheusWebhook


@pytest.fixture
def source_id() -> uuid.UUID:
    return uuid.UUID("aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee")


@pytest.fixture
def normalizer() -> PrometheusNormalizer:
    return PrometheusNormalizer()


def test_maps_firing_alert(normalizer, source_id):
    webhook = PrometheusWebhook(
        **{
            "receiver": "default",
            "status": "firing",
            "alerts": [
                {
                    "status": "firing",
                    "labels": {
                        "alertname": "HighCPU",
                        "severity": "critical",
                        "app": "billing-api",
                        "component": "processor",
                        "region": "us-east-1",
                        "instance": "node-a",
                        "operator": "ops",
                    },
                    "annotations": {"summary": "CPU usage above 90%"},
                    "startsAt": "2026-04-28T10:00:00Z",
                    "fingerprint": "abc123",
                }
            ],
        }
    )
    result = normalizer.normalize(source_id, webhook)
    assert len(result) == 1
    alert = result[0]
    assert alert.message == "HighCPU"
    assert alert.severity == AlertSeverity.CRITICAL
    assert alert.status == AlertStatus.OPEN
    assert alert.application == "billing-api"
    assert alert.component == "processor"
    assert alert.region == "us-east-1"
    assert alert.node_name == "node-a"
    assert alert.operator == "ops"
    assert alert.extra_fields["fingerprint"] == "abc123"


def test_stamps_source_provider_name(normalizer, source_id):
    """The provider name is stamped into extra_fields so correlation rules can
    scope by ``source`` (it is not otherwise a resolvable alert field)."""
    from app.services.correlation_engine import resolve_field

    webhook = PrometheusWebhook(
        alerts=[{"status": "firing", "labels": {"alertname": "X"}, "fingerprint": "f1"}]
    )
    alert = normalizer.normalize(source_id, webhook)[0]
    assert alert.extra_fields["source"] == "Prometheus"
    assert resolve_field(alert, "source") == "Prometheus"


def test_maps_resolved_to_solved(normalizer, source_id):
    webhook = PrometheusWebhook(
        alerts=[
            {
                "status": "resolved",
                "labels": {"alertname": "MemoryLeak", "severity": "error"},
                "annotations": {},
                "fingerprint": "mem123",
            }
        ]
    )
    alert = normalizer.normalize(source_id, webhook)[0]
    assert alert.status == AlertStatus.SOLVED
    assert alert.severity == AlertSeverity.ERROR


def test_defaults_for_missing_fields(normalizer, source_id):
    webhook = PrometheusWebhook(alerts=[{"status": "firing", "labels": {}, "annotations": {}}])
    alert = normalizer.normalize(source_id, webhook)[0]
    assert alert.message == "Unnamed Prometheus Alertmanager Alert"
    assert alert.severity == AlertSeverity.WARNING


def test_external_id_uses_provider_fingerprint(normalizer, source_id):
    """When a fingerprint is present it is used directly as external_id."""
    webhook = PrometheusWebhook(
        alerts=[
            {
                "status": "firing",
                "labels": {"alertname": "HighCPU", "severity": "critical"},
                "annotations": {},
                "fingerprint": "abc123",
            }
        ]
    )
    alert = normalizer.normalize(source_id, webhook)[0]
    assert alert.external_id == "abc123"


def test_external_id_falls_back_to_hash_when_no_fingerprint(normalizer, source_id):
    """When fingerprint is absent the schema falls back to a 64-char SHA-256 hash."""
    webhook = PrometheusWebhook(
        alerts=[{"status": "firing", "labels": {"alertname": "NoFP"}, "annotations": {}, "fingerprint": ""}]
    )
    alert = normalizer.normalize(source_id, webhook)[0]
    assert len(alert.external_id) == 64


def test_same_fingerprint_same_external_id_regardless_of_severity(normalizer, source_id):
    """Re-fire with escalated severity must not change external_id (enables upsert)."""
    def _make(severity: str):
        return PrometheusWebhook(
            alerts=[
                {
                    "status": "firing",
                    "labels": {"alertname": "HighCPU", "severity": severity},
                    "annotations": {},
                    "fingerprint": "stable-fp",
                }
            ]
        )

    a = normalizer.normalize(source_id, _make("warning"))[0]
    b = normalizer.normalize(source_id, _make("critical"))[0]
    assert a.external_id == b.external_id
