"""FastAPI application factory — assembles the full E.sapiens backend."""

from __future__ import annotations

import logging
import warnings
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.database import engine, Base, async_session_factory
from sqlalchemy import text as _text
from app.middleware.redaction import SequenceHeaderRedactionMiddleware
from app.services.reconciler import Reconciler
from app.services import biocontainers as _biocontainers
from app.workers.outbox_relay import OutboxRelay

logger = logging.getLogger(__name__)

# Suppress Pydantic serializer warnings for LangChain structured output
warnings.filterwarnings("ignore", message="Pydantic serializer warnings", category=UserWarning)

# ── Dev user ID (matches _fake_user_id in routers) ──────────────────────
import uuid as _uuid
_DEV_USER_ID = _uuid.UUID("00000000-0000-0000-0000-000000000001")

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

    # Backfill seq_id for existing events and set the sequence start value.
    # Needed because seq_id was previously autoincrement (only works on PK)
    # which left existing rows with NULL, violating the NOT NULL constraint.
    async with engine.begin() as conn:
        # Set seq_id = id for any rows that still have NULL seq_id
        result = await conn.execute(
            _text("UPDATE events SET seq_id = id WHERE seq_id IS NULL")
        )
        if result.rowcount > 0:
            logger.info("Backfilled %d event seq_id values", result.rowcount)

        # Set the sequence start above the current max seq_id
        max_seq = await conn.execute(_text("SELECT COALESCE(MAX(seq_id), 0) FROM events"))
        max_val = max_seq.scalar() or 0
        await conn.execute(
            _text(f"ALTER SEQUENCE event_seq RESTART WITH {max_val + 1}")
        )
        logger.info("Event sequence restart at %d", max_val + 1)

    # Seed default dev user so FK constraints are satisfied for stub auth
    from app.models.user import User
    from sqlalchemy import select as _sel
    async with async_session_factory() as session:
        existing = (await session.execute(
            _sel(User).where(User.id == _DEV_USER_ID)
        )).scalar_one_or_none()
        if existing is None:
            session.add(User(
                id=_DEV_USER_ID,
                email="dev@esapiens.local",
            ))
            await session.commit()
            logger.info("Seeded default dev user %s", _DEV_USER_ID)

    logger.info("Starting outbox relay…")
    await _relay.start()

    logger.info("Starting background reconciler…")
    await _reconciler.start_background_reconciler()

    logger.info("Initializing BioContainers registry…")
    await _biocontainers.initialize()

    yield

    # ── Shutdown ─────────────────────────────────────────────────
    logger.info("Shutting down BioContainers registry…")
    await _biocontainers.shutdown()

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
    from app.routers import auth, sessions, pipelines, runs, grants, ws, sse, chat

    app.include_router(auth.router)
    app.include_router(sessions.router)
    app.include_router(pipelines.router)
    app.include_router(runs.router)
    app.include_router(grants.router)
    app.include_router(chat.router)
    app.include_router(ws.router)
    app.include_router(sse.router)

    # ── Health ────────────────────────────────────────────────────
    @app.get("/health", tags=["health"])
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    return app


# ── Module-level app instance (used by uvicorn) ──────────────────────────
app = create_app()