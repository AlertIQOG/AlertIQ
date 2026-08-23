import httpx

from app.core.config import settings
from app.core.exceptions import NotificationError
from app.schemas.notification import NotificationMessage


class SlackChannel:
    """Sends messages to Slack: Incoming Webhook (fixed channel) by default,
    or the Web API (``chat.postMessage``) for a custom ``to`` channel when
    ``SLACK_BOT_TOKEN`` is configured."""

    name = "slack"

    def is_configured(self) -> bool:
        return bool(settings.SLACK_WEBHOOK_URL or settings.SLACK_BOT_TOKEN)

    def send(self, message: NotificationMessage, to: str | None = None) -> None:
        text = f"*{message.title}*\n{message.body}"
        if to:
            if not settings.SLACK_BOT_TOKEN:
                raise NotificationError(
                    "A custom Slack channel was requested but SLACK_BOT_TOKEN "
                    "is not configured — set it to enable per-rule channel routing."
                )
            self._send_via_api(text, channel=to)
        else:
            self._send_via_webhook(text)

    def _send_via_webhook(self, text: str) -> None:
        if not settings.SLACK_WEBHOOK_URL:
            raise NotificationError("SLACK_WEBHOOK_URL is not configured")
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

    def _send_via_api(self, text: str, *, channel: str) -> None:
        try:
            response = httpx.post(
                "https://slack.com/api/chat.postMessage",
                headers={"Authorization": f"Bearer {settings.SLACK_BOT_TOKEN}"},
                json={"channel": channel, "text": text},
                timeout=10,
            )
        except httpx.HTTPError as exc:
            raise NotificationError(f"Slack API request failed: {exc}") from exc

        if response.status_code >= 400:
            raise NotificationError(
                f"Slack API returned {response.status_code}: {response.text}"
            )

        # The Web API always returns 200, even on failure — the real result is
        # in the body's `ok` field.
        body = response.json()
        if not body.get("ok"):
            raise NotificationError(f"Slack API error: {body.get('error', 'unknown')}")


slack_channel = SlackChannel()
