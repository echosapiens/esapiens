"""Chat router — send prompts to the agent and receive pipeline plans."""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.session import ResearchSession
from app.models.pipeline import Pipeline
from app.services.agent import AgentService
from app.services.subagents import SubagentResult
from app.services.supervisor import SupervisorService

router = APIRouter(prefix="/sessions", tags=["chat"])


# ── Schemas ────────────────────────────────────────────────────────────

class ChatRequest(BaseModel):
    """User prompt sent to the agent."""
    prompt: str = Field(..., min_length=1, max_length=4096)
    grant_id: uuid.UUID | None = None


class ChatResponse(BaseModel):
    """Agent response after planning a pipeline."""
    pipeline_id: str
    title: str
    description: str
    steps: list[dict]
    estimated_cost: float
    status: str
    message: str


# ── Placeholder user ───────────────────────────────────────────────────

async def _fake_user_id() -> uuid.UUID:
    return uuid.UUID("00000000-0000-0000-0000-000000000001")


# ── Chat endpoint ──────────────────────────────────────────────────────

@router.post("/{session_id}/chat", response_model=ChatResponse)
async def chat_with_agent(
    session_id: uuid.UUID,
    body: ChatRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    user_id: Annotated[uuid.UUID, Depends(_fake_user_id)],
) -> ChatResponse:
    """Send a natural-language prompt to the agent and receive a pipeline plan.

    The agent runs the Plan-and-Execute graph (PLANNER → CONSTRUCTOR → CRITIC
    → HITL_GATE) and pauses for human approval. Returns the pipeline plan
    details so the frontend can render the Pipeline tab.
    """
    # Verify session exists and belongs to user
    session = await db.get(ResearchSession, session_id)
    if session is None or session.user_id != user_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found",
        )

    # Run the agent graph
    svc = AgentService()
    try:
        pipeline_id, agent_state = await svc.start_pipeline(
            prompt=body.prompt,
            session_id=session_id,
            user_id=user_id,
            grant_id=body.grant_id,
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Agent planning failed: {exc}",
        )

    # ── No plan generated — conversational response ───────────────
    if pipeline_id is None:
        # The agent returned a conversational message without a pipeline
        msg = "I'm ready to help you plan a bioinformatics pipeline."
        if agent_state.messages:
            last_msg = agent_state.messages[-1]
            if isinstance(last_msg, dict):
                msg = last_msg.get("content", msg)
            else:
                msg = str(last_msg)
        return ChatResponse(
            pipeline_id="",
            title="",
            description="",
            steps=[],
            estimated_cost=0.0,
            status="conversational",
            message=msg,
        )

    # Fetch the persisted pipeline to get full details
    pipeline = await db.get(Pipeline, pipeline_id)
    if pipeline is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Pipeline {pipeline_id} not found after planning",
        )

    # Build response
    plan = agent_state.current_plan
    steps = []
    if plan:
        steps = [
            {
                "step_id": s.step_id,
                "tool_name": s.tool_name,
                "description": s.description,
                "inputs": s.inputs,
                "outputs": s.outputs,
                "depends_on": s.depends_on,
                "estimated_cpu": s.estimated_cpu,
                "estimated_memory_mb": s.estimated_memory_mb,
            }
            for s in plan.steps
        ]

    estimated_cost = 0.0
    if agent_state.critic_result:
        estimated_cost = agent_state.critic_result.estimated_cost

    return ChatResponse(
        pipeline_id=str(pipeline_id),
        title=plan.title if plan else pipeline.name,
        description=plan.description if plan else (pipeline.description or ""),
        steps=steps,
        estimated_cost=estimated_cost,
        status=pipeline.status,
        message=f"Generated {len(steps)} step(s): {plan.title if plan else pipeline.name}",
    )


# ── Supervisor endpoint (multi-agent hub-and-spoke) ─────────────────────


class SupervisorChatRequest(BaseModel):
    """User prompt for the Supervisor multi-agent system."""

    prompt: str = Field(..., min_length=1, max_length=4096)
    grant_id: uuid.UUID | None = None


class SubagentSummary(BaseModel):
    """Summary of a single subagent's contribution."""

    role: str
    task: str
    findings: str
    confidence: float
    structured_data: dict = Field(default_factory=dict)
    citations: list[str] = Field(default_factory=list)


class SupervisorChatResponse(BaseModel):
    """Response from the Supervisor multi-agent system."""

    answer: str = Field(..., description="Synthesized final answer")
    subagent_results: list[SubagentSummary] = Field(default_factory=list)
    iterations: int = 0
    phase: str = "done"


@router.post("/{session_id}/chat/supervisor", response_model=SupervisorChatResponse)
async def chat_with_supervisor(
    session_id: uuid.UUID,
    body: SupervisorChatRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    user_id: Annotated[uuid.UUID, Depends(_fake_user_id)],
) -> SupervisorChatResponse:
    """Send a prompt to the Supervisor multi-agent system.

    The Supervisor reflects on the question and delegates to specialized
    subagents (biology, math, code, literature) as needed. Workers do not
    communicate with each other — the Supervisor is the sole coordinator.
    """
    # Verify session exists
    session = await db.get(ResearchSession, session_id)
    if session is None or session.user_id != user_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found",
        )

    svc = SupervisorService()
    try:
        final_state = await svc.run(
            prompt=body.prompt,
            session_id=session_id,
            user_id=user_id,
            grant_id=body.grant_id,
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Supervisor failed: {exc}",
        )

    return SupervisorChatResponse(
        answer=final_state.final_answer or "I could not generate a response.",
        subagent_results=[
            SubagentSummary(
                role=r.role.value,
                task=r.task,
                findings=r.findings,
                confidence=r.confidence,
                structured_data=r.structured_data,
                citations=r.citations,
            )
            for r in final_state.subagent_results
        ],
        iterations=final_state.iteration,
        phase=final_state.phase.value,
    )