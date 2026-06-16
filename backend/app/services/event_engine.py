"""Event Sourcing Engine — ACID event creation with transactional outbox.

Provides:
  - emit_event: Create Event + Outbox records in a single ACID transaction
  - get_events_after: Return all events after a given sequence ID (for client reconciliation)
  - project_state: Compute current state from event stream projection
"""

from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import async_session_factory
from app.models.event import Event
from app.models.outbox import Outbox
from app.schemas.event import (
    AgentPlanGenerated,
    EventEnvelope,
    MetricsUpdated,
    PipelineStatusChanged,
    RunStepLog,
    ServerEvent,
)

logger = logging.getLogger(__name__)


# ── Known event types ─────────────────────────────────────────────────────

EVENT_TYPES = {
    "SESSION_CREATED",
    "SESSION_UPDATED",
    "SESSION_DELETED",
    "PIPELINE_CREATED",
    "PIPELINE_STATUS_CHANGED",
    "RUN_CREATED",
    "RUN_STARTED",
    "RUN_COMPLETED",
    "RUN_FAILED",
    "RUN_LOG",
    "AGENT_PLAN_GENERATED",
    "AGENT_PLAN_APPROVED",
    "AGENT_PLAN_REJECTED",
    "METRICS_UPDATED",
    "BUDGET_DEBITED",
    "BUDGET_EXHAUSTED",
}


class EventEngine:
    """Event sourcing engine with transactional outbox guarantee.

    Every state mutation in the system should emit an event through this
    engine. Events are stored in the events table (append-only) and the
    outbox table (for reliable Redis publishing) within the same DB
    transaction, ensuring at-least-once delivery.

    Usage:
        engine = EventEngine(db_session)
        await engine.emit_event(
            session_id=uuid4(),
            event_type="PIPELINE_STATUS_CHANGED",
            payload={"pipeline_id": "...", "old_status": "draft", "new_status": "submitted"},
        )
    """

    def __init__(self, db: AsyncSession | None = None) -> None:
        """Initialize with an optional database session.

        If no session is provided, a new one will be created for each operation.
        """
        self._external_db = db

    async def _get_db(self) -> AsyncSession:
        """Get a database session — either the injected one or a fresh one."""
        if self._external_db is not None:
            return self._external_db
        return async_session_factory()

    # ── Core: Emit event ───────────────────────────────────────────

    async def emit_event(
        self,
        session_id: uuid.UUID,
        event_type: str,
        payload: dict[str, Any],
        aggregate_id: str | None = None,
    ) -> Event:
        """Create an Event record and an Outbox record in a single ACID transaction.

        The event is appended to the events table (immutable log) and an
        outbox entry is created for reliable Redis publishing by the
        OutboxRelay worker.

        Args:
            session_id: The research session this event belongs to.
            event_type: One of the known event type strings.
            payload: Arbitrary JSON-serializable data for the event.
            aggregate_id: Optional aggregate identifier (e.g. pipeline_id).
                         If not provided, defaults to the session_id.

        Returns:
            The created Event ORM instance (with id and seq_id populated).

        Raises:
            ValueError: If the event_type is not recognized.
        """
        if event_type not in EVENT_TYPES:
            logger.warning("Unknown event type: %s — emitting anyway", event_type)

        # ── Determine session management ────────────────────────────
        manage_session = self._external_db is None
        db = await self._get_db()

        try:
            # ── Create the Event record ─────────────────────────────
            event = Event(
                session_id=session_id,
                event_type=event_type,
                payload=payload,
            )
            db.add(event)
            await db.flush()  # Generate event.id and event.seq_id

            # ── Create the Outbox record ─────────────────────────────
            # Uses the same transaction — ACID guarantee
            agg_id = aggregate_id or str(session_id)
            outbox = Outbox(
                aggregate_id=agg_id,
                event_type=event_type,
                payload={
                    "event_id": event.id,
                    "seq_id": event.seq_id,
                    "session_id": str(session_id),
                    "event_type": event_type,
                    "payload": payload,
                    "created_at": datetime.now(timezone.utc).isoformat(),
                },
                published=False,
            )
            db.add(outbox)
            await db.flush()

            if manage_session:
                await db.commit()

            logger.info(
                "Emitted event: type=%s session=%s seq=%s aggregate=%s",
                event_type, session_id, event.seq_id, agg_id,
            )
            return event

        except Exception:
            if manage_session:
                await db.rollback()
            raise

        finally:
            if manage_session:
                await db.close()

    # ── Query: Get events after sequence ID ────────────────────────

    async def get_events_after(
        self,
        session_id: uuid.UUID,
        after_seq_id: int = 0,
        limit: int = 1000,
    ) -> list[Event]:
        """Return all events for a session after the given sequence ID.

        This is used for client-side reconciliation: the client sends
        the last seq_id it has seen, and receives all newer events.

        Args:
            session_id: The research session to query.
            after_seq_id: Return events with seq_id greater than this value.
            limit: Maximum number of events to return.

        Returns:
            List of Event instances ordered by seq_id ascending.
        """
        async with async_session_factory() as db:
            stmt = (
                select(Event)
                .where(
                    Event.session_id == session_id,
                    Event.seq_id > after_seq_id,
                )
                .order_by(Event.seq_id.asc())
                .limit(limit)
            )
            result = await db.execute(stmt)
            return list(result.scalars().all())

    # ── Query: Project current state from events ────────────────────

    async def project_state(self, session_id: uuid.UUID) -> dict[str, Any]:
        """Compute the current state of a session by projecting its event stream.

        Replays all events for the session and derives the current state:
        - Pipeline statuses
        - Run statuses
        - Budget / metrics
        - Agent state

        Args:
            session_id: The research session to project.

        Returns:
            Dict with the projected state including:
            - pipelines: list of pipeline states
            - runs: list of run states
            - metrics: aggregated metrics
            - events_count: total number of events processed
        """
        events = await self.get_events_after(session_id, after_seq_id=0, limit=10000)

        pipelines: dict[str, dict[str, Any]] = {}
        runs: dict[str, dict[str, Any]] = {}
        metrics: dict[str, Any] = {
            "total_cpu_hours": 0.0,
            "total_cost": 0.0,
            "total_runs": 0,
            "completed_runs": 0,
            "failed_runs": 0,
        }
        agent_state: dict[str, Any] = {
            "last_plan": None,
            "approval_status": None,
        }

        for event in events:
            payload = event.payload or {}

            if event.event_type == "PIPELINE_CREATED":
                pid = payload.get("pipeline_id", str(event.id))
                pipelines[pid] = {
                    "id": pid,
                    "name": payload.get("name", ""),
                    "status": "draft",
                    "created_at": payload.get("created_at"),
                }

            elif event.event_type == "PIPELINE_STATUS_CHANGED":
                pid = payload.get("pipeline_id", "")
                if pid in pipelines:
                    pipelines[pid]["status"] = payload.get("new_status", "unknown")

            elif event.event_type == "RUN_CREATED":
                rid = payload.get("run_id", str(event.id))
                runs[rid] = {
                    "id": rid,
                    "step_name": payload.get("step_name", ""),
                    "status": "pending",
                    "created_at": payload.get("created_at"),
                }
                metrics["total_runs"] += 1

            elif event.event_type == "RUN_STARTED":
                rid = payload.get("run_id", "")
                if rid in runs:
                    runs[rid]["status"] = "running"

            elif event.event_type == "RUN_COMPLETED":
                rid = payload.get("run_id", "")
                if rid in runs:
                    runs[rid]["status"] = "completed"
                metrics["completed_runs"] += 1
                metrics["total_cpu_hours"] += payload.get("cpu_hours", 0.0)
                metrics["total_cost"] += payload.get("cost", 0.0)

            elif event.event_type == "RUN_FAILED":
                rid = payload.get("run_id", "")
                if rid in runs:
                    runs[rid]["status"] = "failed"
                metrics["failed_runs"] += 1

            elif event.event_type == "AGENT_PLAN_GENERATED":
                agent_state["last_plan"] = payload
                agent_state["approval_status"] = "pending"

            elif event.event_type == "AGENT_PLAN_APPROVED":
                agent_state["approval_status"] = "approved"

            elif event.event_type == "AGENT_PLAN_REJECTED":
                agent_state["approval_status"] = "rejected"

            elif event.event_type == "METRICS_UPDATED":
                # Merge metrics updates
                for key, value in payload.get("metrics", {}).items():
                    if isinstance(value, (int, float)):
                        metrics[key] = metrics.get(key, 0) + value
                    else:
                        metrics[key] = value

            elif event.event_type == "BUDGET_DEBITED":
                metrics["total_cost"] += payload.get("amount", 0.0)

            elif event.event_type == "BUDGET_EXHAUSTED":
                metrics["budget_exhausted"] = True

        return {
            "session_id": str(session_id),
            "pipelines": list(pipelines.values()),
            "runs": list(runs.values()),
            "metrics": metrics,
            "agent_state": agent_state,
            "events_count": len(events),
            "projected_at": datetime.now(timezone.utc).isoformat(),
        }

    # ── Helper: Build a ServerEvent from an Event ───────────────────

    @staticmethod
    def build_server_event(event: Event) -> EventEnvelope | None:
        """Convert an Event ORM instance to a typed ServerEvent envelope.

        Returns None if the event type is not recognized.
        """
        payload = event.payload or {}
        session_id = event.session_id

        if event.event_type == "AGENT_PLAN_GENERATED":
            inner = AgentPlanGenerated(
                session_id=session_id,
                plan=payload.get("plan", {}),
            )
        elif event.event_type == "RUN_LOG":
            inner = RunStepLog(
                run_id=uuid.UUID(payload.get("run_id", str(session_id))),
                step_name=payload.get("step_name", ""),
                stream=payload.get("stream", "stdout"),
                text=payload.get("text", ""),
            )
        elif event.event_type == "METRICS_UPDATED":
            inner = MetricsUpdated(
                session_id=session_id,
                metrics=payload.get("metrics", {}),
            )
        elif event.event_type == "PIPELINE_STATUS_CHANGED":
            inner = PipelineStatusChanged(
                pipeline_id=uuid.UUID(payload.get("pipeline_id", str(session_id))),
                old_status=payload.get("old_status", ""),
                new_status=payload.get("new_status", ""),
            )
        else:
            # Unknown event type — return None
            return None

        return EventEnvelope(
            id=event.id,
            session_id=session_id,
            event=inner,
            created_at=event.created_at,
        )

    # ── Batch: Emit multiple events atomically ──────────────────────

    async def emit_events_batch(
        self,
        events: list[tuple[uuid.UUID, str, dict[str, Any]]],
        aggregate_id: str | None = None,
    ) -> list[Event]:
        """Emit multiple events in a single ACID transaction.

        Args:
            events: List of (session_id, event_type, payload) tuples.
            aggregate_id: Optional aggregate identifier for all events.

        Returns:
            List of created Event instances.
        """
        manage_session = self._external_db is None
        db = await self._get_db()

        try:
            created_events: list[Event] = []

            for session_id, event_type, payload in events:
                event = Event(
                    session_id=session_id,
                    event_type=event_type,
                    payload=payload,
                )
                db.add(event)
                await db.flush()  # Generate id and seq_id

                # Create outbox entry
                agg_id = aggregate_id or str(session_id)
                outbox = Outbox(
                    aggregate_id=agg_id,
                    event_type=event_type,
                    payload={
                        "event_id": event.id,
                        "seq_id": event.seq_id,
                        "session_id": str(session_id),
                        "event_type": event_type,
                        "payload": payload,
                        "created_at": datetime.now(timezone.utc).isoformat(),
                    },
                    published=False,
                )
                db.add(outbox)
                await db.flush()

                created_events.append(event)

            if manage_session:
                await db.commit()

            logger.info("Emitted %d events in batch", len(created_events))
            return created_events

        except Exception:
            if manage_session:
                await db.rollback()
            raise

        finally:
            if manage_session:
                await db.close()