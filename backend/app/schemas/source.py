"""Pydantic schemas for the Source resource."""

import uuid
from datetime import datetime

from pydantic import BaseModel


class SourceCreate(BaseModel):
    """Payload accepted when creating a new source provider."""

    name: str
    provider_type: str
    is_active: bool = True


class SourceUpdate(BaseModel):
    """Payload accepted when partially updating a source."""

    name: str | None = None
    provider_type: str | None = None
    is_active: bool | None = None


class SourceRead(BaseModel):
    """Schema returned to the client."""

    model_config = {"from_attributes": True}

    id: uuid.UUID
    name: str
    provider_type: str
    is_active: bool
    created_at: datetime | None = None
    updated_at: datetime | None = None
