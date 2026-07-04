from fastapi import APIRouter

from app.schemas.notification import (
    SendNotificationRequest,
    SendNotificationResponse,
)
from app.services.notifications import notification_service

router = APIRouter()


@router.post("/send", response_model=SendNotificationResponse)
def send_notification(
    *, body: SendNotificationRequest
) -> SendNotificationResponse:
    """Send a notification to the requested channels (Slack / Email).

    Per-channel failures are reported in the response rather than failing the
    whole request, so one misconfigured channel never blocks the others.
    """
    results = notification_service.send(body, channels=body.channels, to=body.to)
    return SendNotificationResponse(results=results)
