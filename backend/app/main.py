"""FastAPI application factory — assembles the full E.sapiens backend."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.database import engine, Base
from app.middleware.redaction import SequenceHeaderRedactionMiddleware
from app.services.reconciler import Reconciler
from app.workers.outbox_relay import OutboxRelay

logger = logging.getLogger(__name__)

# ── Singletons ────────────────────────────────────────────────────────────
_relay = OutboxRelay()
_reconciler = Reconciler()


# ── Lifespan ─────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Startup/shutdown lifecycle handler."""
    # ── Startup ──────────────────────────────────────────────────
    logger.info("Creating database tables (if not present)…")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    logger.info("Starting outbox relay…")
    await _relay.start()

    logger.info("Starting background reconciler…")
    await _reconciler.start_background_reconciler()

    yield

    # ── Shutdown ─────────────────────────────────────────────────
    logger.info("Stopping background reconciler…")
    await _reconciler.stop_background_reconciler()

    logger.info("Stopping outbox relay…")
    await _relay.stop()
    await engine.dispose()


# ── App factory ──────────────────────────────────────────────────────────

def create_app() -> FastAPI:
    """Build and configure the FastAPI application."""
    app = FastAPI(
        title="E.sapiens API",
        version="0.1.0",
        description="Bioinformatics SaaS platform — compute, data, and agent orchestration",
        lifespan=lifespan,
        redirect_slashes=False,
    )

    # ── Middleware ────────────────────────────────────────────────
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.add_middleware(SequenceHeaderRedactionMiddleware)

    # ── Routers ───────────────────────────────────────────────────
    from app.routers import auth, sessions, pipelines, runs, grants, ws, sse

    app.include_router(auth.router)
    app.include_router(sessions.router)
    app.include_router(pipelines.router)
    app.include_router(runs.router)
    app.include_router(grants.router)
    app.include_router(ws.router)
    app.include_router(sse.router)

    # ── Health ────────────────────────────────────────────────────
    @app.get("/health", tags=["health"])
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    return app


# ── Module-level app instance (used by uvicorn) ──────────────────────────
app = create_app()