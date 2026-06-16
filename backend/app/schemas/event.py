"""Pydantic v2 schemas for SSE events — discriminated union model."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Annotated, Any, Literal, Union

from pydantic import BaseModel, Field, Tag


# ── Individual event payloads ─────────────────────────────────────────

class AgentPlanGenerated(BaseModel):
    """Agent has produced a pipeline plan."""

    event_type: Literal["AGENT_PLAN_GENERATED"] = "AGENT_PLAN_GENERATED"
    session_id: uuid.UUID
    plan: dict[str, Any]


class RunStepLog(BaseModel):
    """Log output from a running step."""

    event_type: Literal["RUN_STEP_LOG"] = "RUN_STEP_LOG"
    run_id: uuid.UUID
    step_name: str
    stream: Literal["stdout", "stderr"] = "stdout"
    text: str


class MetricsUpdated(BaseModel):
    """Resource or cost metrics have been updated."""

    event_type: Literal["METRICS_UPDATED"] = "METRICS_UPDATED"
    session_id: uuid.UUID
    metrics: dict[str, Any]


class PipelineStatusChanged(BaseModel):
    """Pipeline has transitioned to a new status."""

    event_type: Literal["PIPELINE_STATUS_CHANGED"] = "PIPELINE_STATUS_CHANGED"
    pipeline_id: uuid.UUID
    old_status: str
    new_status: str


# ── Discriminated union ──────────────────────────────────────────────

ServerEvent = Annotated[
    Union[
        AgentPlanGenerated,
        RunStepLog,
        MetricsUpdated,
        PipelineStatusChanged,
    ],
    Field(discriminator="event_type"),
]


class EventEnvelope(BaseModel):
    """Envelope wrapping a server-sent event with metadata."""

    id: int
    session_id: uuid.UUID
    event: ServerEvent
    created_at: datetime