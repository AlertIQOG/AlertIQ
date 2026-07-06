"""Unit tests for the outbound notification channels + dispatcher.

No real network / SMTP calls — httpx and smtplib are monkeypatched.
"""

import pytest

from app.core.config import settings
from app.core.exceptions import NotificationError
from app.schemas.notification import NotificationMessage
from app.services.notifications import email_smtp, slack
from app.services.notifications.service import NotificationService

MESSAGE = NotificationMessage(title="Test", body="Hello")


# ─── Slack ────────────────────────────────────────────────────────────────────


class _FakeResponse:
    def __init__(self, status_code: int, text: str = "") -> None:
        self.status_code = status_code
        self.text = text


def test_slack_send_success(monkeypatch):
    monkeypatch.setattr(settings, "SLACK_WEBHOOK_URL", "https://hooks.slack.test/abc")
    captured = {}

    def fake_post(url, json, timeout):
        captured["url"] = url
        captured["json"] = json
        return _FakeResponse(200)

    monkeypatch.setattr(slack.httpx, "post", fake_post)

    slack.SlackChannel().send(MESSAGE)

    assert captured["url"] == "https://hooks.slack.test/abc"
    assert "Test" in captured["json"]["text"]
    assert "Hello" in captured["json"]["text"]


def test_slack_non_2xx_raises(monkeypatch):
    monkeypatch.setattr(settings, "SLACK_WEBHOOK_URL", "https://hooks.slack.test/abc")
    monkeypatch.setattr(
        slack.httpx, "post", lambda *a, **k: _FakeResponse(400, "invalid_payload")
    )

    with pytest.raises(NotificationError):
        slack.SlackChannel().send(MESSAGE)


def test_slack_not_configured(monkeypatch):
    monkeypatch.setattr(settings, "SLACK_WEBHOOK_URL", "")
    assert slack.SlackChannel().is_configured() is False


# ─── Email ────────────────────────────────────────────────────────────────────


class _FakeSMTP:
    instances: list["_FakeSMTP"] = []

    def __init__(self, host, port, timeout=None):
        self.host = host
        self.port = port
        self.started_tls = False
        self.logged_in = None
        self.sent = None
        _FakeSMTP.instances.append(self)

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def starttls(self):
        self.started_tls = True

    def login(self, user, password):
        self.logged_in = (user, password)

    def send_message(self, msg):
        self.sent = msg


def _configure_smtp(monkeypatch):
    monkeypatch.setattr(settings, "SMTP_HOST", "smtp.test")
    monkeypatch.setattr(settings, "SMTP_PORT", 587)
    monkeypatch.setattr(settings, "SMTP_USERNAME", "user@test.com")
    monkeypatch.setattr(settings, "SMTP_PASSWORD", "app-password")
    monkeypatch.setattr(settings, "SMTP_FROM", "")
    monkeypatch.setattr(settings, "SMTP_USE_TLS", True)
    monkeypatch.setattr(settings, "EMAIL_DEFAULT_TO", "dest@test.com")


@pytest.fixture
def smtp_fake(monkeypatch):
    """Configure SMTP settings and patch smtplib.SMTP with the fake; yields it."""
    _configure_smtp(monkeypatch)
    _FakeSMTP.instances.clear()
    monkeypatch.setattr(email_smtp.smtplib, "SMTP", _FakeSMTP)
    return _FakeSMTP


def test_email_send_success(smtp_fake):
    email_smtp.EmailChannel().send(MESSAGE)

    smtp = smtp_fake.instances[-1]
    assert smtp.started_tls is True
    assert smtp.logged_in == ("user@test.com", "app-password")
    assert smtp.sent["To"] == "dest@test.com"
    assert smtp.sent["From"] == "user@test.com"  # falls back to SMTP_USERNAME
    assert smtp.sent["Subject"] == "Test"


def test_email_to_override(smtp_fake):
    email_smtp.EmailChannel().send(MESSAGE, to="override@test.com")

    assert smtp_fake.instances[-1].sent["To"] == "override@test.com"


def test_email_failure_wrapped(monkeypatch):
    _configure_smtp(monkeypatch)

    def boom(*_, **__):
        raise OSError("connection refused")

    monkeypatch.setattr(email_smtp.smtplib, "SMTP", boom)

    with pytest.raises(NotificationError):
        email_smtp.EmailChannel().send(MESSAGE)


def test_email_no_recipient(monkeypatch):
    _configure_smtp(monkeypatch)
    monkeypatch.setattr(settings, "EMAIL_DEFAULT_TO", "")

    with pytest.raises(NotificationError):
        email_smtp.EmailChannel().send(MESSAGE)


# ─── Dispatcher ───────────────────────────────────────────────────────────────


class _StubChannel:
    def __init__(self, name, configured=True, fail=False):
        self.name = name
        self._configured = configured
        self._fail = fail
        self.calls = 0

    def is_configured(self):
        return self._configured

    def send(self, message, to=None):
        self.calls += 1
        if self._fail:
            raise NotificationError(f"{self.name} boom")


def test_dispatcher_skips_unconfigured_and_isolates_failures():
    slack_stub = _StubChannel("slack", fail=True)   # configured but fails
    email_stub = _StubChannel("email", configured=True)  # succeeds
    svc = NotificationService(channels={"slack": slack_stub, "email": email_stub})

    results = svc.send(MESSAGE, channels=["slack", "email"])

    by_channel = {r.channel: r for r in results}
    assert by_channel["slack"].ok is False
    assert by_channel["email"].ok is True  # not blocked by slack failure
    assert email_stub.calls == 1


def test_dispatcher_reports_not_configured():
    email_stub = _StubChannel("email", configured=False)
    svc = NotificationService(channels={"email": email_stub})

    results = svc.send(MESSAGE, channels=["email"])

    assert results[0].ok is False
    assert results[0].detail == "not configured"
    assert email_stub.calls == 0


def test_dispatcher_unknown_channel():
    svc = NotificationService(channels={})
    results = svc.send(MESSAGE, channels=["telegram"])
    assert results[0].ok is False
    assert results[0].detail == "unknown channel"


# ─── Correlation message builder ──────────────────────────────────────────────


def _make_rule_and_alerts():
    import uuid

    from app.models.alert import Alert, AlertSeverity
    from app.models.correlation_rule import CorrelationRule

    rule = CorrelationRule(
        name="High CPU + 5xx",
        time_window_minutes=10,
        group_by=["application", "region"],
        conditions=[{"field": "cpu_usage", "operator": "greater_than", "value": 90}],
    )
    sid = uuid.uuid4()
    alerts = [
        Alert(source_id=sid, external_id="a1", message="CPU 94%",
              severity=AlertSeverity.WARNING, application="checkout",
              region="eu-west-1"),
        Alert(source_id=sid, external_id="a2", message="5xx spike",
              severity=AlertSeverity.CRITICAL, application="checkout",
              region="eu-west-1"),
    ]
    return rule, alerts


def test_build_correlation_message_content():
    from app.services.notifications import build_correlation_message

    rule, alerts = _make_rule_and_alerts()
    msg = build_correlation_message(rule, alerts)

    assert rule.name in msg.title
    assert "Critical" in msg.title or "🔴" in msg.title  # highest severity wins
    assert "matched 2 alert(s)" in msg.body
    assert "Severity:     Critical" in msg.body           # not Warning
    assert "checkout" in msg.body
    assert "cpu_usage greater than 90" in msg.body
    assert str(rule.id) in msg.body


def test_notify_correlation_dispatches_built_message(monkeypatch):
    import app.services.notifications.correlation as corr

    rule, alerts = _make_rule_and_alerts()
    captured = {}

    def fake_send(message, channels, to=None):
        captured["message"] = message
        captured["channels"] = channels
        return []

    monkeypatch.setattr(corr.notification_service, "send", fake_send)
    corr.notify_correlation(rule, alerts)

    assert rule.name in captured["message"].title
    assert captured["channels"] == ["slack", "email"]
