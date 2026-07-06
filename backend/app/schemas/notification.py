from typing import Literal

from pydantic import BaseModel, Field

NotificationChannelName = Literal["slack", "email"]
DEFAULT_CHANNELS: list[NotificationChannelName] = ["slack", "email"]


class NotificationMessage(BaseModel):
    """Channel-agnostic payload. Correlation triggers will build one of these later."""

    title: str = Field(min_length=1, max_length=200)
    body: str = Field(min_length=1)


class SendNotificationRequest(NotificationMessage):
    channels: list[NotificationChannelName] = Field(
        default_factory=lambda: list(DEFAULT_CHANNELS)
    )
    to: str | None = None  # overrides EMAIL_DEFAULT_TO for the email channel


class ChannelResult(BaseModel):
    channel: str
    ok: bool
    detail: str


class SendNotificationResponse(BaseModel):
    results: list[ChannelResult]
