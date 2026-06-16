"""Pydantic v2 schemas for Run."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class RunCreate(BaseModel):
    """Payload for creating a run (typically internal — runs are spawned by the system)."""

    pipeline_id: uuid.UUID
    step_name: str = Field(..., min_length=1, max_length=256)
    container_ref: str | None = None
    command_args: dict[str, Any] | None = None


class RunUpdate(BaseModel):
    """Partial update for a run."""

    status: str | None = Field(None, pattern="^(pending|running|completed|failed)$")
    exit_code: int | None = None
    modal_sandbox_id: str | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
    stdout_log: str | None = None
    stderr_log: str | None = None


class RunRead(BaseModel):
    """Read model returned to the client."""

    id: uuid.UUID
    pipeline_id: uuid.UUID
    step_name: str
    container_ref: str | None
    command_args: dict[str, Any] | None
    status: str
    exit_code: int | None
    modal_sandbox_id: str | None
    started_at: datetime | None
    completed_at: datetime | None
    created_at: datetime

    model_config = {"from_attributes": True}


class RunLogChunk(BaseModel):
    """Streaming log chunk for a run."""

    run_id: uuid.UUID
    stream: str = Field(..., pattern="^(stdout|stderr)$")
    offset: int = Field(..., ge=0)
    text: str