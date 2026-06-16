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


# ── Direct code execution (live Modal sandbox) ─────────────────────────


class CodeExecutionRequest(BaseModel):
    """Direct code execution request — no LLM in the loop."""

    code: str = Field(..., min_length=1, max_length=100_000)
    language: str = Field(default="python", pattern="^(python|r|bash)$")
    timeout: float = Field(default=30.0, ge=1.0, le=300.0)


@router.post("/{session_id}/execute", response_model=dict)
async def execute_code(
    session_id: uuid.UUID,
    body: CodeExecutionRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    user_id: Annotated[uuid.UUID, Depends(_fake_user_id)],
) -> dict:
    """Execute code in a real Modal sandbox.

    Returns the actual stdout, stderr, exit code, files produced, and
    execution duration. This is a real execution environment — not a
    prediction.
    """
    session = await db.get(ResearchSession, session_id)
    if session is None or session.user_id != user_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found",
        )

    from app.services.code_sandbox import get_code_sandbox

    sandbox = get_code_sandbox()
    result = await sandbox.execute(
        code=body.code,
        language=body.language,  # type: ignore[arg-type]
        timeout=body.timeout,
        session_id=session_id,
    )
    return result.model_dump()


# ── Async job dispatch (chat agent fires job, continues conversation) ──


class AsyncDispatchRequest(BaseModel):
    """Request to dispatch a long-running code job to Modal.

    The chat agent uses this when the user wants to run a heavy
    computation. The endpoint returns immediately with a job_id — the
    job runs in a background task and progress is reported via WebSocket
    events (JOB_QUEUED, JOB_STARTED, JOB_PROGRESS, JOB_COMPLETED).
    """

    prompt: str = Field(..., min_length=1, max_length=4096, description="Original user prompt")
    code: str = Field(..., min_length=1, max_length=100_000)
    language: str = Field(default="python", pattern="^(python|r|bash)$")
    timeout: float = Field(default=120.0, ge=5.0, le=600.0)


class AsyncDispatchResponse(BaseModel):
    """Response after dispatching an async job."""

    job_id: str
    status: str
    message: str = "Job dispatched. Continue chatting — I'll send progress updates."


class JobStatusResponse(BaseModel):
    """Status of a dispatched async job."""

    job_id: str
    session_id: str
    prompt: str
    code: str
    language: str
    status: str
    progress: int
    exit_code: int | None = None
    stdout: str = ""
    stderr: str = ""
    files_produced: list[str] = Field(default_factory=list)
    error: str | None = None
    created_at: str
    completed_at: str | None = None


@router.post("/{session_id}/dispatch-job", response_model=AsyncDispatchResponse)
async def dispatch_async_job(
    session_id: uuid.UUID,
    body: AsyncDispatchRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    user_id: Annotated[uuid.UUID, Depends(_fake_user_id)],
) -> AsyncDispatchResponse:
    """Dispatch a code-execution job to Modal in the background.

    Returns immediately with a job_id. The chat agent can continue
    serving the user while the job runs. Progress is delivered via
    WebSocket events on the session channel. When the job completes,
    the agent can synthesize a final report from the results.
    """
    session = await db.get(ResearchSession, session_id)
    if session is None or session.user_id != user_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found",
        )

    from app.services.async_jobs import get_job_manager

    mgr = get_job_manager()
    job = await mgr.dispatch(
        session_id=session_id,
        user_id=user_id,
        prompt=body.prompt,
        code=body.code,
        language=body.language,
        timeout=body.timeout,
    )
    return AsyncDispatchResponse(
        job_id=job.job_id,
        status=job.status.value,
    )


@router.get("/{session_id}/jobs/{job_id}", response_model=JobStatusResponse)
async def get_job_status(
    session_id: uuid.UUID,
    job_id: str,
    db: Annotated[AsyncSession, Depends(get_db)],
    user_id: Annotated[uuid.UUID, Depends(_fake_user_id)],
) -> JobStatusResponse:
    """Get the current status of an async job (for polling or final-report synthesis)."""
    session = await db.get(ResearchSession, session_id)
    if session is None or session.user_id != user_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found",
        )

    from app.services.async_jobs import get_job_manager

    mgr = get_job_manager()
    job = await mgr.get_job(job_id)
    if job is None or job.session_id != str(session_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Job not found",
        )

    result = job.result
    return JobStatusResponse(
        job_id=job.job_id,
        session_id=job.session_id,
        prompt=job.prompt,
        code=job.code,
        language=job.language,
        status=job.status.value,
        progress=job.progress,
        exit_code=result.exit_code if result else None,
        stdout=result.stdout if result else "",
        stderr=result.stderr if result else "",
        files_produced=result.files_produced if result else [],
        error=result.error if result else None,
        created_at=job.created_at,
        completed_at=result.completed_at if result else None,
    )