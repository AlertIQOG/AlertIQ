import uuid
from datetime import datetime
from enum import Enum

from sqlalchemy import Column
from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import Field, SQLModel


class IncidentPriority(str, Enum):
    P1 = "P1"
    P2 = "P2"
    P3 = "P3"
    P4 = "P4"


class IncidentStage(str, Enum):
    OPEN = "Open"
    IN_PROGRESS = "In Progress"
    RESOLVED = "Resolved"


class Incident(SQLModel, table=True):
    __tablename__ = "incidents"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    title: str
    priority: IncidentPriority
    stage: IncidentStage = Field(default=IncidentStage.OPEN)
    assignee: str = Field(default="Unassigned")
    source: str = Field(default="manual")
    linked_alert_id: uuid.UUID | None = Field(default=None)
    notes: str = Field(default="")
    affected_services: list = Field(default_factory=list, sa_column=Column(JSONB))
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
