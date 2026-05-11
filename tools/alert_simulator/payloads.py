"""
Build randomized Grafana and Prometheus Alertmanager webhook payloads.

Shapes match AlertIQ ingest models (see backend/app/providers/grafana.py and
prometheus.py) and align with Grafana webhook notifier and Alertmanager HTTP API.
"""

from __future__ import annotations

import random
import uuid
from datetime import datetime, timezone


# Lowercase — matches normalizer _SEVERITY_MAP in AlertIQ.
SEVERITIES = ("critical", "warning", "info")

ALERT_NAMES = (
    "HighCPU",
    "DiskSpaceLow",
    "HighErrorRate",
    "LatencySpike",
    "PodCrashLooping",
    "MemoryPressure",
    "ConnectionPoolExhausted",
    "CertificateExpiringSoon",
    "ReplicationLag",
    "UnhealthyTarget",
)

REGIONS = ("us-east-1", "us-west-2", "eu-west-1", "ap-southeast-1", "ca-central-1")

APPS = ("billing-api", "auth-service", "search-indexer", "checkout", "notifications")

COMPONENTS = ("api", "worker", "cache", "db-proxy", "queue-consumer")


def _utc_rfc3339_ms() -> str:
    dt = datetime.now(timezone.utc)
    # Milliseconds, Z suffix (common in Alertmanager / Grafana samples).
    return dt.strftime("%Y-%m-%dT%H:%M:%S.") + f"{dt.microsecond // 1000:03d}Z"


def _random_instance() -> str:
    host = f"{random.randint(10, 223)}.{random.randint(0, 255)}.{random.randint(0, 255)}.{random.randint(1, 254)}"
    port = random.choice((8080, 8443, 9100, 443, 3000))
    return f"{host}:{port}"


def _random_fingerprint() -> str:
    return uuid.uuid4().hex + uuid.uuid4().hex[:8]


def build_grafana_webhook() -> dict:
    """Grafana unified alerting webhook JSON (one alert per batch)."""
    name = random.choice(ALERT_NAMES)
    severity = random.choice(SEVERITIES)
    region = random.choice(REGIONS)
    app = random.choice(APPS)
    component = random.choice(COMPONENTS)
    fp = _random_fingerprint()
    starts = _utc_rfc3339_ms()
    value = round(random.uniform(60.0, 99.9), 1)

    return {
        "status": "firing",
        "alerts": [
            {
                "status": "firing",
                "labels": {
                    "alertname": name,
                    "severity": severity,
                    "app": app,
                    "component": component,
                    "region": region,
                },
                "annotations": {
                    "summary": f"{name}: synthetic load ({severity})",
                    "description": f"Mock alert for {app}/{component} in {region}.",
                },
                "startsAt": starts,
                "endsAt": "0001-01-01T00:00:00Z",
                "fingerprint": fp,
                "values": {"A": value},
            }
        ],
        "commonLabels": {"alertname": name},
        "commonAnnotations": {},
        "externalURL": "http://grafana.example/grafana/",
        "groupLabels": {"alertname": name},
    }


def build_prometheus_webhook() -> dict:
    """Prometheus Alertmanager v4 webhook JSON (one alert per batch)."""
    name = random.choice(ALERT_NAMES)
    severity = random.choice(SEVERITIES)
    region = random.choice(REGIONS)
    app = random.choice(APPS)
    component = random.choice(COMPONENTS)
    instance = _random_instance()
    fp = _random_fingerprint()
    starts = _utc_rfc3339_ms()
    operator = random.choice(("platform", "sre", "oncall", "infra"))

    return {
        "receiver": "default",
        "status": "firing",
        "alerts": [
            {
                "status": "firing",
                "labels": {
                    "alertname": name,
                    "severity": severity,
                    "app": app,
                    "component": component,
                    "region": region,
                    "instance": instance,
                    "operator": operator,
                },
                "annotations": {
                    "summary": f"{name} on {instance} ({severity})",
                    "description": f"Mock Alertmanager alert for {app} in {region}.",
                },
                "startsAt": starts,
                "endsAt": "0001-01-01T00:00:00Z",
                "generatorURL": f"http://prometheus.example/graph?g0.expr=ALERTS%7Balertname%3D%22{name}%22%7D",
                "fingerprint": fp,
            }
        ],
        "groupLabels": {"alertname": name},
        "commonLabels": {"alertname": name, "severity": severity},
        "commonAnnotations": {},
        "externalURL": "http://alertmanager.example:9093",
        "version": "4",
        "groupKey": f'{{}}:{{alertname="{name}"}}',
        "truncatedAlerts": 0,
    }
