"""
Contract for outbound notification channels.

Every channel exposes ``name``, reports whether it is configured, and sends a
``NotificationMessage``.  Channels raise ``NotificationError`` on failure; the
dispatcher catches it and reports a per-channel result.
Mirrors the duck-typed contract style of ``app/providers/base.py``.
"""

from typing import Protocol

from app.schemas.notification import NotificationMessage


class NotificationChannel(Protocol):
    """Structural contract that every notification channel must satisfy."""

    name: str

    def is_configured(self) -> bool:
        """Return True when the channel has the settings it needs to send."""
        ...

    def send(self, message: NotificationMessage, to: str | None = None) -> None:
        """Deliver the message. Raises NotificationError on failure."""
        ...
