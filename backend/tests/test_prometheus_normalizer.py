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
