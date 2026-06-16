"""WebSocket endpoint for real-time state synchronization.

Provides:
  - /ws/{session_id} — WebSocket route that authenticates via JWT query param,
    sends backlog of missed events, subscribes to Redis Pub/Sub for live events,
    and handles client actions (reconcile, approve, reject).
"""

from __future__ import annotations

import asyncio
import json
import logging
import uuid
from typing import Any

import redis.asyncio as aioredis
from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect, status
from jose import JWTError, jwt

from app.config import settings
from app.database import async_session_factory
from app.models.session import ResearchSession
from app.services.agent import AgentService
from app.services.event_engine import EventEngine
from app.services.reconciler import Reconciler
from sqlalchemy import select

logger = logging.getLogger(__name__)

router = APIRouter()

# ── Redis channel pattern for session events ─────────────────────────────
SESSION_CHANNEL_PREFIX = "esapiens:session:"
HEARTBEAT_INTERVAL = 30  # seconds


async def _authenticate_ws_token(token: str) -> uuid.UUID | None:
    """Decode a JWT token and return the user_id, or None if invalid."""
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        user_id: str | None = payload.get("sub")
        if user_id is None:
            return None
        return uuid.UUID(user_id)
    except (JWTError, ValueError):
        return None


@router.websocket("/ws/{session_id}")
async def ws_session_events(
    websocket: WebSocket,
    session_id: uuid.UUID,
    token: str = Query(..., description="JWT access token"),
) -> None:
    """WebSocket endpoint for real-time event streaming per session.

    Protocol:
      - On connect: authenticate, send backlog of missed events
      - Client sends {"action": "reconcile", "after_seq_id": N} → server responds with events after that seq_id
      - Client sends {"action": "approve", "pipeline_id": "..."} → triggers AgentService.approve_pipeline
      - Client sends {"action": "reject", "pipeline_id": "..."} → triggers AgentService.reject_pipeline
      - Server forwards Redis Pub/Sub events to client
      - Heartbeat every 30 seconds
    """

    # ── Authenticate ──────────────────────────────────────────────────
    user_id = await _authenticate_ws_token(token)
    if user_id is None:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="Invalid token")
        return

    # ── Validate session ownership ────────────────────────────────────
    async with async_session_factory() as db:
        session = await db.get(ResearchSession, session_id)
        if session is None or session.user_id != user_id:
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION, reason="Session not found")
            return

    await websocket.accept()
    logger.info("WebSocket connected: user=%s session=%s", user_id, session_id)

    # ── Send backlog of missed events ─────────────────────────────────
    event_engine = EventEngine()
    try:
        backlog = await event_engine.get_events_after(session_id, after_seq_id=0)
        if backlog:
            events_data = [
                {
                    "type": "event",
                    "seq_id": e.seq_id,
                    "event_type": e.event_type,
                    "payload": e.payload if isinstance(e.payload, dict) else {},
                    "created_at": e.created_at.isoformat() if e.created_at else None,
                }
                for e in backlog
            ]
            await websocket.send_json({"type": "backlog", "events": events_data, "count": len(events_data)})
            logger.info("Sent %d backlog events to session=%s", len(events_data), session_id)
        else:
            await websocket.send_json({"type": "backlog", "events": [], "count": 0})
    except Exception:
        logger.exception("Error sending backlog for session=%s", session_id)

    # ── Subscribe to Redis Pub/Sub for this session ───────────────────
    redis: aioredis.Redis | None = None
    pubsub: aioredis.client.PubSub | None = None
    channel_name = f"{SESSION_CHANNEL_PREFIX}{session_id}"

    try:
        redis = aioredis.from_url(settings.REDIS_URL, decode_responses=True)
        pubsub = redis.pubsub()
        await pubsub.subscribe(channel_name)
    except Exception:
        logger.exception("Failed to subscribe to Redis Pub/Sub for session=%s", session_id)
        await websocket.close(code=status.WS_1011_INTERNAL_ERROR, reason="Redis connection failed")
        return

    # ── Background tasks ──────────────────────────────────────────────
    receive_task = asyncio.create_task(
        _handle_client_messages(websocket, session_id, user_id)
    )
    pubsub_task = asyncio.create_task(
        _forward_pubsub_events(websocket, pubsub, session_id)
    )
    heartbeat_task = asyncio.create_task(
        _send_heartbeats(websocket)
    )

    try:
        # Wait for any task to complete (usually means disconnect)
        done, pending = await asyncio.wait(
            [receive_task, pubsub_task, heartbeat_task],
            return_when=asyncio.FIRST_COMPLETED,
        )
        # Cancel remaining tasks
        for task in pending:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
    except WebSocketDisconnect:
        logger.info("WebSocket disconnected: user=%s session=%s", user_id, session_id)
    except Exception:
        logger.exception("WebSocket error for session=%s", session_id)
    finally:
        # ── Cleanup ────────────────────────────────────────────────────
        heartbeat_task.cancel()
        receive_task.cancel()
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

        try:
            await websocket.close()
        except Exception:
            pass

        logger.info("WebSocket cleaned up: user=%s session=%s", user_id, session_id)


async def _handle_client_messages(
    websocket: WebSocket,
    session_id: uuid.UUID,
    user_id: uuid.UUID,
) -> None:
    """Handle incoming messages from the WebSocket client."""
    try:
        while True:
            raw = await websocket.receive_text()
            try:
                message = json.loads(raw)
            except json.JSONDecodeError:
                await websocket.send_json({"type": "error", "detail": "Invalid JSON"})
                continue

            action = message.get("action")

            if action == "reconcile":
                after_seq_id = message.get("after_seq_id", 0)
                event_engine = EventEngine()
                events = await event_engine.get_events_after(
                    session_id, after_seq_id=int(after_seq_id)
                )
                events_data = [
                    {
                        "type": "event",
                        "seq_id": e.seq_id,
                        "event_type": e.event_type,
                        "payload": e.payload if isinstance(e.payload, dict) else {},
                        "created_at": e.created_at.isoformat() if e.created_at else None,
                    }
                    for e in events
                ]
                await websocket.send_json({
                    "type": "reconcile",
                    "after_seq_id": after_seq_id,
                    "events": events_data,
                    "count": len(events_data),
                })

            elif action == "approve":
                pipeline_id_str = message.get("pipeline_id")
                if not pipeline_id_str:
                    await websocket.send_json({"type": "error", "detail": "Missing pipeline_id"})
                    continue
                try:
                    pipeline_id = uuid.UUID(pipeline_id_str)
                except ValueError:
                    await websocket.send_json({"type": "error", "detail": "Invalid pipeline_id"})
                    continue

                comment = message.get("comment")
                agent_svc = AgentService()
                try:
                    await agent_svc.approve_pipeline(pipeline_id, user_comment=comment)
                    await websocket.send_json({
                        "type": "action_result",
                        "action": "approve",
                        "pipeline_id": pipeline_id_str,
                        "status": "ok",
                    })
                except Exception as exc:
                    logger.exception("Error approving pipeline %s", pipeline_id)
                    await websocket.send_json({
                        "type": "action_result",
                        "action": "approve",
                        "pipeline_id": pipeline_id_str,
                        "status": "error",
                        "detail": str(exc),
                    })

            elif action == "reject":
                pipeline_id_str = message.get("pipeline_id")
                if not pipeline_id_str:
                    await websocket.send_json({"type": "error", "detail": "Missing pipeline_id"})
                    continue
                try:
                    pipeline_id = uuid.UUID(pipeline_id_str)
                except ValueError:
                    await websocket.send_json({"type": "error", "detail": "Invalid pipeline_id"})
                    continue

                comment = message.get("comment")
                agent_svc = AgentService()
                try:
                    await agent_svc.reject_pipeline(pipeline_id, user_comment=comment)
                    await websocket.send_json({
                        "type": "action_result",
                        "action": "reject",
                        "pipeline_id": pipeline_id_str,
                        "status": "ok",
                    })
                except Exception as exc:
                    logger.exception("Error rejecting pipeline %s", pipeline_id)
                    await websocket.send_json({
                        "type": "action_result",
                        "action": "reject",
                        "pipeline_id": pipeline_id_str,
                        "status": "error",
                        "detail": str(exc),
                    })

            else:
                await websocket.send_json({
                    "type": "error",
                    "detail": f"Unknown action: {action}",
                })

    except WebSocketDisconnect:
        pass  # Expected on disconnect
    except asyncio.CancelledError:
        raise
    except Exception:
        logger.exception("Error in client message handler")


async def _forward_pubsub_events(
    websocket: WebSocket,
    pubsub: aioredis.client.PubSub,
    session_id: uuid.UUID,
) -> None:
    """Forward Redis Pub/Sub messages for the session to the WebSocket client."""
    try:
        async for message in pubsub.listen():
            if message["type"] == "message":
                try:
                    data = message["data"]
                    if isinstance(data, str):
                        payload = json.loads(data)
                    else:
                        payload = data

                    # Forward as a typed event
                    await websocket.send_json({
                        "type": "event",
                        "seq_id": payload.get("seq_id"),
                        "event_type": payload.get("event_type", payload.get("payload", {}).get("event_type", "")),
                        "payload": payload.get("payload", {}),
                        "created_at": payload.get("created_at"),
                    })
                except json.JSONDecodeError:
                    # Forward raw if not JSON
                    await websocket.send_json({
                        "type": "raw",
                        "data": data if isinstance(data, str) else data.decode("utf-8", errors="replace"),
                    })
                except Exception:
                    logger.exception("Error forwarding pubsub event for session=%s", session_id)
    except asyncio.CancelledError:
        raise
    except Exception:
        logger.exception("PubSub listener error for session=%s", session_id)


async def _send_heartbeats(websocket: WebSocket) -> None:
    """Send periodic heartbeat pings to keep the connection alive."""
    try:
        while True:
            await asyncio.sleep(HEARTBEAT_INTERVAL)
            await websocket.send_json({"type": "heartbeat"})
    except asyncio.CancelledError:
        raise
    except Exception:
        pass  # Connection likely closed