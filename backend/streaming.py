"""
Streaming & Sync Chat Endpoints — SSE streaming via sse-starlette.

Provides:
  POST /chat            — synchronous chat
  POST /chat/stream     — SSE streaming chat
  GET  /sessions        — list sessions
  GET  /sessions/{id}   — get session messages
  DELETE /sessions/{id} — delete session
  GET  /chat/report/{id} — generate PDF report

All endpoints require authentication via Depends(get_current_user).
"""

import json
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sse_starlette.sse import EventSourceResponse

from auth import get_current_user
from main import (
    delete_session,
    get_session,
    list_sessions,
    run,
    run_stream,
)

router = APIRouter(tags=["chat"])


# ── Request / response schemas ───────────────────────────────────────────────


class ChatRequest(BaseModel):
    query: str = Field(..., max_length=10000, description="User query (max 10,000 characters)")
    session_id: str = Field("default", max_length=128, pattern=r"^[a-zA-Z0-9_-]+$")
    file_context: str | None = Field(
        None,
        max_length=50000,
        description="Parsed data summary from an uploaded file, prepended to the query for agent context",
    )

class ChatResponse(BaseModel):
    response: str
    session_id: str
    skills: list[str] = []
    tool_calls: list[dict[str, Any]] = []
    error: str | None = None

# ── Sync endpoint ────────────────────────────────────────────────────────────


@router.post("/chat", response_model=ChatResponse)
async def chat_sync(
    req: ChatRequest,
    current_user: dict = Depends(get_current_user),
) -> dict[str, Any]:
    """
    Synchronous chat endpoint (requires auth).
    Returns the full response after the agent finishes.
    """
    # Prepend file context if provided
    query = req.query
    if req.file_context:
        query = f"{req.file_context}\n\n{query}"

    result = run(query=query, session_id=req.session_id, user_id=current_user["id"])
    return ChatResponse(**result).model_dump()


# ── Streaming endpoint ───────────────────────────────────────────────────────


@router.post("/chat/stream")
async def chat_stream(
    req: ChatRequest,
    current_user: dict = Depends(get_current_user),
) -> StreamingResponse:
    """
    Streaming chat endpoint using Server-Sent Events (requires auth).

    Event types:
      skills_loaded — list of matched skill paths
      tool_call     — tool being executed
      tool_result   — result of a tool execution
      chunk         — text token from the LLM
      done          — final response payload
      error         — error message
    """
    # Prepend file context if provided
    query = req.query
    if req.file_context:
        query = f"{req.file_context}\n\n{query}"

    # sse-starlette runs sync generators in a thread pool via
    # iterate_in_threadpool, so we can pass run_stream directly.
    # We use a generator expression to inject the user_id.
    def _stream():
        yield from run_stream(query=query, session_id=req.session_id, user_id=current_user["id"])

    return EventSourceResponse(_stream())


# ── Session management endpoints ─────────────────────────────────────────────


@router.get("/sessions")
async def sessions_list(
    current_user: dict = Depends(get_current_user),
) -> list[dict[str, Any]]:
    """List all active sessions for the authenticated user."""
    return list_sessions(user_id=current_user["id"])


@router.get("/sessions/{session_id}")
async def sessions_get(
    session_id: str,
    current_user: dict = Depends(get_current_user),
) -> dict[str, Any]:
    """Get full session data including messages (requires auth)."""
    session = get_session(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")
    return session


@router.delete("/sessions/{session_id}")
async def sessions_delete(
    session_id: str,
    current_user: dict = Depends(get_current_user),
) -> dict[str, str]:
    """Delete a session (requires auth)."""
    if not delete_session(session_id):
        raise HTTPException(status_code=404, detail="Session not found")
    return {"status": "deleted", "session_id": session_id}


# ── Job monitor endpoints ────────────────────────────────────────────────


@router.get("/jobs")
async def jobs_list(
    status: str | None = None,
    current_user: dict = Depends(get_current_user),
) -> list[dict[str, Any]]:
    """
    List background jobs, optionally filtered by status.
    Returns job_id, tool, name, status, start_time, end_time, error.
    """
    from storage import get_storage
    return get_storage().list_jobs(status=status, limit=100)


@router.get("/jobs/{job_id}")
async def jobs_get(
    job_id: str,
    current_user: dict = Depends(get_current_user),
) -> dict[str, Any]:
    """Get full details of a single background job."""
    from storage import get_storage
    record = get_storage().get_job(job_id)
    if record is None:
        raise HTTPException(status_code=404, detail=f"Job '{job_id}' not found")
    return record


# ── Report generation ─────────────────────────────────────────────────────


@router.get("/chat/report/{session_id}")
async def generate_report(
    session_id: str,
    current_user: dict = Depends(get_current_user),
):
    """
    Generate a PDF report for a session and return it as a file download (requires auth).
    """
    from main import get_session as gs
    from report import generate_session_report
    from fastapi.responses import Response

    session = gs(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")

    pdf_bytes = generate_session_report(session)

    title = session.get("title", "session_report").replace(" ", "_")
    safe_title = "".join(c if c.isalnum() or c in "_-" else "_" for c in title)

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="esapiens_{safe_title}.pdf"',
            "Content-Length": str(len(pdf_bytes)),
        },
    )