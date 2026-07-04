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
    """Schema returned to the client.

    Includes ``webhook_secret`` so operators can configure the sending
    provider (Grafana / Alertmanager). The sources API itself requires
    authentication, so the secret is only visible to logged-in users.
    """

    model_config = {"from_attributes": True}

    id: uuid.UUID
    name: str
    provider_type: str
    is_active: bool
    webhook_secret: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
