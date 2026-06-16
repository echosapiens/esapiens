# Sprint 7 — E.sapiens Bioinformatics SaaS Platform

## Architecture Overview

A production-grade platform bridging bioinformatics and HPC via an AI agent orchestrator. Four layers:

```
Frontend (Next.js) → Control Plane (FastAPI) → State Engine (Postgres + Redis) → Compute Plane (Modal)
```

## Build Phases

### Phase 1: Project Scaffold & Infrastructure
- Monorepo structure: `backend/`, `frontend/`, `docker-compose.yml`
- PostgreSQL + Redis via Docker Compose
- Alembic migrations, SQLAlchemy async models
- Pydantic schemas for all API contracts

### Phase 2: Backend Core (FastAPI)
- Auth layer: JWT + ORCID OAuth stub
- API routers: sessions, pipelines, runs, tools, grants
- SQLAlchemy async engine with session management
- Health checks, CORS, error handling

### Phase 3: LangGraph Agent Service
- Plan-and-Execute graph: Planner → Constructor → Critic → HITL Gate
- BioContainerStep Pydantic schema (pinned sha256 images)
- Tool metadata RAG stub (vector DB ready)
- Action traces abstraction for UI

### Phase 4: Modal Compute Integration
- Hybrid Controller-Sandbox model
- Pipeline controller (Modal Function) + ephemeral Sandboxes
- Streaming logs via `process.stdout` → Redis Pub/Sub
- Cost estimation matrix + grant quota enforcement

### Phase 5: State Engine & Real-Time Sync
- Event-sourced state: append-only event log in Postgres
- Transactional Outbox pattern (ACID event + outbox insert)
- WebSocket + SSE endpoints with `after_seq_id` reconciliation
- Client-side delta reducer (Zustand)

### Phase 6: Frontend (Next.js Academic IDE)
- Split-pane layout: Chat (left) + Workspace Canvas (right)
- Real-time WebSocket hook with reconnection + state reconciliation
- Pipeline execution Gantt/DAG chart
- Tool parameter override editor
- Export Methods panel (publication-ready)
- IGV.js stub + MultiQC iframe stub

### Phase 7: Security & Compliance
- Column-level encryption for PHI fields
- Sequence header redaction middleware
- Air-gapped sandbox execution (`network_access=False`)
- OIDC identity tokens for Modal Sandboxes
- Grant budget ledger with pre-execution quota checks

### Phase 8: Integration Tests
- End-to-end: Create session → Plan pipeline → Approve → Execute on Modal → Stream logs → Export methods
- WebSocket reconnection under disconnect
- Outbox → Redis fanout delivery guarantee

## Tech Stack
| Layer | Technology |
|-------|-----------|
| Frontend | Next.js 14, TypeScript, Zustand, TailwindCSS, shadcn/ui |
| Backend | FastAPI, SQLAlchemy 2.0 (async), Alembic, Pydantic v2 |
| Agent | LangGraph, LangChain |
| Compute | Modal SDK (Sandbox API) |
| Database | PostgreSQL 16 + TimescaleDB |
| Realtime | Redis 7 Pub/Sub, WebSocket, SSE |
| Auth | JWT (python-jose), ORCID OAuth2 |
| DevOps | Docker Compose, uv |

## Directory Structure
```
Esapiens-Sprint-7/
├── backend/
│   ├── app/
│   │   ├── main.py              # FastAPI app factory
│   │   ├── config.py            # Settings (env vars)
│   │   ├── database.py          # Async SQLAlchemy engine
│   │   ├── models/              # SQLAlchemy ORM models
│   │   │   ├── session.py
│   │   │   ├── pipeline.py
│   │   │   ├── run.py
│   │   │   ├── event.py
│   │   │   ├── outbox.py
│   │   │   └── grant.py
│   │   ├── schemas/             # Pydantic v2 schemas
│   │   │   ├── session.py
│   │   │   ├── pipeline.py
│   │   │   ├── run.py
│   │   │   ├── event.py
│   │   │   └── bio_container.py
│   │   ├── routers/             # API endpoints
│   │   │   ├── auth.py
│   │   │   ├── sessions.py
│   │   │   ├── pipelines.py
│   │   │   ├── runs.py
│   │   │   ├── ws.py            # WebSocket endpoint
│   │   │   └── grants.py
│   │   ├── services/            # Business logic
│   │   │   ├── agent.py         # LangGraph orchestration
│   │   │   ├── modal_compute.py # Modal Sandbox integration
│   │   │   ├── event_engine.py  # Event sourcing + outbox
│   │   │   ├── reconciler.py    # Job status reconciliation
│   │   │   └── budget.py        # Grant quota gateway
│   │   ├── middleware/
│   │   │   └── redaction.py     # Sequence header redaction
│   │   └── workers/
│   │       └── outbox_relay.py  # Outbox → Redis fanout
│   ├── alembic/
│   │   └── versions/
│   ├── alembic.ini
│   ├── pyproject.toml
│   └── Dockerfile
├── frontend/
│   ├── src/
│   │   ├── app/                 # Next.js app router
│   │   ├── components/
│   │   │   ├── chat/
│   │   │   ├── workspace/
│   │   │   ├── pipeline/
│   │   │   └── ui/
│   │   ├── hooks/
│   │   │   ├── useWebSocket.ts
│   │   │   └── useStateSync.ts
│   │   ├── store/
│   │   │   └── sessionStore.ts  # Zustand store + reducer
│   │   ├── lib/
│   │   │   └── api.ts
│   │   └── types/
│   │       └── events.ts
│   ├── package.json
│   ├── next.config.js
│   ├── tailwind.config.ts
│   └── tsconfig.json
├── docker-compose.yml
├── .env.example
└── PLAN.md
```