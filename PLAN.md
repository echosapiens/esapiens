# Esapiens Sprint 4 — Split-Runtime Bio-Orchestrator

> **Mission:** Re-architect from GCP-targeted monolith to a Split-Runtime architecture
> running orchestration on Hostinger VPS (2GB RAM) and heavy compute on Modal Sandboxes.

## Topology

```
User → [FastAPI + LangGraph on Hostinger VPS]
                ↓
[Phase 1: Research Agent] — queries BioContainers + OpenRouter for tool discovery
        ↓
[Phase 2: Contract Agent] — builds Pydantic ContainerContract (image, inputs, CLI, outputs)
        ↓
[Phase 3: Orchestrator] — spawns modal.Sandbox, pulls BioContainer, executes, streams logs
        ↓
[SQLite persistence] — job history, execution logs, results
```

## Architecture Components

### Backend (VPS-side, lightweight)
- **FastAPI** — CORS, JWT auth, SSE streaming
- **LangGraph** — 3-node immutable state graph
- **Pydantic schemas** — ContainerContract, FileRequirement, JobExecution, CostEstimate
- **OpenRouter client** — LLM reasoning for Phase 1 & 2
- **Modal SDK** — spawn sandboxes from VPS
- **SQLite** — job persistence, checkpoints

### Modal-side (heavy compute)
- **Ephemeral MicroVMs** — docker-in-docker sandbox
- **BioContainers** — quay.io registry pull
- **Mount paths** — /data/input/, /data/output/
- **Streaming** — stdout/stderr back to VPS

### Frontend (Next.js + Tailwind)
- Natural language prompt input
- Job monitoring dashboard (status, logs, results)
- Cost preview before execution
- Session management

## Task Breakdown

### Phase 1: Backend Foundation
1. Create project scaffold (directories, requirements.txt, .env)
2. Pydantic schemas (ContainerContract, FileRequirement, etc.)
3. Config & security layer (JWT, CORS, input sanitization)
4. OpenRouter client wrapper
5. SQLite persistence layer
6. Modal SDK integration layer

### Phase 2: LangGraph 3-Phase Agent
7. Research Agent — BioContainers API + OpenRouter tool discovery
8. Contract Agent — Pydantic ContainerContract generation
9. Orchestrator Agent — Modal Sandbox lifecycle management
10. State graph assembly + FastAPI endpoints

### Phase 3: Frontend
11. Next.js + Tailwind scaffold
12. Prompt input + submission API client
13. Job monitoring dashboard (SSE + polling)
14. Results viewer
15. Cost preview component

### Phase 4: Deployment & Verification
16. Dockerfile for VPS
17. UFW rules, rate limiting
18. Integration test: full 3-phase pipeline