"""Pydantic schemas for the Alert resource."""

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from app.models.alert import AlertSeverity, AlertStatus


class AlertCreate(BaseModel):
    """Payload accepted when creating a new alert."""

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
    status: AlertStatus = AlertStatus.OPEN
    extra_fields: dict[str, Any] = Field(default_factory=dict)


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
