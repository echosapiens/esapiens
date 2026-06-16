"""Async Job Manager — dispatch heavy work to Modal, return immediately.

The chat agent uses this when the user wants to run a long computation
that shouldn't block the conversation. Flow:

  1. Chat calls AsyncJobManager.dispatch(code) — returns job_id immediately
  2. Background task: spins up Modal sandbox, runs code, captures output
  3. Progress events stream via WebSocket (RUN_PROGRESS)
  4. When done, RUN_STATUS_CHANGED event fires with the full output
  5. Chat agent can subscribe to completion and synthesize a report

The key design property: the chat API NEVER blocks on long-running work.
The user can keep sending messages while the job runs in the background.
When the job completes, the supervisor reflects on the results and
synthesizes a final report.
"""

from __future__ import annotations

import asyncio
import json
import logging
import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import async_session_factory
from app.models.outbox import Outbox
from app.services.event_engine import EventEngine

logger = logging.getLogger(__name__)


# ── Job status ───────────────────────────────────────────────────────────


class AsyncJobStatus(str, Enum):
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class AsyncJobResult(BaseModel):
    """Result of an async code-execution job."""

    job_id: str
    session_id: str
    code: str
    language: str = "python"
    status: AsyncJobStatus = AsyncJobStatus.QUEUED
    progress: int = 0
    exit_code: int | None = None
    stdout: str = ""
    stderr: str = ""
    return_value: str | None = None
    files_produced: list[str] = Field(default_factory=list)
    error: str | None = None
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    started_at: str | None = None
    completed_at: str | None = None
    sandbox_id: str | None = None


# ── Job record persistence ───────────────────────────────────────────────


class AsyncJobRecord(BaseModel):
    """In-memory job record. Persisted to Redis for cross-process access."""

    job_id: str = Field(default_factory=lambda: f"job_{uuid.uuid4().hex[:12]}")
    session_id: str
    user_id: str
    prompt: str = Field(..., description="The original user prompt that triggered this job")
    code: str = ""
    language: str = "python"
    status: AsyncJobStatus = AsyncJobStatus.QUEUED
    progress: int = 0
    result: AsyncJobResult | None = None
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


# ── Job manager ──────────────────────────────────────────────────────────


REDIS_JOB_PREFIX = "esapiens:async_job:"


class AsyncJobManager:
    """Manages async code-execution jobs across the system.

    Jobs are dispatched to Modal sandboxes in background tasks. The chat
    agent gets a job_id immediately and can continue the conversation.
    """

    def __init__(self) -> None:
        self._redis = None
        # Local cache of in-flight jobs (for status queries within the same process)
        self._jobs: dict[str, AsyncJobRecord] = {}

    async def _get_redis(self):
        if self._redis is None:
            import redis.asyncio as aioredis
            self._redis = aioredis.from_url(settings.REDIS_URL, decode_responses=True)
        return self._redis

    async def dispatch(
        self,
        session_id: uuid.UUID,
        user_id: uuid.UUID,
        prompt: str,
        code: str,
        language: str = "python",
        timeout: float = 120.0,
    ) -> AsyncJobRecord:
        """Dispatch a job to a Modal sandbox.

        Returns the job record immediately. The job runs in the background.
        Progress is published to the session's WebSocket channel.
        """
        job = AsyncJobRecord(
            session_id=str(session_id),
            user_id=str(user_id),
            prompt=prompt,
            code=code,
            language=language,
        )
        self._jobs[job.job_id] = job

        # Persist to Redis for cross-process access
        try:
            redis = await self._get_redis()
            await redis.set(
                f"{REDIS_JOB_PREFIX}{job.job_id}",
                job.model_dump_json(),
                ex=3600,  # 1 hour TTL
            )
        except Exception as exc:
            logger.warning("Failed to persist job %s to Redis: %s", job.job_id, exc)

        # Emit JOB_QUEUED event so the chat UI can show "job submitted"
        await self._emit_job_event(
            session_id=session_id,
            job_id=job.job_id,
            event_type="JOB_QUEUED",
            payload={
                "job_id": job.job_id,
                "prompt": prompt[:200],
                "code_preview": code[:200],
            },
        )

        # Dispatch the actual execution in the background — DO NOT BLOCK
        asyncio.create_task(
            self._run_job(job, timeout=timeout)
        )

        logger.info(
            "AsyncJob %s queued for session=%s (code=%d chars)",
            job.job_id, session_id, len(code),
        )
        return job

    async def _run_job(self, job: AsyncJobRecord, timeout: float) -> None:
        """Run the job in a Modal sandbox, update status, emit events.

        This is the background task. The chat API has already returned
        the job_id to the user — this just does the work and publishes
        progress.
        """
        from app.services.code_sandbox import get_code_sandbox
        from app.services.modal_compute import ModalComputeService

        session_id = uuid.UUID(job.session_id)
        try:
            job.status = AsyncJobStatus.RUNNING
            job.progress = 5
            await self._update_job(job)
            await self._emit_job_event(
                session_id=session_id,
                job_id=job.job_id,
                event_type="JOB_STARTED",
                payload={"job_id": job.job_id},
            )

            # Actually run the code
            sandbox = get_code_sandbox()
            exec_result = await sandbox.execute(
                code=job.code,
                language=job.language,  # type: ignore[arg-type]
                timeout=timeout,
                session_id=session_id,
            )

            # Build the result
            if exec_result.error:
                job.status = AsyncJobStatus.FAILED
                job.result = AsyncJobResult(
                    job_id=job.job_id,
                    session_id=job.session_id,
                    code=job.code,
                    language=job.language,
                    status=AsyncJobStatus.FAILED,
                    error=exec_result.error,
                    sandbox_id=exec_result.sandbox_id,
                )
            else:
                job.status = AsyncJobStatus.COMPLETED
                job.progress = 100
                job.result = AsyncJobResult(
                    job_id=job.job_id,
                    session_id=job.session_id,
                    code=job.code,
                    language=job.language,
                    status=AsyncJobStatus.COMPLETED,
                    progress=100,
                    exit_code=exec_result.exit_code,
                    stdout=exec_result.stdout,
                    stderr=exec_result.stderr,
                    files_produced=exec_result.files_produced,
                    sandbox_id=exec_result.sandbox_id,
                )
            await self._update_job(job)

            # Emit JOB_COMPLETED event with full result
            await self._emit_job_event(
                session_id=session_id,
                job_id=job.job_id,
                event_type="JOB_COMPLETED",
                payload={
                    "job_id": job.job_id,
                    "status": job.status.value,
                    "exit_code": exec_result.exit_code,
                    "stdout": exec_result.stdout[:5000] if exec_result.stdout else "",
                    "stderr": exec_result.stderr[:2000] if exec_result.stderr else "",
                    "files_produced": exec_result.files_produced,
                    "error": exec_result.error,
                    "duration_seconds": exec_result.duration_seconds,
                    "sandbox_id": exec_result.sandbox_id,
                },
            )

        except Exception as exc:
            import traceback
            logger.exception("AsyncJob %s failed: %s", job.job_id, exc)
            job.status = AsyncJobStatus.FAILED
            job.result = AsyncJobResult(
                job_id=job.job_id,
                session_id=job.session_id,
                code=job.code,
                language=job.language,
                status=AsyncJobStatus.FAILED,
                error=f"{type(exc).__name__}: {exc}",
            )
            await self._update_job(job)
            await self._emit_job_event(
                session_id=session_id,
                job_id=job.job_id,
                event_type="JOB_FAILED",
                payload={"job_id": job.job_id, "error": str(exc)},
            )

    async def _update_job(self, job: AsyncJobRecord) -> None:
        """Persist the job's current state to Redis."""
        try:
            redis = await self._get_redis()
            await redis.set(
                f"{REDIS_JOB_PREFIX}{job.job_id}",
                job.model_dump_json(),
                ex=3600,
            )
        except Exception as exc:
            logger.debug("Failed to update job %s in Redis: %s", job.job_id, exc)

    async def _emit_job_event(
        self,
        session_id: uuid.UUID,
        job_id: str,
        event_type: str,
        payload: dict[str, Any],
    ) -> None:
        """Emit a job lifecycle event into the outbox.

        This flows through the standard event pipeline → Redis pub/sub →
        WebSocket subscribers on the session channel. The chat UI
        subscribes to these events to show real-time progress.
        """
        try:
            async with async_session_factory() as db:
                engine = EventEngine(db)
                await engine.emit_event(
                    session_id=session_id,
                    event_type=event_type,
                    payload={"job_id": job_id, **payload},
                    aggregate_id=job_id,
                )
                await db.commit()
        except Exception as exc:
            logger.debug("Failed to emit %s for job %s: %s", event_type, job_id, exc)

    # ── Query API ─────────────────────────────────────────────────────

    async def get_job(self, job_id: str) -> AsyncJobRecord | None:
        """Get a job by ID. Checks in-memory cache first, then Redis."""
        if job_id in self._jobs:
            return self._jobs[job_id]
        try:
            redis = await self._get_redis()
            data = await redis.get(f"{REDIS_JOB_PREFIX}{job_id}")
            if data:
                job = AsyncJobRecord.model_validate_json(data)
                self._jobs[job_id] = job
                return job
        except Exception as exc:
            logger.debug("Failed to fetch job %s from Redis: %s", job_id, exc)
        return None

    async def list_jobs(self, session_id: str | None = None) -> list[AsyncJobRecord]:
        """List all jobs, optionally filtered by session."""
        try:
            redis = await self._get_redis()
            keys = []
            async for key in redis.scan_iter(f"{REDIS_JOB_PREFIX}*"):
                keys.append(key)
            jobs = []
            for key in keys:
                data = await redis.get(key)
                if not data:
                    continue
                try:
                    job = AsyncJobRecord.model_validate_json(data)
                    if session_id is None or job.session_id == session_id:
                        jobs.append(job)
                except Exception:
                    continue
            return sorted(jobs, key=lambda j: j.created_at, reverse=True)
        except Exception as exc:
            logger.warning("Failed to list jobs: %s", exc)
            return list(self._jobs.values())


# ── Singleton ────────────────────────────────────────────────────────────

_job_manager: AsyncJobManager | None = None


def get_job_manager() -> AsyncJobManager:
    """Return the singleton AsyncJobManager instance."""
    global _job_manager
    if _job_manager is None:
        _job_manager = AsyncJobManager()
    return _job_manager