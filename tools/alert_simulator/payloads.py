"""
Build randomized Grafana and Prometheus Alertmanager webhook payloads.

Shapes match AlertIQ ingest models (see backend/app/providers/grafana.py and
prometheus.py) and align with Grafana webhook notifier and Alertmanager HTTP API.
"""

from __future__ import annotations

import random
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone


# Lowercase — matches normalizer _SEVERITY_MAP in AlertIQ (grafana.py / prometheus.py).
SEVERITIES = ("critical", "error", "warning", "info")

# Roughly production-shaped skew: most noise is low severity, critical is rare.
# Order matches SEVERITIES.
SEVERITY_WEIGHTS = (5, 15, 35, 45)

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

# Mostly prod, occasionally staging — matches real hostnames seen on the
# deployed server ("prod-auth-db-1" style), not bare IP:port.
_NODE_ENVS = ("prod", "prod", "prod", "stg")

# Coherent "one incident, several symptoms" sets for build_incident_burst,
# rather than bursting unrelated alert names together.
INCIDENT_SYMPTOM_SETS: tuple[tuple[str, ...], ...] = (
    ("HighCPU", "LatencySpike", "ConnectionPoolExhausted"),
    ("DiskSpaceLow", "ReplicationLag", "MemoryPressure"),
    ("PodCrashLooping", "UnhealthyTarget", "HighErrorRate"),
    ("MemoryPressure", "HighErrorRate", "LatencySpike"),
)


def random_severity() -> str:
    return random.choices(SEVERITIES, weights=SEVERITY_WEIGHTS, k=1)[0]


def _utc_rfc3339_ms(dt: datetime | None = None) -> str:
    dt = dt or datetime.now(timezone.utc)
    return dt.strftime("%Y-%m-%dT%H:%M:%S.") + f"{dt.microsecond // 1000:03d}Z"


def _random_node_name(app: str, component: str) -> str:
    env = random.choice(_NODE_ENVS)
    n = random.randint(1, 12)
    return f"{env}-{app}-{component}-{n}"


def _random_fingerprint() -> str:
    return uuid.uuid4().hex + uuid.uuid4().hex[:8]


@dataclass(frozen=True)
class AlertSpec:
    """One alert's values — random by default, or fixed for a shared-label burst."""

    name: str = field(default_factory=lambda: random.choice(ALERT_NAMES))
    severity: str = field(default_factory=random_severity)
    region: str = field(default_factory=lambda: random.choice(REGIONS))
    app: str = field(default_factory=lambda: random.choice(APPS))
    component: str = field(default_factory=lambda: random.choice(COMPONENTS))
    fingerprint: str = field(default_factory=_random_fingerprint)


@dataclass(frozen=True)
class FiredAlert:
    """What's needed to later send a matching resolution webhook."""

    provider: str  # "grafana" | "prometheus"
    spec: AlertSpec
    starts_at: str
    instance: str | None = None
    operator: str | None = None


def build_grafana_webhook(spec: AlertSpec | None = None) -> tuple[dict, FiredAlert]:
    """Grafana unified alerting webhook JSON (one alert per batch)."""
    spec = spec or AlertSpec()
    starts = _utc_rfc3339_ms()
    value = round(random.uniform(60.0, 99.9), 1)
    instance = _random_node_name(spec.app, spec.component)
    operator = random.choice(("platform", "sre", "oncall", "infra"))

    body = {
        "status": "firing",
        "alerts": [
            {
                "status": "firing",
                "labels": {
                    "alertname": spec.name,
                    "severity": spec.severity,
                    "app": spec.app,
                    "component": spec.component,
                    "region": spec.region,
                    "instance": instance,
                    "operator": operator,
                },
                "annotations": {
                    "summary": f"{spec.name}: synthetic load ({spec.severity})",
                    "description": f"Mock alert for {spec.app}/{spec.component} in {spec.region}.",
                },
                "startsAt": starts,
                "endsAt": "0001-01-01T00:00:00Z",
                "fingerprint": spec.fingerprint,
                "values": {"A": value},
            }
        ],
        "commonLabels": {"alertname": spec.name},
        "commonAnnotations": {},
        "externalURL": "http://grafana.example/grafana/",
        "groupLabels": {"alertname": spec.name},
    }
    return body, FiredAlert(
        provider="grafana", spec=spec, starts_at=starts, instance=instance, operator=operator
    )


def build_prometheus_webhook(spec: AlertSpec | None = None) -> tuple[dict, FiredAlert]:
    """Prometheus Alertmanager v4 webhook JSON (one alert per batch)."""
    spec = spec or AlertSpec()
    instance = _random_node_name(spec.app, spec.component)
    starts = _utc_rfc3339_ms()
    operator = random.choice(("platform", "sre", "oncall", "infra"))

    body = {
        "receiver": "default",
        "status": "firing",
        "alerts": [
            {
                "status": "firing",
                "labels": {
                    "alertname": spec.name,
                    "severity": spec.severity,
                    "app": spec.app,
                    "component": spec.component,
                    "region": spec.region,
                    "instance": instance,
                    "operator": operator,
                },
                "annotations": {
                    "summary": f"{spec.name} on {instance} ({spec.severity})",
                    "description": f"Mock Alertmanager alert for {spec.app} in {spec.region}.",
                },
                "startsAt": starts,
                "endsAt": "0001-01-01T00:00:00Z",
                "generatorURL": f"http://prometheus.example/graph?g0.expr=ALERTS%7Balertname%3D%22{spec.name}%22%7D",
                "fingerprint": spec.fingerprint,
            }
        ],
        "groupLabels": {"alertname": spec.name},
        "commonLabels": {"alertname": spec.name, "severity": spec.severity},
        "commonAnnotations": {},
        "externalURL": "http://alertmanager.example:9093",
        "version": "4",
        "groupKey": f'{{}}:{{alertname="{spec.name}"}}',
        "truncatedAlerts": 0,
    }
    return body, FiredAlert(
        provider="prometheus", spec=spec, starts_at=starts, instance=instance, operator=operator
    )


def build_resolution_webhook(fired: FiredAlert) -> dict:
    """A "resolved" follow-up for a previously-fired alert — updates the same
    row (Open -> Solved), doesn't create a new one."""
    spec = fired.spec
    ends = _utc_rfc3339_ms()

    if fired.provider == "grafana":
        return {
            "status": "resolved",
            "alerts": [
                {
                    "status": "resolved",
                    "labels": {
                        "alertname": spec.name,
                        "severity": spec.severity,
                        "app": spec.app,
                        "component": spec.component,
                        "region": spec.region,
                        "instance": fired.instance or _random_node_name(spec.app, spec.component),
                        "operator": fired.operator or "platform",
                    },
                    "annotations": {
                        "summary": f"{spec.name}: resolved",
                        "description": f"{spec.app}/{spec.component} in {spec.region} recovered.",
                    },
                    "startsAt": fired.starts_at,
                    "endsAt": ends,
                    "fingerprint": spec.fingerprint,
                    "values": {},
                }
            ],
            "commonLabels": {"alertname": spec.name},
            "commonAnnotations": {},
            "externalURL": "http://grafana.example/grafana/",
            "groupLabels": {"alertname": spec.name},
        }

    return {
        "receiver": "default",
        "status": "resolved",
        "alerts": [
            {
                "status": "resolved",
                "labels": {
                    "alertname": spec.name,
                    "severity": spec.severity,
                    "app": spec.app,
                    "component": spec.component,
                    "region": spec.region,
                    "instance": fired.instance or _random_node_name(spec.app, spec.component),
                    "operator": fired.operator or "platform",
                },
                "annotations": {
                    "summary": f"{spec.name} resolved",
                    "description": f"Mock Alertmanager resolution for {spec.app} in {spec.region}.",
                },
                "startsAt": fired.starts_at,
                "endsAt": ends,
                "generatorURL": f"http://prometheus.example/graph?g0.expr=ALERTS%7Balertname%3D%22{spec.name}%22%7D",
                "fingerprint": spec.fingerprint,
            }
        ],
        "groupLabels": {"alertname": spec.name},
        "commonLabels": {"alertname": spec.name, "severity": spec.severity},
        "commonAnnotations": {},
        "externalURL": "http://alertmanager.example:9093",
        "version": "4",
        "groupKey": f'{{}}:{{alertname="{spec.name}"}}',
        "truncatedAlerts": 0,
    }


def build_incident_burst(size: int) -> list[AlertSpec]:
    """``size`` alert specs sharing app/component/region, drawn from one
    coherent symptom set (e.g. high CPU + latency spike + exhausted pool)."""
    app = random.choice(APPS)
    component = random.choice(COMPONENTS)
    region = random.choice(REGIONS)

    symptoms = list(random.choice(INCIDENT_SYMPTOM_SETS))
    random.shuffle(symptoms)
    names = [symptoms[i % len(symptoms)] for i in range(size)]

    # Bursts skew more severe than the baseline stream — looks like an incident.
    burst_weights = (20, 30, 30, 20)
    return [
        AlertSpec(
            name=name,
            severity=random.choices(SEVERITIES, weights=burst_weights, k=1)[0],
            region=region,
            app=app,
            component=component,
        )
        for name in names
    ]
