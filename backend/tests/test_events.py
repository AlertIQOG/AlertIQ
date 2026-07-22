"""Tests for the live-update event bus and its SSE endpoint.

Covers the three layers of the feature:

  * ``EventBus`` semantics — thread-safe publish, fan-out, overflow handling,
    and the "no loop bound = silent no-op" contract that keeps scripts and
    unit tests side-effect free;
  * the ``/events/stream`` SSE generator (a published event is rendered as a
    ``data:`` frame; auth still guards the route).  The generator is driven
    directly because ``TestClient`` buffers a response to completion — an
    infinite SSE stream would hang the test;
  * service-layer emission — the alert upsert publishes ``alert.created`` /
    ``alert.updated`` after commit.
"""

import asyncio
import json
import threading
import uuid

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, delete

from app.api.v1.events import _event_stream
from app.core.database import engine
from app.main import app
from app.models.alert import Alert, AlertSeverity, AlertStatus
from app.models.source import Source
from app.schemas.alert import AlertCreate
from app.services.alert import alert_service
from app.services.events import EventBus, event_bus

# ── EventBus unit tests (no DB, no app) ───────────────────────────


def test_publish_without_bound_loop_is_noop():
    bus = EventBus()
    bus.publish("alert.created", uuid.uuid4())  # must not raise


def test_publish_from_worker_thread_reaches_subscriber():
    async def scenario():
        bus = EventBus()
        bus.bind_loop(asyncio.get_running_loop())
        queue = bus.subscribe()

        thread = threading.Thread(
            target=bus.publish, args=("alert.created", "abc-123")
        )
        thread.start()
        thread.join()

        event = await asyncio.wait_for(queue.get(), timeout=2)
        assert event == {"type": "alert.created", "id": "abc-123"}

    asyncio.run(scenario())


def test_unsubscribed_queue_receives_nothing():
    async def scenario():
        bus = EventBus()
        bus.bind_loop(asyncio.get_running_loop())
        queue = bus.subscribe()
        bus.unsubscribe(queue)

        bus.publish("alert.created", "x")
        await asyncio.sleep(0)  # let call_soon_threadsafe callbacks run
        assert queue.empty()

    asyncio.run(scenario())


def test_overflow_drops_oldest_and_keeps_newest():
    async def scenario():
        bus = EventBus()
        bus.bind_loop(asyncio.get_running_loop())
        queue = bus.subscribe()

        for i in range(queue.maxsize + 5):
            bus.publish("alert.updated", str(i))
        await asyncio.sleep(0)

        assert queue.qsize() == queue.maxsize
        last = None
        while not queue.empty():
            last = queue.get_nowait()
        assert last == {"type": "alert.updated", "id": str(queue.maxsize + 4)}

    asyncio.run(scenario())


# ── SSE stream generator ──────────────────────────────────────────


class _ConnectedRequest:
    """Stands in for a live ``fastapi.Request`` that never disconnects."""

    async def is_disconnected(self) -> bool:
        return False


def test_stream_renders_published_event_as_data_frame():
    async def scenario():
        event_bus.bind_loop(asyncio.get_running_loop())
        try:
            stream = _event_stream(_ConnectedRequest())

            # The opening comment proves the subscription is registered,
            # so an event published now cannot be missed.
            first = await asyncio.wait_for(anext(stream), timeout=2)
            assert first.startswith(": connected")

            event_bus.publish("alert.created", "e2e-alert-id")

            frame = await asyncio.wait_for(anext(stream), timeout=2)
            assert frame.startswith("data:")
            payload = json.loads(frame[len("data:"):].strip())
            assert payload == {"type": "alert.created", "id": "e2e-alert-id"}

            # Closing the generator must unsubscribe the client's queue.
            await stream.aclose()
            assert event_bus._subscribers == set()
        finally:
            event_bus.unbind_loop()

    asyncio.run(scenario())


def test_stream_requires_auth():
    with TestClient(app) as client:
        response = client.get("/api/v1/events/stream")
        assert response.status_code == 401


# ── Service-layer emission (alert upsert — the ingest hot path) ───


@pytest.fixture
def seeded_source(monkeypatch):
    published: list[tuple[str, str]] = []
    monkeypatch.setattr(
        event_bus,
        "publish",
        lambda event_type, entity_id=None: published.append(
            (event_type, str(entity_id))
        ),
    )

    source_id = uuid.uuid4()
    with Session(engine) as s:
        s.add(Source(id=source_id, name="events-test", provider_type="grafana"))
        s.commit()

    yield source_id, published

    with Session(engine) as s:
        s.exec(delete(Alert).where(Alert.source_id == source_id))
        s.exec(delete(Source).where(Source.id == source_id))
        s.commit()


def test_upsert_publishes_created_then_updated(seeded_source):
    source_id, published = seeded_source
    payload = AlertCreate(
        source_id=source_id,
        external_id="evt-1",
        message="CPU high",
        severity=AlertSeverity.WARNING,
        status=AlertStatus.OPEN,
    )

    with Session(engine) as s:
        alert, created = alert_service.upsert(s, obj_in=payload)
        assert created is True
        assert published == [("alert.created", str(alert.id))]

        _, created_again = alert_service.upsert(s, obj_in=payload)
        assert created_again is False
        assert published[1] == ("alert.updated", str(alert.id))
