"""
FastAPI Application — Main entry point for local development.

Sets up CORS, includes auth & chat routers, and provides
health-check and root info endpoints.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from auth import auth_router
from file_upload import upload_router
from streaming import router as chat_router

# ── App instance ─────────────────────────────────────────────────────────────

app = FastAPI(
    title="E.sapiens v2 Agent API",
    description="Agentic bioinformatics backend with FastAPI + LangGraph + SSE streaming",
    version="0.2.0",
)

# ── CORS ──────────────────────────────────────────────────────────────────────
# Restrict origins to known frontend URLs. In production, set via
# the CORS_ORIGINS env var (comma-separated). Default: localhost only.
import os

_CORS_ORIGINS = os.environ.get(
    "CORS_ORIGINS",
    "http://localhost:5173,http://localhost:4173,http://localhost:3000",
).split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=_CORS_ORIGINS,
    allow_credentials=False,
    allow_methods=["GET", "POST", "DELETE"],
    allow_headers=["Content-Type", "Authorization"],
)

# ── Mount auth routes ────────────────────────────────────────────────────────

app.include_router(auth_router)

# ── Mount upload endpoint ────────────────────────────────────────────────

app.include_router(upload_router)

# ── Mount chat endpoints ──────────────────────────────────────────────────

app.include_router(chat_router)


# ── Health check ─────────────────────────────────────────────────────────────


@app.get("/health")
async def health_check() -> dict:
    """Health check endpoint."""
    return {"status": "healthy", "service": "esapiens-v2-agent"}


# ── Root endpoint ────────────────────────────────────────────────────────────


@app.get("/")
async def root() -> dict:
    """Root endpoint with API info."""
    return {
        "service": "E.sapiens v2 Agent",
        "version": "0.2.0",
        "description": "Agentic bioinformatics assistant with LangGraph ReAct loop + SSE streaming",
        "endpoints": {
            "POST /auth/register": "Register a new user",
            "POST /auth/login": "Login and receive a JWT token",
            "GET /auth/me": "Get current user profile (requires auth)",
            "POST /upload": "Upload a data file (CSV, TSV, JSON, XLSX) for analysis",
            "POST /chat": "Synchronous chat (blocking, requires auth)",
            "POST /chat/stream": "Streaming chat (SSE, requires auth)",
            "GET /sessions": "List active sessions (requires auth)",
            "GET /sessions/{id}": "Get session messages (requires auth)",
            "DELETE /sessions/{id}": "Delete a session (requires auth)",
            "GET /chat/report/{session_id}": "Generate PDF report (requires auth)",
            "GET /health": "Health check",
            "GET /": "API info",
        },
    }