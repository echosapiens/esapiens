"""SSE (Server-Sent Events) endpoint as fallback for WebSocket.

Provides:
  - /api/events/{session_id}/stream — EventSource-compatible SSE stream that
    authenticates via JWT query param, subscribes to Redis Pub/Sub, and sends
    keepalive comments every 15 seconds.
"""

from __future__ import annotations

import asyncio
import json
import logging
import uuid
from typing import Any

import redis.asyncio as aioredis
from fastapi import APIRouter, Query, Request
from fastapi.responses import StreamingResponse
from jose import JWTError, jwt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import async_session_factory
from app.models.session import ResearchSession
from app.services.event_engine import EventEngine

logger = logging.getLogger(__name__)

router = APIRouter()

# ── Constants ───────────────────────────────────────────────────────────────
SESSION_CHANNEL_PREFIX = "esapiens:session:"
KEEPALIVE_INTERVAL = 15  # seconds


async def _authenticate_sse_token(token: str) -> uuid.UUID | None:
    """Decode a JWT token and return the user_id, or None if invalid."""
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        user_id: str | None = payload.get("sub")
        if user_id is None:
            return None
        return uuid.UUID(user_id)
    except (JWTError, ValueError):
        return None


@router.get("/api/events/{session_id}/stream")
async def sse_session_stream(
    session_id: uuid.UUID,
    token: str = Query(..., description="JWT access token"),
) -> StreamingResponse:
    """SSE endpoint for real-time event streaming per session.

    This is an EventSource-compatible fallback for clients that cannot use
    WebSocket connections. It subscribes to the Redis Pub/Sub channel for
    the given session and streams events as SSE data lines.

    The client must provide a valid JWT token as a query parameter.
    """

    # ── Authenticate ──────────────────────────────────────────────────
    user_id = await _authenticate_sse_token(token)
    if user_id is None:
        return StreamingResponse(
            _sse_error("Invalid or expired token"),
            media_type="text/event-stream",
            status_code=401,
        )

    # ── Validate session ownership ────────────────────────────────────
    async with async_session_factory() as db:
        session = await db.get(ResearchSession, session_id)
        if session is None or session.user_id != user_id:
            return StreamingResponse(
                _sse_error("Session not found"),
                media_type="text/event-stream",
                status_code=404,
            )

    # ── Build the SSE generator ────────────────────────────────────────
    return StreamingResponse(
        _event_stream(session_id, user_id),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # Disable nginx buffering
        },
    )


async def _event_stream(
    session_id: uuid.UUID,
    user_id: uuid.UUID,
) -> Any:
    """Async generator that yields SSE events for the given session."""

    # ── Send initial backlog ──────────────────────────────────────────
    event_engine = EventEngine()
    try:
        backlog = await event_engine.get_events_after(session_id, after_seq_id=0)
        if backlog:
            events_data = [
                {
                    "seq_id": e.seq_id,
                    "event_type": e.event_type,
                    "payload": e.payload if isinstance(e.payload, dict) else {},
                    "created_at": e.created_at.isoformat() if e.created_at else None,
                }
                for e in backlog
            ]
            yield f"event: backlog\ndata: {json.dumps(events_data)}\n\n"
        else:
            yield f"event: backlog\ndata: []\n\n"
    except Exception:
        logger.exception("Error sending SSE backlog for session=%s", session_id)
        yield f"event: error\ndata: {{\"detail\": \"Failed to load backlog\"}}\n\n"

    # ── Subscribe to Redis Pub/Sub ────────────────────────────────────
    redis: aioredis.Redis | None = None
    pubsub: aioredis.client.PubSub | None = None
    channel_name = f"{SESSION_CHANNEL_PREFIX}{session_id}"

    try:
        redis = aioredis.from_url(settings.REDIS_URL, decode_responses=True)
        pubsub = redis.pubsub()
        await pubsub.subscribe(channel_name)
    except Exception:
        logger.exception("Failed to subscribe to Redis Pub/Sub for SSE session=%s", session_id)
        yield f"event: error\ndata: {{\"detail\": \"Redis connection failed\"}}\n\n"
        return

    # ── Stream events ─────────────────────────────────────────────────
    keepalive_task = asyncio.create_task(_keepalive_loop())
    pubsub_task = asyncio.create_task(_pubsub_listener(pubsub, session_id))

    try:
        done, pending = await asyncio.wait(
            [keepalive_task, pubsub_task],
            return_when=asyncio.FIRST_COMPLETED,
        )
        for task in pending:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
    except asyncio.CancelledError:
        pass
    except Exception:
        logger.exception("SSE stream error for session=%s", session_id)
    finally:
        keepalive_task.cancel()
        pubsub_task.cancel()

        try:
            await pubsub.unsubscribe(channel_name)
            await pubsub.close()
        except Exception:
            pass

        if redis:
            try:
                await redis.close()
            except Exception:
                pass


async def _keepalive_loop() -> Any:
    """Yield SSE keepalive comments every KEEPALIVE_INTERVAL seconds."""
    try:
        while True:
            await asyncio.sleep(KEEPALIVE_INTERVAL)
            yield f": keepalive\n\n"
    except asyncio.CancelledError:
        raise


async def _pubsub_listener(
    pubsub: aioredis.client.PubSub,
    session_id: uuid.UUID,
) -> Any:
    """Yield SSE events from Redis Pub/Sub messages."""
    try:
        async for message in pubsub.listen():
            if message["type"] == "message":
                data = message["data"]
                if isinstance(data, str):
                    yield f"event: event\ndata: {data}\n\n"
                else:
                    yield f"event: event\ndata: {data.decode('utf-8', errors='replace')}\n\n"
    except asyncio.CancelledError:
        raise
    except Exception:
        logger.exception("PubSub listener error for SSE session=%s", session_id)


async def _sse_error(detail: str) -> Any:
    """Yield a single SSE error event."""
    yield f"event: error\ndata: {json.dumps({'detail': detail})}\n\n"