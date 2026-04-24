import uuid
from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING, Any

from sqlalchemy import Column, DateTime, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import Field, Relationship, SQLModel

if TYPE_CHECKING:
    from app.models.source import Source


class AlertSeverity(str, Enum):
    INFO = "Info"
    WARNING = "Warning"
    ERROR = "Error"
    CRITICAL = "Critical"
class AlertStatus(str, Enum):
    OPEN = "Open"
    IN_PROGRESS = "In progress"
    SOLVED = "Solved"
    DISMISSED = "Dismissed"


class Alert(SQLModel, table=True):
    __tablename__ = "alerts"
    
    # Deduplication Constraint! A single provider (source) should not push an alert with the exact same external_id twice.
    __table_args__ = (
        UniqueConstraint("source_id", "external_id", name="uq_alert_source_external_id"),
    )

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    source_id: uuid.UUID = Field(foreign_key="sources.id", ondelete="CASCADE", index=True)
    external_id: str = Field(index=True)
    message: str
    application: str | None = Field(default=None, index=True)
    component: str | None = Field(default=None, index=True)
    impact: str | None = Field(default=None)
    region: str | None = Field(default=None)
    node_name: str | None = Field(default=None)
    operator: str | None = Field(default=None)
    severity: AlertSeverity
    status: AlertStatus = Field(default=AlertStatus.OPEN)
    created_at: datetime | None = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    )
    updated_at: datetime | None = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    )
    
    extra_fields: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSONB))

    source: "Source" = Relationship(back_populates="alerts")
