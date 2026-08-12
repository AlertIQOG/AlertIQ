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
        """Send a message to all requested notification channels.

        Each channel is isolated so one failure does not prevent the remaining
        channels from being attempted. Failures are logged explicitly and are
        also returned to the caller for rule-level visibility.
        """
        results: list[ChannelResult] = []

        for name in channels:
            channel = self._channels.get(name)

            if channel is None:
                detail = "unknown channel"

                logger.error(
                    "Notification channel %s does not exist",
                    name,
                )

                results.append(
                    ChannelResult(
                        channel=name,
                        ok=False,
                        detail=detail,
                    )
                )
                continue

            if not channel.is_configured():
                detail = "not configured"

                logger.error(
                    "Notification channel %s is not configured",
                    name,
                )

                results.append(
                    ChannelResult(
                        channel=name,
                        ok=False,
                        detail=detail,
                    )
                )
                continue

            try:
                channel.send(
                    message,
                    to=to,
                )

                logger.info(
                    "Notification sent successfully via %s",
                    name,
                )

                results.append(
                    ChannelResult(
                        channel=name,
                        ok=True,
                        detail="sent",
                    )
                )

            except NotificationError as exc:
                logger.error(
                    "Notification via %s failed: %s",
                    name,
                    exc.detail,
                )

                results.append(
                    ChannelResult(
                        channel=name,
                        ok=False,
                        detail=exc.detail,
                    )
                )

            except Exception as exc:  # noqa: BLE001
                logger.exception(
                    "Unexpected notification failure via %s",
                    name,
                )

                results.append(
                    ChannelResult(
                        channel=name,
                        ok=False,
                        detail=f"unexpected error: {exc}",
                    )
                )

        failed = [
            result
            for result in results
            if not result.ok
        ]

        if failed:
            logger.error(
                "Notification dispatch completed with %d/%d failed channel(s)",
                len(failed),
                len(results),
            )

        return results


# Registry keyed by each channel's own name so the keys can never drift from it.
notification_service = NotificationService(
    channels={c.name: c for c in (slack_channel, email_channel)}
)
