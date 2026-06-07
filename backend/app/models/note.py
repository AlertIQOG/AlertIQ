"""Note model — operational notes attached to alerts."""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Column, DateTime, Text, func
from sqlmodel import Field, Relationship, SQLModel

if TYPE_CHECKING:
    from app.models.alert import Alert


class Note(SQLModel, table=True):
    __tablename__ = "notes"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    alert_id: uuid.UUID = Field(foreign_key="alerts.id", ondelete="CASCADE", index=True)
    author: str = Field(index=True)
    content: str = Field(sa_column=Column(Text, nullable=False))
    created_at: datetime | None = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    )

    alert: "Alert" = Relationship(back_populates="notes")
