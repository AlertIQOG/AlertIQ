"""
Standalone E2E check for the notification integrations.

Sends a test message directly through the notification service (no HTTP server needed),
using the Slack/SMTP settings from your .env, and prints a per-channel result.

Run from the backend/ directory:

    python -m scripts.send_test_notification
    python -m scripts.send_test_notification --channels slack
    python -m scripts.send_test_notification --to someone@example.com
"""

import argparse
import sys

from app.schemas.notification import DEFAULT_CHANNELS, NotificationMessage
from app.services.notifications import notification_service


def main() -> int:
    parser = argparse.ArgumentParser(description="Send a test AlertIQ notification.")
    default_channels = ",".join(DEFAULT_CHANNELS)
    parser.add_argument(
        "--channels",
        default=default_channels,
        help=f"Comma-separated channels to send to (default: {default_channels}).",
    )
    parser.add_argument("--title", default="AlertIQ test notification")
    parser.add_argument(
        "--body", default="Hello from AlertIQ — notifications are working."
    )
    parser.add_argument("--to", default=None, help="Override email recipient.")
    args = parser.parse_args()

    channels = [c.strip() for c in args.channels.split(",") if c.strip()]
    message = NotificationMessage(title=args.title, body=args.body)

    results = notification_service.send(message, channels=channels, to=args.to)

    print("Notification results:")
    for r in results:
        mark = "OK " if r.ok else "FAIL"
        print(f"  [{mark}] {r.channel}: {r.detail}")

    return 0 if all(r.ok for r in results) else 1


if __name__ == "__main__":
    sys.exit(main())
