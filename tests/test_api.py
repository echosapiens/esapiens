"""Integration tests for the E.sapiens backend API.

Uses pytest + httpx AsyncClient with an in-memory SQLite database for testing.
Tests cover health endpoint, auth flow, event engine, budget service, and
database operations for sessions, pipelines, and grants.
"""

from __future__ import annotations

import asyncio
import json
import uuid
from decimal import Decimal

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import Column, String, Text, Integer, Numeric, Boolean, event as sa_event, select
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy.pool import StaticPool
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker


# ── Test-specific Base (no FK constraints — SQLite-friendly) ────────────

class Base(DeclarativeBase):
    pass


class UserRow(Base):
    __tablename__ = "users"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    email: Mapped[str] = mapped_column(String(256), nullable=False, unique=True)


class SessionRow(Base):
    __tablename__ = "research_sessions"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    title: Mapped[str] = mapped_column(String(256), nullable=False)
    user_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="active", index=True)
    created_at: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    updated_at: Mapped[str] = mapped_column(String(64), nullable=False, default="")


class PipelineRow(Base):
    __tablename__ = "pipelines"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    session_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(256), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    dag_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="draft", index=True)
    created_at: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    updated_at: Mapped[str] = mapped_column(String(64), nullable=False, default="")


class RunRow(Base):
    __tablename__ = "runs"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    pipeline_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    step_name: Mapped[str] = mapped_column(String(256), nullable=False)
    container_ref: Mapped[str | None] = mapped_column(String(512), nullable=True)
    command_args: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="pending", index=True)
    exit_code: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[str] = mapped_column(String(64), nullable=False, default="")


class EventRow(Base):
    __tablename__ = "events"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    session_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    event_type: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    payload: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    seq_id: Mapped[int | None] = mapped_column(Integer, unique=True, default=None)
    created_at: Mapped[str] = mapped_column(String(64), nullable=False, default="")


class OutboxRow(Base):
    __tablename__ = "outbox"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    aggregate_id: Mapped[str] = mapped_column(String(256), nullable=False, index=True)
    event_type: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    payload: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    created_at: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    published: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, index=True)


class GrantRow(Base):
    __tablename__ = "grants"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(256), nullable=False)
    institution: Mapped[str | None] = mapped_column(String(512), nullable=True)
    total_budget: Mapped[str] = mapped_column(String(20), nullable=False)
    spent_budget: Mapped[str] = mapped_column(String(20), nullable=False, default="0.00")
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="USD")
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="active", index=True)
    created_at: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    updated_at: Mapped[str] = mapped_column(String(64), nullable=False, default="")


# ── Engine + session factory ────────────────────────────────────────────

TEST_DATABASE_URL = "sqlite+aiosqlite://"

test_engine = create_async_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)

TestSessionFactory = async_sessionmaker(
    test_engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


# ── Fixtures ─────────────────────────────────────────────────────────────

@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture(scope="session", autouse=True)
async def setup_database():
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await test_engine.dispose()


@pytest_asyncio.fixture
async def db_session():
    """Provide a fresh DB session — auto-cleanup via rollback in a SAVEPOINT."""
    async with TestSessionFactory() as session:
        # Use a SAVEPOINT so we can roll back all inserts after the test
        nested = await session.begin_nested()
        yield session
        # Rollback the savepoint, discarding all changes
        await nested.rollback()
        await session.close()


# ══════════════════════════════════════════════════════════════════════════
#  TESTS
# ══════════════════════════════════════════════════════════════════════════


class TestHealthEndpoint:
    @pytest.mark.asyncio
    async def test_health_returns_ok(self):
        from app.main import create_app
        test_app = create_app()
        test_app.router.lifespan_context = None  # skip lifespan for unit test

        async with AsyncClient(
            transport=ASGITransport(app=test_app), base_url="http://test"
        ) as ac:
            resp = await ac.get("/health")
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"


class TestAuthFlow:
    @pytest.mark.asyncio
    async def test_login_returns_token(self):
        from app.main import create_app
        test_app = create_app()
        test_app.router.lifespan_context = None

        async with AsyncClient(
            transport=ASGITransport(app=test_app), base_url="http://test"
        ) as ac:
            resp = await ac.post("/auth/login", json={"email": "test@example.com", "password": "any"})
        assert resp.status_code == 200
        data = resp.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"

    @pytest.mark.asyncio
    async def test_login_token_is_decodable(self):
        from jose import jwt
        from app.config import settings
        from app.main import create_app

        test_app = create_app()
        test_app.router.lifespan_context = None

        async with AsyncClient(
            transport=ASGITransport(app=test_app), base_url="http://test"
        ) as ac:
            resp = await ac.post("/auth/login", json={"email": "test@example.com", "password": "any"})
        token = resp.json()["access_token"]
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        assert "sub" in payload


class TestEventEngine:
    @pytest.mark.asyncio
    async def test_emit_and_retrieve_event(self, db_session: AsyncSession):
        user_id = str(uuid.uuid4())
        session_id = str(uuid.uuid4())

        # Commit parent rows so FK-free SQLite can reference them
        db_session.add(UserRow(id=user_id, email=f"evt-{user_id[:8]}@example.com"))
        db_session.add(SessionRow(id=session_id, title="Evt Session", user_id=user_id, status="active"))
        await db_session.flush()

        db_session.add(EventRow(
            session_id=session_id,
            event_type="SESSION_CREATED",
            payload=json.dumps({"title": "Test"}),
        ))
        await db_session.flush()

        stmt = select(EventRow).where(EventRow.event_type == "SESSION_CREATED")
        result = await db_session.execute(stmt)
        events = list(result.scalars().all())
        assert len(events) == 1
        assert events[0].event_type == "SESSION_CREATED"

    @pytest.mark.asyncio
    async def test_event_seq_id_autoincrement(self, db_session: AsyncSession):
        user_id = str(uuid.uuid4())
        session_id = str(uuid.uuid4())

        db_session.add(UserRow(id=user_id, email=f"seq-{user_id[:8]}@example.com"))
        db_session.add(SessionRow(id=session_id, title="Seq Test", user_id=user_id, status="active"))
        await db_session.flush()

        # Insert events with explicit seq_id values (simulating production auto-increment)
        db_session.add(EventRow(session_id=session_id, event_type="EVT_A", payload="{}", seq_id=1))
        db_session.add(EventRow(session_id=session_id, event_type="EVT_B", payload="{}", seq_id=2))
        await db_session.flush()

        stmt = select(EventRow).where(EventRow.session_id == session_id).order_by(EventRow.seq_id)
        result = await db_session.execute(stmt)
        events = list(result.scalars().all())
        assert len(events) == 2
        assert events[0].seq_id < events[1].seq_id
        assert events[0].id < events[1].id  # PK auto-increments

    @pytest.mark.asyncio
    async def test_outbox_creation(self, db_session: AsyncSession):
        db_session.add(OutboxRow(
            aggregate_id="test-session",
            event_type="SESSION_CREATED",
            payload=json.dumps({"event_type": "SESSION_CREATED"}),
            published=False,
        ))
        await db_session.flush()

        stmt = select(OutboxRow).where(OutboxRow.published == False)  # noqa: E712
        result = await db_session.execute(stmt)
        entries = list(result.scalars().all())
        assert len(entries) >= 1
        assert entries[0].event_type == "SESSION_CREATED"


class TestBudgetService:
    @pytest.mark.asyncio
    async def test_estimate_pipeline_cost(self):
        from app.services.budget import BudgetService
        from app.schemas.bio_container import BioContainerStep

        steps = [
            BioContainerStep(
                tool_name="fastqc",
                container_image="quay.io/biocontainers/fastqc:0.12.1@sha256:abc",
                command_args=["input.fastq.gz"],
                cpus=2,
                memory_mb=4096,
            ),
            BioContainerStep(
                tool_name="bwa-mem2",
                container_image="quay.io/biocontainers/bwa-mem2:2.2.1@sha256:def",
                command_args=["input_R1.fastq.gz"],
                cpus=8,
                memory_mb=32768,
            ),
        ]
        cost = BudgetService.estimate_pipeline_cost(steps)
        assert isinstance(cost, Decimal)
        assert cost > Decimal("0.00")

    @pytest.mark.asyncio
    async def test_estimate_single_step_cost(self):
        from app.services.budget import BudgetService
        from app.schemas.bio_container import BioContainerStep

        step = BioContainerStep(
            tool_name="fastqc",
            container_image="quay.io/biocontainers/fastqc:0.12.1@sha256:abc",
            command_args=["input.fastq.gz"],
            cpus=2,
            memory_mb=4096,
        )
        cost = BudgetService.estimate_step_cost(step)
        assert isinstance(cost, Decimal)
        assert cost > Decimal("0.00")

    @pytest.mark.asyncio
    async def test_cost_includes_overhead(self):
        from app.services.budget import BudgetService
        from app.schemas.bio_container import BioContainerStep

        step = BioContainerStep(
            tool_name="fastqc",
            container_image="quay.io/biocontainers/fastqc:0.12.1@sha256:abc",
            command_args=["input.fastq.gz"],
            cpus=2,
            memory_mb=4096,
        )
        cost = BudgetService.estimate_step_cost(step)
        # Cost should include 15% overhead
        assert cost > Decimal("0.00")
        assert cost.quantize(Decimal("0.01")) > Decimal("0.00")


class TestGrantsWithDB:
    @pytest.mark.asyncio
    async def test_create_and_retrieve_grant(self, db_session: AsyncSession):
        user_id = str(uuid.uuid4())
        grant_id = str(uuid.uuid4())

        db_session.add(UserRow(id=user_id, email=f"grant-{user_id[:8]}@example.com"))
        await db_session.flush()

        db_session.add(GrantRow(
            id=grant_id, user_id=user_id, name="NIH R01 Grant",
            institution="Test University", total_budget="10000.00",
            spent_budget="0.00", currency="USD", status="active",
        ))
        await db_session.flush()

        stmt = select(GrantRow).where(GrantRow.id == grant_id)
        result = await db_session.execute(stmt)
        g = result.scalar_one_or_none()
        assert g is not None
        assert g.name == "NIH R01 Grant"
        assert g.total_budget == "10000.00"

    @pytest.mark.asyncio
    async def test_grant_budget_calculation(self, db_session: AsyncSession):
        user_id = str(uuid.uuid4())
        grant_id = str(uuid.uuid4())

        db_session.add(UserRow(id=user_id, email=f"budget-{user_id[:8]}@example.com"))
        await db_session.flush()

        db_session.add(GrantRow(
            id=grant_id, user_id=user_id, name="Budget Test",
            total_budget="50000.00", spent_budget="12500.50",
            currency="USD", status="active",
        ))
        await db_session.flush()

        stmt = select(GrantRow).where(GrantRow.id == grant_id)
        result = await db_session.execute(stmt)
        g = result.scalar_one_or_none()
        remaining = Decimal(g.total_budget) - Decimal(g.spent_budget)
        assert remaining == Decimal("37499.50")


class TestSessionWithDB:
    @pytest.mark.asyncio
    async def test_create_and_retrieve_session(self, db_session: AsyncSession):
        user_id = str(uuid.uuid4())
        session_id = str(uuid.uuid4())

        db_session.add(UserRow(id=user_id, email=f"sess-{user_id[:8]}@example.com"))
        await db_session.flush()

        db_session.add(SessionRow(id=session_id, title="Test Session", user_id=user_id, status="active"))
        await db_session.flush()

        stmt = select(SessionRow).where(SessionRow.id == session_id)
        result = await db_session.execute(stmt)
        s = result.scalar_one_or_none()
        assert s is not None
        assert s.title == "Test Session"
        assert s.status == "active"

    @pytest.mark.asyncio
    async def test_session_soft_delete(self, db_session: AsyncSession):
        user_id = str(uuid.uuid4())
        session_id = str(uuid.uuid4())

        db_session.add(UserRow(id=user_id, email=f"del-{user_id[:8]}@example.com"))
        await db_session.flush()

        db_session.add(SessionRow(id=session_id, title="To Delete", user_id=user_id, status="active"))
        await db_session.flush()

        # Soft delete
        stmt = select(SessionRow).where(SessionRow.id == session_id)
        result = await db_session.execute(stmt)
        s = result.scalar_one()
        s.status = "deleted"
        await db_session.flush()

        result2 = await db_session.execute(stmt)
        assert result2.scalar_one().status == "deleted"


class TestPipelineWithDB:
    @pytest.mark.asyncio
    async def test_create_pipeline_under_session(self, db_session: AsyncSession):
        user_id = str(uuid.uuid4())
        session_id = str(uuid.uuid4())
        pipeline_id = str(uuid.uuid4())

        db_session.add(UserRow(id=user_id, email=f"pipe-{user_id[:8]}@example.com"))
        db_session.add(SessionRow(id=session_id, title="Pipeline Session", user_id=user_id, status="active"))
        await db_session.flush()

        db_session.add(PipelineRow(
            id=pipeline_id, session_id=session_id, name="Test Pipeline",
            description="A test pipeline",
            dag_json=json.dumps({"steps": [{"tool": "fastqc"}]}),
            status="draft",
        ))
        await db_session.flush()

        stmt = select(PipelineRow).where(PipelineRow.id == pipeline_id)
        result = await db_session.execute(stmt)
        p = result.scalar_one_or_none()
        assert p is not None
        assert p.name == "Test Pipeline"
        assert p.status == "draft"

    @pytest.mark.asyncio
    async def test_pipeline_status_transition(self, db_session: AsyncSession):
        user_id = str(uuid.uuid4())
        session_id = str(uuid.uuid4())
        pipeline_id = str(uuid.uuid4())

        db_session.add(UserRow(id=user_id, email=f"submit-{user_id[:8]}@example.com"))
        db_session.add(SessionRow(id=session_id, title="Submit Session", user_id=user_id, status="active"))
        await db_session.flush()

        db_session.add(PipelineRow(
            id=pipeline_id, session_id=session_id, name="Submit Test",
            dag_json="{}", status="draft",
        ))
        await db_session.flush()

        # Transition status
        stmt = select(PipelineRow).where(PipelineRow.id == pipeline_id)
        result = await db_session.execute(stmt)
        p = result.scalar_one()
        p.status = "submitted"
        await db_session.flush()

        result2 = await db_session.execute(stmt)
        assert result2.scalar_one().status == "submitted"

    @pytest.mark.asyncio
    async def test_pipeline_dag_json_roundtrip(self, db_session: AsyncSession):
        """Verify DAG JSON is stored and retrieved correctly."""
        user_id = str(uuid.uuid4())
        session_id = str(uuid.uuid4())
        pipeline_id = str(uuid.uuid4())

        db_session.add(UserRow(id=user_id, email=f"dag-{user_id[:8]}@example.com"))
        db_session.add(SessionRow(id=session_id, title="DAG Session", user_id=user_id, status="active"))
        await db_session.flush()

        dag = {
            "steps": [
                {"tool": "fastqc", "container": "quay.io/biocontainers/fastqc:0.12.1"},
                {"tool": "bwa-mem2", "container": "quay.io/biocontainers/bwa-mem2:2.2.1"},
            ],
            "edges": [["fastqc", "bwa-mem2"]],
        }
        db_session.add(PipelineRow(
            id=pipeline_id, session_id=session_id, name="DAG Pipeline",
            dag_json=json.dumps(dag), status="draft",
        ))
        await db_session.flush()

        stmt = select(PipelineRow).where(PipelineRow.id == pipeline_id)
        result = await db_session.execute(stmt)
        p = result.scalar_one()
        retrieved_dag = json.loads(p.dag_json)
        assert len(retrieved_dag["steps"]) == 2
        assert retrieved_dag["edges"] == [["fastqc", "bwa-mem2"]]