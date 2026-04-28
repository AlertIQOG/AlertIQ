"""
Prometheus Alertmanager webhook adapter.

Converts native Prometheus Alertmanager payloads into ``AlertCreate`` objects.
"""

import uuid
from typing import Any

from pydantic import BaseModel, Field

from app.models.alert import AlertSeverity, AlertStatus
from app.schemas.alert import AlertCreate

_SEVERITY_MAP: dict[str, AlertSeverity] = {
    "critical": AlertSeverity.CRITICAL,
    "error": AlertSeverity.ERROR,
    "warning": AlertSeverity.WARNING,
    "info": AlertSeverity.INFO,
}
_DEFAULT_SEVERITY = AlertSeverity.WARNING

_STATUS_MAP: dict[str, AlertStatus] = {
    "firing": AlertStatus.OPEN,
    "resolved": AlertStatus.SOLVED,
}
_DEFAULT_STATUS = AlertStatus.OPEN


class PrometheusAlert(BaseModel):
    status: str = "firing"
    labels: dict[str, str] = Field(default_factory=dict)
    annotations: dict[str, str] = Field(default_factory=dict)
    startsAt: str | None = None
    endsAt: str | None = None
    generatorURL: str | None = None
    fingerprint: str = ""


class PrometheusWebhook(BaseModel):
    receiver: str = ""
    status: str = "firing"
    alerts: list[PrometheusAlert] = Field(default_factory=list)
    groupLabels: dict[str, str] = Field(default_factory=dict)
    commonLabels: dict[str, str] = Field(default_factory=dict)
    commonAnnotations: dict[str, str] = Field(default_factory=dict)
    externalURL: str = ""
    version: str = ""
    groupKey: str = ""
    truncatedAlerts: int = 0


class PrometheusNormalizer:
    def normalize(
        self,
        source_id: uuid.UUID,
        payload: PrometheusWebhook,
    ) -> list[AlertCreate]:
        results: list[AlertCreate] = []
        for alert in payload.alerts:
            labels = alert.labels
            annotations = alert.annotations

            severity_raw = labels.get("severity", "").lower()
            severity = _SEVERITY_MAP.get(severity_raw, _DEFAULT_SEVERITY)

            status_raw = alert.status.lower()
            status = _STATUS_MAP.get(status_raw, _DEFAULT_STATUS)

            message = labels.get("alertname", "Unnamed Prometheus Alertmanager Alert")

            extra_fields: dict[str, Any] = {
                "fingerprint": alert.fingerprint,
                "labels": labels,
                "annotations": annotations,
            }
            if alert.startsAt:
                extra_fields["startsAt"] = alert.startsAt
            if alert.endsAt:
                extra_fields["endsAt"] = alert.endsAt
            if alert.generatorURL:
                extra_fields["generatorURL"] = alert.generatorURL

            results.append(
                AlertCreate(
                    source_id=source_id,
                    message=message,
                    severity=severity,
                    status=status,
                    application=labels.get("app") or labels.get("job"),
                    component=labels.get("component"),
                    region=labels.get("region"),
                    node_name=labels.get("instance"),
                    operator=labels.get("operator"),
                    extra_fields=extra_fields,
                )
            )

        return results


prometheus_normalizer = PrometheusNormalizer()
