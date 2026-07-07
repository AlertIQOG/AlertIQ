"""
Unit tests for the Grafana normalizer.

These tests are pure logic — no DB, no FastAPI, no I/O.
They verify that the GrafanaNormalizer correctly maps Grafana's webhook
payload into AlertCreate objects with the right field values.
"""

import uuid

import pytest

from app.models.alert import AlertSeverity, AlertStatus
from app.providers.grafana import GrafanaNormalizer, GrafanaWebhook


@pytest.fixture
def source_id() -> uuid.UUID:
    return uuid.UUID("aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee")


@pytest.fixture
def normalizer() -> GrafanaNormalizer:
    return GrafanaNormalizer()


@pytest.fixture
def single_firing_payload() -> dict:
    """A realistic single-alert Grafana webhook payload."""
    return {
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
                },
                "annotations": {
                    "summary": "CPU usage above 90%",
                    "description": "billing-api processor has high CPU for 5m.",
                },
                "startsAt": "2026-04-28T10:00:00Z",
                "endsAt": "0001-01-01T00:00:00Z",
                "fingerprint": "abc123def456",
                "values": {"A": 95.2},
            }
        ],
        "commonLabels": {"alertname": "HighCPU"},
        "commonAnnotations": {},
        "externalURL": "http://grafana.local",
        "groupLabels": {"alertname": "HighCPU"},
    }


@pytest.fixture
def multi_alert_payload() -> dict:
    """A batch with two alerts — one firing, one resolved."""
    return {
        "status": "firing",
        "alerts": [
            {
                "status": "firing",
                "labels": {
                    "alertname": "DiskFull",
                    "severity": "warning",
                    "job": "node-exporter",
                },
                "annotations": {"summary": "Disk almost full"},
                "fingerprint": "disk111",
                "values": {},
            },
            {
                "status": "resolved",
                "labels": {
                    "alertname": "MemoryLeak",
                    "severity": "error",
                    "app": "auth-service",
                    "component": "cache",
                    "region": "eu-west-1",
                },
                "annotations": {"summary": "Memory leak resolved"},
                "fingerprint": "mem222",
                "values": {},
            },
        ],
    }


# ── Single-alert tests ──────────────────────────────────────────────


class TestSingleAlert:
    def test_returns_one_alert(self, normalizer, source_id, single_firing_payload):
        webhook = GrafanaWebhook(**single_firing_payload)
        result = normalizer.normalize(source_id, webhook)
        assert len(result) == 1

    def test_message_from_alertname(self, normalizer, source_id, single_firing_payload):
        webhook = GrafanaWebhook(**single_firing_payload)
        alert = normalizer.normalize(source_id, webhook)[0]
        assert alert.message == "HighCPU"

    def test_severity_mapping(self, normalizer, source_id, single_firing_payload):
        webhook = GrafanaWebhook(**single_firing_payload)
        alert = normalizer.normalize(source_id, webhook)[0]
        assert alert.severity == AlertSeverity.CRITICAL

    def test_status_firing(self, normalizer, source_id, single_firing_payload):
        webhook = GrafanaWebhook(**single_firing_payload)
        alert = normalizer.normalize(source_id, webhook)[0]
        assert alert.status == AlertStatus.OPEN

    def test_application_from_app_label(self, normalizer, source_id, single_firing_payload):
        webhook = GrafanaWebhook(**single_firing_payload)
        alert = normalizer.normalize(source_id, webhook)[0]
        assert alert.application == "billing-api"

    def test_component_mapped(self, normalizer, source_id, single_firing_payload):
        webhook = GrafanaWebhook(**single_firing_payload)
        alert = normalizer.normalize(source_id, webhook)[0]
        assert alert.component == "processor"

    def test_region_mapped(self, normalizer, source_id, single_firing_payload):
        webhook = GrafanaWebhook(**single_firing_payload)
        alert = normalizer.normalize(source_id, webhook)[0]
        assert alert.region == "us-east-1"

    def test_source_id_set(self, normalizer, source_id, single_firing_payload):
        webhook = GrafanaWebhook(**single_firing_payload)
        alert = normalizer.normalize(source_id, webhook)[0]
        assert alert.source_id == source_id

    def test_extra_fields_contains_fingerprint(self, normalizer, source_id, single_firing_payload):
        webhook = GrafanaWebhook(**single_firing_payload)
        alert = normalizer.normalize(source_id, webhook)[0]
        assert alert.extra_fields["fingerprint"] == "abc123def456"

    def test_extra_fields_contains_labels(self, normalizer, source_id, single_firing_payload):
        webhook = GrafanaWebhook(**single_firing_payload)
        alert = normalizer.normalize(source_id, webhook)[0]
        assert "alertname" in alert.extra_fields["labels"]

    def test_stamps_source_provider_name(self, normalizer, source_id, single_firing_payload):
        """Provider name is stamped so correlation rules can scope by ``source``."""
        webhook = GrafanaWebhook(**single_firing_payload)
        alert = normalizer.normalize(source_id, webhook)[0]
        assert alert.extra_fields["source"] == "Grafana"

    def test_extra_fields_contains_annotations(self, normalizer, source_id, single_firing_payload):
        webhook = GrafanaWebhook(**single_firing_payload)
        alert = normalizer.normalize(source_id, webhook)[0]
        assert alert.extra_fields["annotations"]["summary"] == "CPU usage above 90%"

    def test_external_id_uses_provider_fingerprint(self, normalizer, source_id, single_firing_payload):
        """When a fingerprint is present it is used directly as external_id."""
        webhook = GrafanaWebhook(**single_firing_payload)
        alert = normalizer.normalize(source_id, webhook)[0]
        assert alert.external_id == "abc123def456"

    def test_external_id_falls_back_to_hash_when_no_fingerprint(self, normalizer, source_id):
        """When fingerprint is absent the schema falls back to a 64-char SHA-256 hash."""
        webhook = GrafanaWebhook(
            alerts=[
                {
                    "status": "firing",
                    "labels": {"alertname": "NoFP", "severity": "info"},
                    "annotations": {},
                    "fingerprint": "",
                    "values": {},
                }
            ]
        )
        alert = normalizer.normalize(source_id, webhook)[0]
        assert len(alert.external_id) == 64


# ── Multi-alert / batch tests ───────────────────────────────────────


class TestMultiAlert:
    def test_returns_two_alerts(self, normalizer, source_id, multi_alert_payload):
        webhook = GrafanaWebhook(**multi_alert_payload)
        result = normalizer.normalize(source_id, webhook)
        assert len(result) == 2

    def test_resolved_maps_to_solved(self, normalizer, source_id, multi_alert_payload):
        webhook = GrafanaWebhook(**multi_alert_payload)
        resolved = normalizer.normalize(source_id, webhook)[1]
        assert resolved.status == AlertStatus.SOLVED

    def test_job_label_used_as_application(self, normalizer, source_id, multi_alert_payload):
        webhook = GrafanaWebhook(**multi_alert_payload)
        first = normalizer.normalize(source_id, webhook)[0]
        assert first.application == "node-exporter"


# ── Edge-case tests ─────────────────────────────────────────────────


class TestEdgeCases:
    def test_empty_alerts_list(self, normalizer, source_id):
        webhook = GrafanaWebhook(status="firing", alerts=[])
        result = normalizer.normalize(source_id, webhook)
        assert result == []

    def test_missing_severity_defaults_to_warning(self, normalizer, source_id):
        webhook = GrafanaWebhook(
            alerts=[
                {
                    "status": "firing",
                    "labels": {"alertname": "NoSeverity"},
                    "annotations": {},
                    "fingerprint": "nosev",
                    "values": {},
                }
            ]
        )
        alert = normalizer.normalize(source_id, webhook)[0]
        assert alert.severity == AlertSeverity.WARNING

    def test_missing_alertname_defaults(self, normalizer, source_id):
        webhook = GrafanaWebhook(
            alerts=[
                {
                    "status": "firing",
                    "labels": {"severity": "info"},
                    "annotations": {},
                    "fingerprint": "noname",
                    "values": {},
                }
            ]
        )
        alert = normalizer.normalize(source_id, webhook)[0]
        assert alert.message == "Unnamed Grafana Alert"

    def test_deterministic_external_id(self, normalizer, source_id, single_firing_payload):
        """Same payload → same external_id (dedup relies on this)."""
        webhook = GrafanaWebhook(**single_firing_payload)
        a = normalizer.normalize(source_id, webhook)[0]
        b = normalizer.normalize(source_id, webhook)[0]
        assert a.external_id == b.external_id

    def test_different_fingerprints_produce_different_ids(self, normalizer, source_id):
        """Different fingerprints → different external_ids."""
        def _make(fp: str):
            return GrafanaWebhook(
                alerts=[
                    {
                        "status": "firing",
                        "labels": {"alertname": "X", "severity": "info"},
                        "annotations": {},
                        "fingerprint": fp,
                        "values": {},
                    }
                ]
            )

        a = normalizer.normalize(source_id, _make("fp1"))[0]
        b = normalizer.normalize(source_id, _make("fp2"))[0]
        assert a.external_id != b.external_id

    def test_same_fingerprint_same_external_id_regardless_of_severity(self, normalizer, source_id):
        """Re-fire with escalated severity must not change external_id (enables upsert)."""
        def _make(severity: str):
            return GrafanaWebhook(
                alerts=[
                    {
                        "status": "firing",
                        "labels": {"alertname": "HighCPU", "severity": severity},
                        "annotations": {},
                        "fingerprint": "stable-fp",
                        "values": {},
                    }
                ]
            )

        a = normalizer.normalize(source_id, _make("warning"))[0]
        b = normalizer.normalize(source_id, _make("critical"))[0]
        assert a.external_id == b.external_id
