"""
FastAPI Application — Main entry point for local development.

Sets up CORS, includes chat & session routers, and provides
health-check and root info endpoints.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

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

# ── Mount chat endpoints ────────────────────────────────────────────────────

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
            "POST /chat": "Synchronous chat (blocking)",
            "POST /chat/stream": "Streaming chat (SSE)",
            "GET /sessions": "List active sessions",
            "GET /sessions/{id}": "Get session messages",
            "DELETE /sessions/{id}": "Delete a session",
            "GET /health": "Health check",
            "GET /": "API info",
        },
    }