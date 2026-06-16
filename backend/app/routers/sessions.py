"""Sessions router — CRUD for research sessions."""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.session import ResearchSession
from app.schemas.session import SessionCreate, SessionRead, SessionUpdate

router = APIRouter(prefix="/sessions", tags=["sessions"])

# Placeholder user dependency — replace with real auth
async def _fake_user_id() -> uuid.UUID:
    return uuid.UUID("00000000-0000-0000-0000-000000000001")


# ── Create ───────────────────────────────────────────────────────────

@router.post("/", response_model=SessionRead, status_code=status.HTTP_201_CREATED)
async def create_session(
    body: SessionCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    user_id: Annotated[uuid.UUID, Depends(_fake_user_id)],
) -> ResearchSession:
    """Create a new research session."""
    session = ResearchSession(title=body.title, user_id=user_id, status="active")
    db.add(session)
    await db.flush()
    await db.refresh(session)
    return session


# ── List ─────────────────────────────────────────────────────────────

@router.get("/", response_model=list[SessionRead])
async def list_sessions(
    db: Annotated[AsyncSession, Depends(get_db)],
    user_id: Annotated[uuid.UUID, Depends(_fake_user_id)],
) -> list[ResearchSession]:
    """List all active sessions for the current user."""
    stmt = (
        select(ResearchSession)
        .where(ResearchSession.user_id == user_id, ResearchSession.status != "deleted")
        .order_by(ResearchSession.created_at.desc())
    )
    result = await db.execute(stmt)
    return list(result.scalars().all())


# ── Read ─────────────────────────────────────────────────────────────

@router.get("/{session_id}", response_model=SessionRead)
async def get_session(
    session_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    user_id: Annotated[uuid.UUID, Depends(_fake_user_id)],
) -> ResearchSession:
    """Get a single session by ID."""
    session = await db.get(ResearchSession, session_id)
    if session is None or session.user_id != user_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")
    return session


# ── Update ───────────────────────────────────────────────────────────

@router.patch("/{session_id}", response_model=SessionRead)
async def update_session(
    session_id: uuid.UUID,
    body: SessionUpdate,
    db: Annotated[AsyncSession, Depends(get_db)],
    user_id: Annotated[uuid.UUID, Depends(_fake_user_id)],
) -> ResearchSession:
    """Partially update a session."""
    session = await db.get(ResearchSession, session_id)
    if session is None or session.user_id != user_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")

    update_data = body.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(session, key, value)

    await db.flush()
    await db.refresh(session)
    return session


# ── Delete (soft) ────────────────────────────────────────────────────

@router.delete("/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_session(
    session_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    user_id: Annotated[uuid.UUID, Depends(_fake_user_id)],
) -> None:
    """Soft-delete a session (sets status to 'deleted')."""
    session = await db.get(ResearchSession, session_id)
    if session is None or session.user_id != user_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")

    session.status = "deleted"
    await db.flush()