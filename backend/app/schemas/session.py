"""Pydantic v2 schemas for ResearchSession."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, Field, model_validator


class SessionCreate(BaseModel):
    """Payload for creating a new research session."""

    title: str = Field(..., min_length=1, max_length=256)


class SessionUpdate(BaseModel):
    """Partial update for a research session."""

    title: str | None = Field(None, min_length=1, max_length=256)
    status: str | None = Field(None, pattern="^(active|archived|deleted)$")


class SessionRead(BaseModel):
    """Read model returned to the client."""

    id: uuid.UUID
    title: str
    user_id: uuid.UUID
    status: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}