from fastapi import APIRouter

from app.schemas.notification import (
    TestNotificationRequest,
    TestNotificationResponse,
)
from app.services.notifications import notification_service

router = APIRouter()


@router.post("/test", response_model=TestNotificationResponse)
def send_test_notification(
    *, body: TestNotificationRequest
) -> TestNotificationResponse:
    """Send a test message to the requested channels (Slack / Email).

    Standalone endpoint to prove the notification integrations work end-to-end.
    Per-channel failures are reported in the response rather than failing the request.
    """
    results = notification_service.send(body, channels=body.channels, to=body.to)
    return TestNotificationResponse(results=results)
