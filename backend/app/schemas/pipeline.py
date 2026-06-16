"""Pydantic v2 schemas for Pipeline and DAG steps."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class DAGStepRead(BaseModel):
    """A single step inside a pipeline DAG."""

    step_name: str
    container_image: str
    command_args: list[str] = []
    depends_on: list[str] = Field(default_factory=list)

    model_config = {"from_attributes": True}


class PipelineCreate(BaseModel):
    """Payload for creating a new pipeline."""

    name: str = Field(..., min_length=1, max_length=256)
    description: str | None = None
    dag_json: dict[str, Any] = Field(..., description="DAG definition with steps and dependencies")


class PipelineUpdate(BaseModel):
    """Partial update for a pipeline."""

    name: str | None = Field(None, min_length=1, max_length=256)
    description: str | None = None
    dag_json: dict[str, Any] | None = None
    status: str | None = Field(None, pattern="^(draft|submitted|running|completed|failed)$")


class PipelineRead(BaseModel):
    """Read model returned to the client."""

    id: uuid.UUID
    session_id: uuid.UUID
    name: str
    description: str | None
    dag_json: dict[str, Any]
    status: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}