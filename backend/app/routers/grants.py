"""Grants router — CRUD and balance for research funding / budget tracking."""

from __future__ import annotations

import uuid
from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.grant import Grant
from app.schemas.grant import GrantCreate, GrantRead, GrantUpdate, GrantBalance

router = APIRouter(prefix="/grants", tags=["grants"])

# Placeholder user dependency
async def _fake_user_id() -> uuid.UUID:
    return uuid.UUID("00000000-0000-0000-0000-000000000001")


# ── Create ───────────────────────────────────────────────────────────

@router.post("", response_model=GrantRead, status_code=status.HTTP_201_CREATED)
async def create_grant(
    body: GrantCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
    user_id: Annotated[uuid.UUID, Depends(_fake_user_id)],
) -> Grant:
    """Create a new grant."""
    grant = Grant(
        user_id=user_id,
        name=body.name,
        institution=body.institution,
        total_budget=body.total_budget,
        spent_budget=Decimal("0.00"),
        currency=body.currency or "USD",
        status="active",
    )
    db.add(grant)
    await db.flush()
    await db.refresh(grant)
    return grant


# ── List ─────────────────────────────────────────────────────────────

@router.get("", response_model=list[GrantRead])
async def list_grants(
    db: Annotated[AsyncSession, Depends(get_db)],
    user_id: Annotated[uuid.UUID, Depends(_fake_user_id)],
) -> list[Grant]:
    """List all grants for the current user."""
    stmt = (
        select(Grant)
        .where(Grant.user_id == user_id)
        .order_by(Grant.created_at.desc())
    )
    result = await db.execute(stmt)
    return list(result.scalars().all())


# ── Read ─────────────────────────────────────────────────────────────

@router.get("/{grant_id}", response_model=GrantRead)
async def get_grant(
    grant_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    user_id: Annotated[uuid.UUID, Depends(_fake_user_id)],
) -> Grant:
    """Get a single grant by ID."""
    grant = await db.get(Grant, grant_id)
    if grant is None or grant.user_id != user_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Grant not found")
    return grant


# ── Balance ──────────────────────────────────────────────────────────

@router.get("/{grant_id}/balance", response_model=GrantBalance)
async def get_grant_balance(
    grant_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    user_id: Annotated[uuid.UUID, Depends(_fake_user_id)],
) -> GrantBalance:
    """Get the remaining budget for a grant."""
    grant = await db.get(Grant, grant_id)
    if grant is None or grant.user_id != user_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Grant not found")

    remaining = grant.total_budget - grant.spent_budget
    return GrantBalance(
        grant_id=grant.id,
        total_budget=grant.total_budget,
        spent_budget=grant.spent_budget,
        remaining_budget=remaining,
        currency=grant.currency,
    )


# ── Update ───────────────────────────────────────────────────────────

@router.patch("/{grant_id}", response_model=GrantRead)
async def update_grant(
    grant_id: uuid.UUID,
    body: GrantUpdate,
    db: Annotated[AsyncSession, Depends(get_db)],
    user_id: Annotated[uuid.UUID, Depends(_fake_user_id)],
) -> Grant:
    """Partially update a grant."""
    grant = await db.get(Grant, grant_id)
    if grant is None or grant.user_id != user_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Grant not found")

    update_data = body.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(grant, key, value)

    await db.flush()
    await db.refresh(grant)
    return grant