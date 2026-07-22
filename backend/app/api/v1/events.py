"""
Server-Sent Events stream for live UI updates.

Clients hold a long-lived ``GET /events/stream`` connection and receive one
``data: {"type": ..., "id": ...}`` frame per mutation published on the
:data:`~app.services.events.event_bus`.  Events are invalidation signals —
the client refetches through the regular REST endpoints on receipt.
"""

import asyncio
import json
from collections.abc import AsyncIterator

from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse

from app.services.events import event_bus

router = APIRouter()

# Comment frame sent while idle so proxies and browsers don't reap the
# connection; also bounds how long a stale generator lingers after disconnect.
_KEEPALIVE_SECONDS = 15


async def _event_stream(request: Request) -> AsyncIterator[str]:
    queue = event_bus.subscribe()
    try:
        # Opening comment lets the client confirm the stream is live.
        yield ": connected\n\n"
        while True:
            try:
                event = await asyncio.wait_for(
                    queue.get(), timeout=_KEEPALIVE_SECONDS
                )
                yield f"data: {json.dumps(event)}\n\n"
            except asyncio.TimeoutError:
                if await request.is_disconnected():
                    break
                yield ": keep-alive\n\n"
    finally:
        # Runs on client disconnect too (generator is closed by the server).
        event_bus.unsubscribe(queue)


@router.get("/stream")
async def stream_events(request: Request) -> StreamingResponse:
    """Long-lived SSE stream of mutation events (auth via bearer token)."""
    return StreamingResponse(
        _event_stream(request),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            # Disable buffering in reverse proxies (nginx) so frames flush.
            "X-Accel-Buffering": "no",
        },
    )
