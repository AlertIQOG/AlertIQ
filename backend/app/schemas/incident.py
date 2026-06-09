"""Pydantic schemas for the Incident resource."""

import uuid
from datetime import datetime

from pydantic import BaseModel, Field

from app.models.incident import IncidentPriority, IncidentStage


class IncidentCreate(BaseModel):
    title: str
    priority: IncidentPriority
    stage: IncidentStage = IncidentStage.OPEN
    assignee: str = "Unassigned"
    source: str = "manual"
    linked_alert_id: uuid.UUID | None = None
    notes: str = ""
    affected_services: list[str] = Field(default_factory=list)


class IncidentUpdate(BaseModel):
    title: str | None = None
    priority: IncidentPriority | None = None
    stage: IncidentStage | None = None
    assignee: str | None = None
    notes: str | None = None
    affected_services: list[str] | None = None
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class IncidentRead(BaseModel):
    model_config = {"from_attributes": True}

    id: uuid.UUID
    title: str
    priority: IncidentPriority
    stage: IncidentStage
    assignee: str
    source: str
    linked_alert_id: uuid.UUID | None
    notes: str
    affected_services: list[str]
    created_at: datetime
    updated_at: datetime
