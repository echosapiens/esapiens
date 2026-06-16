"""Runs router — read, list, cancel, and fetch logs for pipeline runs."""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.pipeline import Pipeline
from app.models.run import Run
from app.models.session import ResearchSession
from app.schemas.run import RunRead, RunLogChunk

router = APIRouter(tags=["runs"])

# Placeholder user dependency
async def _fake_user_id() -> uuid.UUID:
    return uuid.UUID("00000000-0000-0000-0000-000000000001")


# ── Read ─────────────────────────────────────────────────────────────

@router.get("/runs/{run_id}", response_model=RunRead)
async def get_run(
    run_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    user_id: Annotated[uuid.UUID, Depends(_fake_user_id)],
) -> Run:
    """Get a single run by ID."""
    run = await db.get(Run, run_id)
    if run is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Run not found")
    return run


# ── List ─────────────────────────────────────────────────────────────

@router.get("/pipelines/{pipeline_id}/runs", response_model=list[RunRead])
async def list_runs(
    pipeline_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    user_id: Annotated[uuid.UUID, Depends(_fake_user_id)],
) -> list[Run]:
    """List all runs for a pipeline."""
    stmt = (
        select(Run)
        .where(Run.pipeline_id == pipeline_id)
        .order_by(Run.created_at.asc())
    )
    result = await db.execute(stmt)
    return list(result.scalars().all())


# ── Cancel ───────────────────────────────────────────────────────────

@router.post("/runs/{run_id}/cancel", response_model=RunRead)
async def cancel_run(
    run_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    user_id: Annotated[uuid.UUID, Depends(_fake_user_id)],
) -> Run:
    """Cancel a running or pending run."""
    run = await db.get(Run, run_id)
    if run is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Run not found")
    if run.status not in ("pending", "running"):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Cannot cancel run in '{run.status}' state",
        )

    run.status = "failed"
    run.exit_code = -1
    await db.flush()
    await db.refresh(run)
    return run


# ── Logs ─────────────────────────────────────────────────────────────

@router.get("/runs/{run_id}/logs", response_model=list[RunLogChunk])
async def get_run_logs(
    run_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    user_id: Annotated[uuid.UUID, Depends(_fake_user_id)],
    stream: str = "stdout",
) -> list[RunLogChunk]:
    """Retrieve log chunks for a run. Query param `stream` selects stdout or stderr."""
    run = await db.get(Run, run_id)
    if run is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Run not found")

    log_text: str | None = run.stdout_log if stream == "stdout" else run.stderr_log
    if log_text is None:
        return []

    # For now return a single chunk; in production this would paginate
    # or stream from an external log store (e.g. S3, Modal volume).
    return [
        RunLogChunk(
            run_id=run.id,
            stream=stream,
            offset=0,
            text=log_text,
        )
    ]


# ── Job Monitor (cross-session live job dashboard) ──────────────────────


class JobSummary(BaseModel):
    """Summary of a single run for the Job Monitor page."""

    run_id: str
    pipeline_id: str
    pipeline_name: str
    session_id: str
    session_title: str
    step_name: str
    container_ref: str | None
    status: str
    progress: int = Field(default=0, ge=0, le=100)
    exit_code: int | None
    modal_sandbox_id: str | None
    started_at: str | None
    completed_at: str | None
    created_at: str


class JobsListResponse(BaseModel):
    """Response for the Job Monitor endpoint."""

    active: list[JobSummary] = Field(default_factory=list)
    recent: list[JobSummary] = Field(default_factory=list)
    total_active: int = 0


@router.get("/jobs", response_model=JobsListResponse)
async def list_jobs(
    db: Annotated[AsyncSession, Depends(get_db)],
    user_id: Annotated[uuid.UUID, Depends(_fake_user_id)],
    active_only: bool = False,
    limit: int = 50,
) -> JobsListResponse:
    """List all runs across all sessions for the Job Monitor dashboard.

    Returns:
      - active: runs in pending/running state (for the live progress page)
      - recent: recently completed/failed runs (last 24h, capped at `limit`)

    All runs execute on Modal sandboxes — the VPS just monitors them.
    """
    # Active runs (pending or running)
    active_stmt = (
        select(Run, Pipeline, ResearchSession)
        .join(Pipeline, Run.pipeline_id == Pipeline.id)
        .join(ResearchSession, Pipeline.session_id == ResearchSession.id)
        .where(
            Pipeline.session_id.in_(
                select(ResearchSession.id).where(ResearchSession.user_id == user_id)
            ),
            Run.status.in_(("pending", "running")),
        )
        .order_by(Run.created_at.desc())
    )
    active_result = await db.execute(active_stmt)
    active_rows = active_result.all()

    # Recent completed/failed runs
    recent_stmt = (
        select(Run, Pipeline, ResearchSession)
        .join(Pipeline, Run.pipeline_id == Pipeline.id)
        .join(ResearchSession, Pipeline.session_id == ResearchSession.id)
        .where(
            Pipeline.session_id.in_(
                select(ResearchSession.id).where(ResearchSession.user_id == user_id)
            ),
            Run.status.in_(("completed", "failed")),
        )
        .order_by(Run.completed_at.desc().nulls_last())
        .limit(limit)
    )
    recent_result = await db.execute(recent_stmt)
    recent_rows = recent_result.all()

    def _to_summary(run: Run, pipeline: Pipeline, session: ResearchSession) -> JobSummary:
        return JobSummary(
            run_id=str(run.id),
            pipeline_id=str(pipeline.id),
            pipeline_name=pipeline.name,
            session_id=str(session.id),
            session_title=session.title,
            step_name=run.step_name,
            container_ref=run.container_ref,
            status=run.status,
            progress=run.progress,
            exit_code=run.exit_code,
            modal_sandbox_id=run.modal_sandbox_id,
            started_at=run.started_at.isoformat() if run.started_at else None,
            completed_at=run.completed_at.isoformat() if run.completed_at else None,
            created_at=run.created_at.isoformat(),
        )

    active_jobs = [_to_summary(r, p, s) for r, p, s in active_rows]
    recent_jobs = [_to_summary(r, p, s) for r, p, s in recent_rows]

    if active_only:
        return JobsListResponse(active=active_jobs, recent=[], total_active=len(active_jobs))

    return JobsListResponse(
        active=active_jobs,
        recent=recent_jobs,
        total_active=len(active_jobs),
    )