import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import Column, DateTime, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import Field, SQLModel


class CorrelationRule(SQLModel, table=True):
    __tablename__ = "correlation_rules"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)

    name: str = Field(index=True)
    description: str | None = None

    enabled: bool = Field(default=True, index=True)

    # Defines which alerts this rule applies to
    scope: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSONB))

    # Defines the logical conditions that trigger this rule
    conditions: list[dict[str, Any]] = Field(default_factory=list, sa_column=Column(JSONB))

    # Defines the time range in minutes for grouping related alerts
    time_window_minutes: int = Field(default=5)

    # Defines which alert fields are used to group alerts together
    group_by: list[str] = Field(default_factory=list, sa_column=Column(JSONB))

    # Actions to run when the rule matches (multiselect): "aggregate" folds the
    # alerts into an aggregated alert, "email" sends an email notification.
    actions: list[str] = Field(
        default_factory=lambda: ["aggregate"], sa_column=Column(JSONB)
    )

    # Email addresses notified when the "email" action fires. Empty means fall
    # back to the global EMAIL_DEFAULT_TO.
    email_recipients: list[str] = Field(default_factory=list, sa_column=Column(JSONB))

    created_at: datetime | None = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), server_default=func.now(), nullable=False),
    )

    updated_at: datetime | None = Field(
        default=None,
        sa_column=Column(
            DateTime(timezone=True),
            server_default=func.now(),
            onupdate=func.now(),
            nullable=False,
        ),
    )