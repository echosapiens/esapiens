"""Pipelines router — CRUD + submit for pipeline resources."""

from __future__ import annotations

import asyncio
import logging
import uuid
from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import async_session_factory, get_db
from app.models.pipeline import Pipeline
from app.models.run import Run
from app.models.session import ResearchSession
from app.schemas.pipeline import PipelineCreate, PipelineRead, PipelineUpdate
from app.services.modal_compute import ModalComputeService

logger = logging.getLogger(__name__)

router = APIRouter(tags=["pipelines"])

# Placeholder user dependency
async def _fake_user_id() -> uuid.UUID:
    return uuid.UUID("00000000-0000-0000-0000-000000000001")


# ── Create ───────────────────────────────────────────────────────────

@router.post(
    "/sessions/{session_id}/pipelines",
    response_model=PipelineRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_pipeline(
    session_id: uuid.UUID,
    body: PipelineCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    user_id: Annotated[uuid.UUID, Depends(_fake_user_id)],
) -> Pipeline:
    """Create a new pipeline under a session."""
    session = await db.get(ResearchSession, session_id)
    if session is None or session.user_id != user_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")

    pipeline = Pipeline(
        session_id=session_id,
        name=body.name,
        description=body.description,
        dag_json=body.dag_json,
        status="draft",
    )
    db.add(pipeline)
    await db.flush()
    await db.refresh(pipeline)
    return pipeline


# ── List ─────────────────────────────────────────────────────────────

@router.get(
    "/sessions/{session_id}/pipelines",
    response_model=list[PipelineRead],
)
async def list_pipelines(
    session_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    user_id: Annotated[uuid.UUID, Depends(_fake_user_id)],
) -> list[Pipeline]:
    """List all pipelines for a session."""
    session = await db.get(ResearchSession, session_id)
    if session is None or session.user_id != user_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")

    stmt = (
        select(Pipeline)
        .where(Pipeline.session_id == session_id)
        .order_by(Pipeline.created_at.desc())
    )
    result = await db.execute(stmt)
    return list(result.scalars().all())


# ── Read ─────────────────────────────────────────────────────────────

@router.get("/pipelines/{pipeline_id}", response_model=PipelineRead)
async def get_pipeline(
    pipeline_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    user_id: Annotated[uuid.UUID, Depends(_fake_user_id)],
) -> Pipeline:
    """Get a single pipeline by ID."""
    pipeline = await db.get(Pipeline, pipeline_id)
    if pipeline is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Pipeline not found")
    return pipeline


# ── Update ───────────────────────────────────────────────────────────

@router.patch("/pipelines/{pipeline_id}", response_model=PipelineRead)
async def update_pipeline(
    pipeline_id: uuid.UUID,
    body: PipelineUpdate,
    db: Annotated[AsyncSession, Depends(get_db)],
    user_id: Annotated[uuid.UUID, Depends(_fake_user_id)],
) -> Pipeline:
    """Partially update a pipeline."""
    pipeline = await db.get(Pipeline, pipeline_id)
    if pipeline is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Pipeline not found")

    update_data = body.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(pipeline, key, value)

    await db.flush()
    await db.refresh(pipeline)
    return pipeline


# ── Submit (transitions to 'submitted' and dispatches to Modal) ─────────


async def _dispatch_pipeline_to_modal(pipeline_id: uuid.UUID) -> None:
    """Create Run records for each step and dispatch them to Modal sandboxes.

    Runs as a background task — the API response returns immediately.
    All work is dispatched off to Modal; the VPS only tracks progress
    via the database and Redis pub/sub.
    """
    try:
        async with async_session_factory() as db:
            pipeline = await db.get(Pipeline, pipeline_id)
            if pipeline is None:
                logger.error("Pipeline %s not found for dispatch", pipeline_id)
                return

            dag = pipeline.dag_json or {}
            steps = dag.get("steps", []) if isinstance(dag, dict) else []
            if not steps:
                logger.warning("Pipeline %s has no steps to dispatch", pipeline_id)
                return

            # Create Run records (one per step)
            run_records: list[Run] = []
            for step in steps:
                step_id = step.get("step_id") or step.get("name") or "unknown"
                container_ref = step.get("container_image") or step.get("image")
                command_args = step.get("command_args", [])
                if isinstance(command_args, str):
                    command_args = [command_args]
                run = Run(
                    pipeline_id=pipeline_id,
                    step_name=step_id,
                    container_ref=container_ref,
                    command_args={"args": command_args} if command_args else None,
                    status="pending",
                    progress=0,
                )
                db.add(run)
                run_records.append(run)

            # Transition pipeline to 'running'
            pipeline.status = "running"
            await db.commit()
            for r in run_records:
                await db.refresh(r)

            logger.info(
                "Pipeline %s dispatched to Modal: %d runs created",
                pipeline_id, len(run_records),
            )

        # Dispatch each run to a Modal sandbox (concurrently, non-blocking)
        compute = ModalComputeService()
        for run in run_records:
            if not run.container_ref:
                logger.warning("Run %s has no container_ref, skipping", run.id)
                continue
            # Run the dispatch in the background — don't block the dispatch loop
            asyncio.create_task(
                compute.run_pipeline_step(
                    run_id=run.id,
                    container_ref=run.container_ref,
                    command_args=(run.command_args or {}).get("args", [])
                        if isinstance(run.command_args, dict) else [],
                    cpus=1,
                    memory_mb=4096,
                )
            )

    except Exception as exc:
        logger.exception("Failed to dispatch pipeline %s to Modal: %s", pipeline_id, exc)


@router.post("/pipelines/{pipeline_id}/submit", response_model=PipelineRead)
async def submit_pipeline(
    pipeline_id: uuid.UUID,
    background_tasks: BackgroundTasks,
    db: Annotated[AsyncSession, Depends(get_db)],
    user_id: Annotated[uuid.UUID, Depends(_fake_user_id)],
) -> Pipeline:
    """Submit a pipeline for execution.

    Transitions status from 'draft' to 'submitted' and creates one Run
    per DAG step. Run dispatch to Modal sandboxes happens asynchronously
    in the background so this endpoint returns immediately.
    """
    pipeline = await db.get(Pipeline, pipeline_id)
    if pipeline is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Pipeline not found")
    if pipeline.status not in ("draft", "submitted"):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Pipeline is in '{pipeline.status}' status; only 'draft' can be submitted",
        )

    pipeline.status = "submitted"
    await db.flush()
    await db.refresh(pipeline)

    # Dispatch to Modal in the background (non-blocking)
    background_tasks.add_task(_dispatch_pipeline_to_modal, pipeline_id)

    return pipeline