"""
Channel-agnostic notification dispatcher.

This is the seam a future correlation-rule trigger will call: build a
``NotificationMessage`` from a matched rule and call ``notification_service.send(...)``.
"""

from app.core.exceptions import NotificationError
from app.core.logging import logger
from app.schemas.notification import (
    ChannelResult,
    NotificationChannelName,
    NotificationMessage,
)
from app.services.notifications.base import NotificationChannel
from app.services.notifications.email_smtp import email_channel
from app.services.notifications.slack import slack_channel


class NotificationService:
    def __init__(self, channels: dict[str, NotificationChannel]) -> None:
        self._channels = channels

    def send(
        self,
        message: NotificationMessage,
        channels: list[NotificationChannelName],
        to: str | None = None,
    ) -> list[ChannelResult]:
        """Send to each requested channel, isolating failures so one bad channel
        does not block the others. Returns a per-channel result."""
        results: list[ChannelResult] = []

        for name in channels:
            channel = self._channels.get(name)

            if channel is None:
                results.append(
                    ChannelResult(channel=name, ok=False, detail="unknown channel")
                )
                continue

            if not channel.is_configured():
                results.append(
                    ChannelResult(channel=name, ok=False, detail="not configured")
                )
                continue

            try:
                channel.send(message, to=to)
                results.append(ChannelResult(channel=name, ok=True, detail="sent"))
            except NotificationError as exc:
                logger.warning("Notification via %s failed: %s", name, exc.detail)
                results.append(ChannelResult(channel=name, ok=False, detail=exc.detail))

        return results


# Registry keyed by each channel's own name so the keys can never drift from it.
notification_service = NotificationService(
    channels={c.name: c for c in (slack_channel, email_channel)}
)
