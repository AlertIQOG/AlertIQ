"""
In-process event bus powering the ``/events/stream`` SSE endpoint.

Services publish thin *invalidation signals* (``{"type": "alert.created",
"id": "..."}``) after committing a mutation; connected UI clients react by
re-fetching through the regular REST endpoints.  Events carry no entity
payload on purpose — the REST layer stays the single source of truth for
serialization, auth, and filtering.

Threading model
---------------
FastAPI runs the (synchronous) service layer in worker threads, while SSE
subscribers are async generators living on the event loop.  ``publish`` is
therefore safe to call from any thread: it hands the fan-out to the loop via
``call_soon_threadsafe``.  The loop is captured once at application startup
(see the lifespan hook in ``app.main``); before that — e.g. in unit tests or
scripts that never start the ASGI app — ``publish`` is a silent no-op.

This is a single-process design.  Running uvicorn with multiple workers would
require an external broker (Postgres LISTEN/NOTIFY, Redis); for this
deployment one worker is the documented setup.
"""

import asyncio
import threading
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

from app.core.logging import logger

# Per-subscriber buffer. Events are cheap invalidation signals, so a slow
# consumer simply loses the oldest ones — it re-syncs on its next refetch.
_QUEUE_MAXSIZE = 100


class EventBus:
    """Fan-out of mutation events to all connected SSE subscribers."""

    def __init__(self) -> None:
        self._loop: asyncio.AbstractEventLoop | None = None
        self._subscribers: set[asyncio.Queue[dict[str, Any]]] = set()
        self._lock = threading.Lock()
        # Per-thread deferral buffer (see ``deferred``). Thread-local because
        # each request is handled start-to-finish on one worker thread, so one
        # request's deferral must not swallow another's events.
        self._local = threading.local()

    def bind_loop(self, loop: asyncio.AbstractEventLoop) -> None:
        """Capture the running event loop (called once from app startup)."""
        self._loop = loop

    def unbind_loop(self) -> None:
        """Forget the loop on shutdown so late publishes become no-ops."""
        self._loop = None

    def subscribe(self) -> "asyncio.Queue[dict[str, Any]]":
        """Register a new subscriber queue (event-loop side)."""
        queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue(
            maxsize=_QUEUE_MAXSIZE
        )
        with self._lock:
            self._subscribers.add(queue)
        return queue

    def unsubscribe(self, queue: "asyncio.Queue[dict[str, Any]]") -> None:
        """Remove a subscriber queue when its SSE connection closes."""
        with self._lock:
            self._subscribers.discard(queue)

    @contextmanager
    def deferred(self) -> Iterator[None]:
        """
        Hold this thread's events until the block exits, then emit them once.

        A multi-step operation passes through states no client should ever
        render. Ingest is the motivating case: each alert is announced as it is
        persisted, and only *then* does correlation decide whether it belongs
        in a group and should be dismissed. A client refetching on that first
        announcement sees members as standalone alerts a few milliseconds
        before they are folded away — and, because the client throttles
        refetches, it can sit on that half-built picture for a full second.

        Deferring the whole batch means the first thing a client sees is the
        finished result. Duplicate ``(type, id)`` pairs collapse, so a storm
        costs one flush rather than one event per alert per step.

        Events are flushed even when the block raises: whatever committed
        before the failure still has to reach connected clients.
        """
        outer: list[tuple[str, Any]] | None = getattr(self._local, "buffer", None)
        buffer: list[tuple[str, Any]] = []
        self._local.buffer = buffer
        try:
            yield
        finally:
            self._local.buffer = outer
            if outer is not None:
                # Nested block — let the outermost one decide when to emit.
                outer.extend(buffer)
            else:
                seen: set[tuple[str, str]] = set()
                for event_type, entity_id in buffer:
                    key = (event_type, str(entity_id))
                    if key in seen:
                        continue
                    seen.add(key)
                    self._emit(event_type, entity_id)

    def publish(self, event_type: str, entity_id: Any = None) -> None:
        """
        Emit an event from any thread.

        Call this *after* the transaction commits, so a client refetching in
        response is guaranteed to see the new state. Inside a ``deferred``
        block the event is buffered instead and emitted when the block exits.
        """
        buffer: list[tuple[str, Any]] | None = getattr(self._local, "buffer", None)
        if buffer is not None:
            buffer.append((event_type, entity_id))
            return
        self._emit(event_type, entity_id)

    def _emit(self, event_type: str, entity_id: Any = None) -> None:
        """Hand a single event to the event loop for fan-out."""
        loop = self._loop
        if loop is None or loop.is_closed():
            return

        event: dict[str, Any] = {"type": event_type}
        if entity_id is not None:
            event["id"] = str(entity_id)

        try:
            loop.call_soon_threadsafe(self._fan_out, event)
        except RuntimeError:
            # Loop shut down between the check and the call — drop the event.
            logger.debug("Event %s dropped: event loop is closed", event_type)

    def _fan_out(self, event: dict[str, Any]) -> None:
        with self._lock:
            subscribers = list(self._subscribers)
        for queue in subscribers:
            try:
                queue.put_nowait(event)
            except asyncio.QueueFull:
                # Drop the oldest event to make room — the subscriber only
                # uses events as refetch triggers, so gaps are harmless.
                try:
                    queue.get_nowait()
                    queue.put_nowait(event)
                except (asyncio.QueueEmpty, asyncio.QueueFull):
                    pass


event_bus = EventBus()
