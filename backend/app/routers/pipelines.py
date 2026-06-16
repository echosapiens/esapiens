"""Pipelines router — CRUD + submit for pipeline resources."""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.pipeline import Pipeline
from app.models.session import ResearchSession
from app.schemas.pipeline import PipelineCreate, PipelineRead, PipelineUpdate

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


# ── Submit ───────────────────────────────────────────────────────────

@router.post("/pipelines/{pipeline_id}/submit", response_model=PipelineRead)
async def submit_pipeline(
    pipeline_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    user_id: Annotated[uuid.UUID, Depends(_fake_user_id)],
) -> Pipeline:
    """Transition a pipeline from 'draft' to 'submitted' status."""
    pipeline = await db.get(Pipeline, pipeline_id)
    if pipeline is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Pipeline not found")
    if pipeline.status != "draft":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Pipeline is in '{pipeline.status}' status; only 'draft' can be submitted",
        )

    pipeline.status = "submitted"
    await db.flush()
    await db.refresh(pipeline)
    return pipeline