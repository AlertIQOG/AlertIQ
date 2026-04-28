"""Pydantic schemas for the Alert resource."""

import hashlib
import json
import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field, model_validator

from app.models.alert import AlertSeverity, AlertStatus


class AlertCreate(BaseModel):
    """Payload accepted when creating a new alert."""

    source_id: uuid.UUID
    message: str
    application: str | None = None
    component: str | None = None
    impact: str | None = None
    region: str | None = None
    node_name: str | None = None
    operator: str | None = None
    severity: AlertSeverity
    status: AlertStatus = AlertStatus.OPEN
    extra_fields: dict[str, Any] = Field(default_factory=dict)
    external_id: str = Field(default="", description="SHA-256 hash of alert content — set automatically.")

    @model_validator(mode="after")
    def _compute_external_id(self) -> "AlertCreate":
        payload = {
            "source_id": str(self.source_id),
            "message": self.message,
            "application": self.application,
            "component": self.component,
            "impact": self.impact,
            "region": self.region,
            "node_name": self.node_name,
            "operator": self.operator,
            "severity": self.severity.value,
            "extra_fields": self.extra_fields,
        }
        canonical = json.dumps(payload, sort_keys=True, ensure_ascii=False)
        self.external_id = hashlib.sha256(canonical.encode()).hexdigest()
        return self


class AlertUpdate(BaseModel):
    """Payload accepted when partially updating an alert."""

    message: str | None = None
    severity: AlertSeverity | None = None
    status: AlertStatus | None = None
    application: str | None = None
    component: str | None = None
    impact: str | None = None
    region: str | None = None
    node_name: str | None = None
    operator: str | None = None
    extra_fields: dict[str, Any] | None = None


class AlertRead(BaseModel):
    """Schema returned to the client — never exposes the raw DB model."""

    model_config = {"from_attributes": True}

    id: uuid.UUID
    source_id: uuid.UUID
    external_id: str
    message: str
    application: str | None = None
    component: str | None = None
    impact: str | None = None
    region: str | None = None
    node_name: str | None = None
    operator: str | None = None
    severity: AlertSeverity
    status: AlertStatus
    extra_fields: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime | None = None
    updated_at: datetime | None = None
