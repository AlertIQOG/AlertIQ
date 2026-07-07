"""
Grafana Alertmanager webhook adapter.

Converts the Grafana unified-alerting webhook payload into a list of
``AlertCreate`` objects that the alert service can persist.

Grafana sends a batched payload like::

    {
      "status": "firing",
      "alerts": [
        {
          "status": "firing",
          "labels": {"alertname": "HighCPU", "severity": "critical", ...},
          "annotations": {"summary": "...", "description": "..."},
          "startsAt": "...",
          "endsAt": "...",
          "fingerprint": "abc123",
          "values": {}
        }
      ],
      ...
    }

References:
  - https://grafana.com/docs/grafana/latest/alerting/configure-notifications/manage-contact-points/integrations/webhook-notifier/
"""

import uuid
from typing import Any

from pydantic import BaseModel, Field, field_validator

from app.models.alert import AlertSeverity, AlertStatus
from app.schemas.alert import AlertCreate

# ─── Severity mapping ───────────────────────────────────────────────
# Grafana uses lowercase label values; AlertIQ uses title-case enum members.
_SEVERITY_MAP: dict[str, AlertSeverity] = {
    "critical": AlertSeverity.CRITICAL,
    "error": AlertSeverity.ERROR,
    "warning": AlertSeverity.WARNING,
    "info": AlertSeverity.INFO,
}

_DEFAULT_SEVERITY = AlertSeverity.WARNING

# ─── Status mapping ─────────────────────────────────────────────────
_STATUS_MAP: dict[str, AlertStatus] = {
    "firing": AlertStatus.OPEN,
    "resolved": AlertStatus.SOLVED,
}

_DEFAULT_STATUS = AlertStatus.OPEN


# ─── Pydantic schemas for the incoming Grafana payload ──────────────
class GrafanaAlert(BaseModel):
    """A single alert inside the Grafana webhook batch."""

    status: str = "firing"
    labels: dict[str, str] = Field(default_factory=dict)
    annotations: dict[str, str] = Field(default_factory=dict)
    startsAt: str | None = None
    endsAt: str | None = None
    fingerprint: str = ""
    values: dict[str, Any] = Field(default_factory=dict)

    @field_validator("labels", "annotations", mode="before")
    @classmethod
    def _coerce_str_dict(cls, v: Any) -> dict:
        return v or {}

    @field_validator("values", mode="before")
    @classmethod
    def _coerce_any_dict(cls, v: Any) -> dict:
        return v or {}


class GrafanaWebhook(BaseModel):
    """Top-level Grafana Alertmanager webhook payload."""

    status: str = "firing"
    alerts: list[GrafanaAlert] = Field(default_factory=list)
    commonLabels: dict[str, str] = Field(default_factory=dict)
    commonAnnotations: dict[str, str] = Field(default_factory=dict)
    externalURL: str = ""
    groupLabels: dict[str, str] = Field(default_factory=dict)

    @field_validator("alerts", "commonLabels", "commonAnnotations", "groupLabels", mode="before")
    @classmethod
    def _coerce_null(cls, v: Any) -> Any:
        return v or ([] if isinstance(v, list) else {})


# ─── Normalizer ─────────────────────────────────────────────────────
class GrafanaNormalizer:
    """
    Converts a ``GrafanaWebhook`` into a list of ``AlertCreate`` objects.

    Satisfies the ``AlertNormalizer`` protocol from ``app.providers.base``.
    """

    def normalize(
        self,
        source_id: uuid.UUID,
        payload: GrafanaWebhook,
    ) -> list[AlertCreate]:
        """Map each Grafana alert to an ``AlertCreate``."""
        results: list[AlertCreate] = []
        for alert in payload.alerts:
            labels = alert.labels
            annotations = alert.annotations

            severity_raw = labels.get("severity", "").lower()
            severity = _SEVERITY_MAP.get(severity_raw, _DEFAULT_SEVERITY)

            status_raw = alert.status.lower()
            status = _STATUS_MAP.get(status_raw, _DEFAULT_STATUS)

            message = labels.get("alertname", "Unnamed Grafana Alert")

            # Best-effort field extraction from labels
            application = labels.get("app") or labels.get("job")
            component = labels.get("component")
            region = labels.get("region")

            # Preserve the full Grafana alert for reference / debugging
            extra_fields: dict[str, Any] = {
                # Provider name — lets correlation rules scope by ``source``
                # (matches the value the rule form sends). Not otherwise a
                # resolvable alert field.
                "source": "Grafana",
                "fingerprint": alert.fingerprint,
                "labels": labels,
                "annotations": annotations,
                "values": alert.values,
            }
            if alert.startsAt:
                extra_fields["startsAt"] = alert.startsAt
            if alert.endsAt:
                extra_fields["endsAt"] = alert.endsAt

            results.append(
                AlertCreate(
                    source_id=source_id,
                    external_id=alert.fingerprint,  # stable provider fingerprint; falls back to hash if empty
                    message=message,
                    severity=severity,
                    status=status,
                    application=application,
                    component=component,
                    region=region,
                    extra_fields=extra_fields,
                )
            )

        return results


# Module-level singleton — import and use directly.
grafana_normalizer = GrafanaNormalizer()
