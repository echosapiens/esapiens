"""Pydantic v2 schemas for Grant (funding / budget tracking)."""

from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field


class GrantCreate(BaseModel):
    """Payload for creating a new grant."""

    name: str = Field(..., min_length=1, max_length=256)
    institution: str | None = None
    total_budget: Decimal = Field(..., gt=0)
    currency: str | None = Field(None, max_length=3)


class GrantUpdate(BaseModel):
    """Partial update for a grant."""

    name: str | None = Field(None, min_length=1, max_length=256)
    institution: str | None = None
    total_budget: Decimal | None = Field(None, gt=0)
    status: str | None = Field(None, pattern="^(active|exhausted|expired)$")


class GrantRead(BaseModel):
    """Read model returned to the client."""

    id: uuid.UUID
    user_id: uuid.UUID
    name: str
    institution: str | None
    total_budget: Decimal
    spent_budget: Decimal
    currency: str
    status: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class GrantBalance(BaseModel):
    """Remaining budget for a grant."""

    grant_id: uuid.UUID
    total_budget: Decimal
    spent_budget: Decimal
    remaining_budget: Decimal
    currency: str