"""Note schemas."""

import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class NoteCreate(BaseModel):
    """Schema for creating a note."""

    author: str = Field(
        ...,
        min_length=1,
        max_length=255,
        description="Note author",
        examples=["ofir.kaya"],
    )
    content: str = Field(
        ...,
        min_length=1,
        max_length=5000,
        description="Note content",
        examples=["Escalated to DevOps team — network latency confirmed."],
    )


class NoteRead(BaseModel):
    """Schema for reading a note."""

    model_config = {"from_attributes": True}

    id: uuid.UUID
    alert_id: uuid.UUID
    author: str
    content: str
    created_at: datetime | None = None
