"""Runs router — read, list, cancel, and fetch logs for pipeline runs."""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.run import Run
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