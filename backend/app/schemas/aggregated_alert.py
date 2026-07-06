"""Pydantic schemas for the AggregatedAlert resource (read-only API)."""

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from app.models.aggregated_alert import AggregatedAlertStatus
from app.models.alert import AlertSeverity


class AggregatedAlertRead(BaseModel):
    """Schema returned to the client for an aggregated alert."""

    model_config = {"from_attributes": True}

    id: uuid.UUID
    rule_id: uuid.UUID
    rule_name: str
    title: str
    group_key: str
    group_values: dict[str, Any] = Field(default_factory=dict)
    severity: AlertSeverity
    status: AggregatedAlertStatus
    count: int
    alert_ids: list[str] = Field(default_factory=list)
    close_reason: str | None = None
    first_seen: datetime
    last_seen: datetime
    window_ends_at: datetime
    created_at: datetime | None = None
    updated_at: datetime | None = None
