import httpx

from app.core.config import settings
from app.core.exceptions import NotificationError
from app.schemas.notification import NotificationMessage


class SlackChannel:
    """Sends messages to a Slack channel via an Incoming Webhook."""

    name = "slack"

    def is_configured(self) -> bool:
        return bool(settings.SLACK_WEBHOOK_URL)

    def send(self, message: NotificationMessage, to: str | None = None) -> None:
        text = f"*{message.title}*\n{message.body}"
        try:
            response = httpx.post(
                settings.SLACK_WEBHOOK_URL,
                json={"text": text},
                timeout=10,
            )
        except httpx.HTTPError as exc:
            raise NotificationError(f"Slack request failed: {exc}") from exc

        if response.status_code >= 400:
            raise NotificationError(
                f"Slack returned {response.status_code}: {response.text}"
            )


slack_channel = SlackChannel()
