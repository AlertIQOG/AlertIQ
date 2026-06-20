"""CopilotSuggestion model — cached generated suggestions, one per alert.

A suggestion is keyed to the alert and a hash of its queryable content plus the
generation provider. A cache hit (same hash + provider) is served instantly with
no Voyage/LLM call; a content change or an explicit regenerate produces a fresh
row in place.
"""

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import Column, DateTime, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import Field, SQLModel


class CopilotSuggestion(SQLModel, table=True):
    __tablename__ = "copilot_suggestions"

    __table_args__ = (
        UniqueConstraint("alert_id", name="uq_copilot_suggestion_alert"),
    )

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    alert_id: uuid.UUID = Field(
        foreign_key="alerts.id", ondelete="CASCADE", index=True
    )
    content_hash: str
    provider: str
    # Full serialized structured result (precedent_found, diagnosis, steps, ...).
    payload: dict[str, Any] = Field(default_factory=dict, sa_column=Column(JSONB))

    created_at: datetime | None = Field(
        default=None,
        sa_column=Column(
            DateTime(timezone=True), server_default=func.now(), nullable=False
        ),
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
