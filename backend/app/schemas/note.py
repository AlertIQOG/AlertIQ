"""Note schemas."""

import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class NoteCreate(BaseModel):
    """Schema for creating a note.

    The author is taken from the authenticated user, never from the client.
    """

    content: str = Field(
        ...,
        min_length=1,
        max_length=5000,
        description="Note content",
        examples=["Escalated to DevOps team — network latency confirmed."],
    )


class NoteUpdate(BaseModel):
    """Schema for editing an existing note (content only)."""

    content: str = Field(
        ...,
        min_length=1,
        max_length=5000,
        description="Updated note content",
        examples=["Root cause was a stuck migration — killed the PID and it drained."],
    )


class NoteRead(BaseModel):
    """Schema for reading a note."""

    model_config = {"from_attributes": True}

    id: uuid.UUID
    alert_id: uuid.UUID
    author: str
    content: str
    created_at: datetime | None = None
