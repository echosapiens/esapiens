"""OutboxRelay — polls the outbox table and publishes unpublished events to Redis Pub/Sub.

This implements the transactional outbox pattern: application code writes events
to the outbox table within the same DB transaction as the state change. The relay
then periodically scans for unpublished rows and pushes them to Redis, guaranteeing
at-least-once delivery.
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import AsyncGenerator

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import async_session_factory
from app.models.outbox import Outbox

logger = logging.getLogger(__name__)


class OutboxRelay:
    """Background worker that publishes outbox events to Redis Pub/Sub."""

    def __init__(self) -> None:
        self._running = False
        self._task: asyncio.Task | None = None  # type: ignore[type-arg]
        self._redis = None

    # ── Lifecycle ─────────────────────────────────────────────────────

    async def start(self) -> None:
        """Start the relay loop as a background task."""
        if self._running:
            return
        self._running = True
        self._task = asyncio.create_task(self._run_loop())
        logger.info("OutboxRelay started (interval=%ds)", settings.OUTBOX_RELAY_INTERVAL_SECONDS)

    async def stop(self) -> None:
        """Gracefully stop the relay loop."""
        self._running = False
        if self._task and not self._task.done():
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        if self._redis:
            await self._redis.close()
            self._redis = None
        logger.info("OutboxRelay stopped")

    # ── Main loop ─────────────────────────────────────────────────────

    async def _run_loop(self) -> None:
        """Poll-and-publish loop."""
        import redis.asyncio as aioredis

        self._redis = aioredis.from_url(settings.REDIS_URL, decode_responses=True)

        while self._running:
            try:
                await self._publish_pending()
            except Exception:
                logger.exception("OutboxRelay error during publish cycle")
            await asyncio.sleep(settings.OUTBOX_RELAY_INTERVAL_SECONDS)

    async def _publish_pending(self) -> int:
        """Find unpublished outbox rows and publish them to Redis."""
        published = 0
        async with async_session_factory() as db:
            stmt = (
                select(Outbox)
                .where(Outbox.published.is_(False))
                .order_by(Outbox.id.asc())
                .limit(100)
            )
            result = await db.execute(stmt)
            rows = list(result.scalars().all())

            for row in rows:
                payload = json.dumps(
                    {
                        "id": row.id,
                        "aggregate_id": row.aggregate_id,
                        "event_type": row.event_type,
                        "payload": row.payload,
                        "created_at": row.created_at.isoformat() if row.created_at else None,
                    }
                )
                await self._redis.publish(settings.OUTBOX_REDIS_CHANNEL, payload)

                # Mark as published
                await db.execute(
                    update(Outbox)
                    .where(Outbox.id == row.id)
                    .values(published=True)
                )
                published += 1

            if published:
                await db.commit()
                logger.info("OutboxRelay published %d event(s)", published)

        return published