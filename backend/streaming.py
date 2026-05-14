"""
Streaming & Sync Chat Endpoints — SSE streaming via sse-starlette.

Provides:
  POST /chat            — synchronous chat
  POST /chat/stream     — SSE streaming chat
  GET  /sessions        — list sessions
  GET  /sessions/{id}   — get session messages
  DELETE /sessions/{id} — delete session
"""

import json
from typing import Any, AsyncGenerator

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sse_starlette.sse import EventSourceResponse

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


class ChatResponse(BaseModel):
    response: str
    session_id: str
    skills: list[str] = []
    tool_calls: list[dict[str, Any]] = []
    error: str | None = None


# ── Sync endpoint ────────────────────────────────────────────────────────────


@router.post("/chat", response_model=ChatResponse)
async def chat_sync(req: ChatRequest) -> dict[str, Any]:
    """
    Synchronous chat endpoint.
    Returns the full response after the agent finishes.
    """
    result = run(query=req.query, session_id=req.session_id)
    return ChatResponse(**result).model_dump()


# ── Streaming endpoint ───────────────────────────────────────────────────────


@router.post("/chat/stream")
async def chat_stream(req: ChatRequest) -> StreamingResponse:
    """
    Streaming chat endpoint using Server-Sent Events.

    Event types:
      skills_loaded — list of matched skill paths
      tool_call     — tool being executed
      tool_result   — result of a tool execution
      chunk         — text token from the LLM
      done          — final response payload
      error         — error message
    """

    async def event_generator() -> AsyncGenerator[dict, None]:
        for event in run_stream(query=req.query, session_id=req.session_id):
            yield event

    return EventSourceResponse(event_generator())


# ── Session management endpoints ─────────────────────────────────────────────


@router.get("/sessions")
async def sessions_list() -> list[dict[str, Any]]:
    """List all active sessions."""
    return list_sessions()


@router.get("/sessions/{session_id}")
async def sessions_get(session_id: str) -> dict[str, Any]:
    """Get full session data including messages."""
    session = get_session(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")
    return session


@router.delete("/sessions/{session_id}")
async def sessions_delete(session_id: str) -> dict[str, str]:
    """Delete a session."""
    if not delete_session(session_id):
        raise HTTPException(status_code=404, detail="Session not found")
    return {"status": "deleted", "session_id": session_id}


# ── Report generation ─────────────────────────────────────────────────────


@router.get("/chat/report/{session_id}")
async def generate_report(session_id: str):
    """
    Generate a PDF report for a session and return it as a file download.
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