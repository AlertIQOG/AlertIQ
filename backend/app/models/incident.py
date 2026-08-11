import uuid
from datetime import datetime
from enum import Enum

from sqlalchemy import Column, DateTime, func
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
    # Primary alert this incident came from (kept for existing links/UI).
    linked_alert_id: uuid.UUID | None = Field(default=None)
    # Every alert promoted into this incident, including the primary one.
    linked_alert_ids: list = Field(default_factory=list, sa_column=Column(JSONB))
    notes: str = Field(default="")
    affected_services: list = Field(default_factory=list, sa_column=Column(JSONB))
    # Timezone-aware, DB-managed timestamps, matching every other model.
    created_at: datetime | None = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), server_default=func.now(), nullable=False),
    )
    updated_at: datetime | None = Field(
        default=None,
        sa_column=Column(
            DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
        ),
    )
