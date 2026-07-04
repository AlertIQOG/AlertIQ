import smtplib
from email.message import EmailMessage

from app.core.config import settings
from app.core.exceptions import NotificationError
from app.schemas.notification import NotificationMessage


class EmailChannel:
    """Sends messages as email over SMTP (e.g. Gmail with an App Password)."""

    name = "email"

    def is_configured(self) -> bool:
        return bool(
            settings.SMTP_HOST and settings.SMTP_USERNAME and settings.SMTP_PASSWORD
        )

    def send(self, message: NotificationMessage, to: str | None = None) -> None:
        recipient = to or settings.EMAIL_DEFAULT_TO
        if not recipient:
            raise NotificationError(
                "No email recipient (set EMAIL_DEFAULT_TO or pass 'to')"
            )

        sender = settings.SMTP_FROM or settings.SMTP_USERNAME

        email = EmailMessage()
        email["Subject"] = message.title
        email["From"] = sender
        email["To"] = recipient
        email.set_content(message.body)

        try:
            host, port = settings.SMTP_HOST, settings.SMTP_PORT
            with smtplib.SMTP(host, port, timeout=15) as smtp:
                if settings.SMTP_USE_TLS:
                    smtp.starttls()
                smtp.login(settings.SMTP_USERNAME, settings.SMTP_PASSWORD)
                smtp.send_message(email)
        except (smtplib.SMTPException, OSError) as exc:
            raise NotificationError(f"Email send failed: {exc}") from exc


email_channel = EmailChannel()
