# E.sapiens v2 — Bioinformatics Agent Platform

> **An intelligent, agentic bioinformatics assistant** powered by LangGraph, FastAPI, and React.
> E.sapiens v2 classifies user queries, dynamically loads bioinformatics *skills*, and orchestrates
> a ReAct (Reasoning + Acting) loop to answer questions, analyze data, and produce rich
> visualizations — all through a natural-language chat interface.

---

## Architecture Overview

```
┌──────────────────────────────────────────────────────────────────┐
│                         User / Browser                          │
└──────────────────┬───────────────────────────────────────────────┘
                   │  POST /chat  │  POST /chat/stream (SSE)
                   ▼              ▼
┌──────────────────────────────────────────────────────────────────┐
│  ┌─────────────────────┐         ┌────────────────────────────┐  │
│  │   Nginx (prod)      │         │  Vite Dev Server (dev)     │  │
│  │   or Vite Proxy     │         │  proxy: /api, /chat → BE   │  │
│  └────────┬────────────┘         └───────────┬────────────────┘  │
│           │                                  │                   │
│  ┌────────▼──────────────────────────────────▼────────────────┐  │
│  │                  FastAPI / Uvicorn                         │  │
│  │  app.py → streaming.py → main.py → agent.py               │  │
│  │  Port 8000                                                 │  │
│  └──────────────────────────┬─────────────────────────────────┘  │
│                             │                                    │
│  ┌──────────────────────────▼─────────────────────────────────┐  │
│  │              LangGraph StateGraph (ReAct Loop)              │  │
│  │                                                             │  │
│  │  ┌──────────┐   ┌───────────┐   ┌────────────────────┐    │  │
│  │  │ Intent   │──▶│ Load      │──▶│ ReAct Agent Loop   │    │  │
│  │  │ Classify │   │ Skills    │   │ (LLM + Tools)      │    │  │
│  │  └──────────┘   └───────────┘   └─────────┬──────────┘    │  │
│  │                                           ▼                │  │
│  │  ┌─────────────────────────────────────────────────────┐   │  │
│  │  │  Tool Executor: BioPython, NCBI, PDB, Plots, etc.  │   │  │
│  │  └─────────────────────────────────────────────────────┘   │  │
│  └─────────────────────────────────────────────────────────────┘  │
│                                                                    │
│  ┌─────────────────────────────────────────────────────────────┐  │
│  │  Session Store (in-memory) — skills, messages, viz data    │  │
│  └─────────────────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────────────┘
```

### Key Components

| Component | Technology | Purpose |
|-----------|-----------|---------|
| **Frontend** | React 18 + TypeScript + Mantine v7 + Vite | Chat UI, visualizations (plotly, NGL viewer, charts) |
| **Backend** | FastAPI + Uvicorn | REST endpoints, SSE streaming, CORS |
| **Agent** | LangGraph (StateGraph) | ReAct loop — intent classification → skill loading → tool execution |
| **LLM** | OpenRouter API | Language model provider (Claude, GPT, Gemini, etc.) |
| **Tools** | BioPython, httpx, custom | BLAST, NCBI queries, PDB fetching, data plotting |

---

## Prerequisites

- **Node.js** 18+ (20+ recommended)
- **npm** 9+
- **Python** 3.12+
- **OpenRouter API key** — [get one here](https://openrouter.ai/keys)
- **Docker** (optional, for production deployment)

---

## Quick Start — Without Docker

### 1. Clone and configure

```bash
cd /Users/shababkhan/Documents/Esapiens-Sprints/Esapiens-Sprint-2

# Set up backend configuration
cp backend/.env.example backend/.env
# Edit backend/.env — replace the placeholder with your OpenRouter API key
```

### 2. Start the backend

```bash
cd backend

# Create and activate virtual environment (if not already done)
python3 -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Start the API server
uvicorn app:app --host 0.0.0.0 --port 8000 --reload
```

The backend is now running at **http://localhost:8000**.

- Health check: `curl http://localhost:8000/health`
- API info: `curl http://localhost:8000/`

### 3. Start the frontend (in a separate terminal)

```bash
cd frontend

# Install dependencies
npm install --legacy-peer-deps

# Start Vite dev server
npm run dev
```

The frontend is now running at **http://localhost:5173**.

The Vite dev server automatically proxies `/api` and `/chat` requests to the backend at `http://localhost:8000`.

### 4. Open the app

Navigate to **[http://localhost:5173](http://localhost:5173)** in your browser.

---

## Quick Start — With Docker

### 1. Set your API key

```bash
export OPENROUTER_API_KEY=sk-or-v1-your-actual-key-here
```

### 2. Build and run

```bash
docker compose up --build
```

Or use the helper script:

```bash
OPENROUTER_API_KEY=sk-or-v1-your-actual-key-here ./scripts/start-prod.sh
```

### 3. Access the app

- **Frontend**: http://localhost:5173
- **Backend API**: http://localhost:8000
- **Health check**: http://localhost:8000/health

### 4. Stop the containers

```bash
docker compose down
```

---

## Configuration

### Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `OPENROUTER_API_KEY` | **Yes** | Your OpenRouter API key for LLM access |

### Backend `.env` file

```env
OPENROUTER_API_KEY=sk-or-v1-your-actual-key-here
```

### Nginx (Production)

When running with Docker Compose, `frontend/nginx.conf` configures:
- Static asset serving from `/usr/share/nginx/html`
- Proxy pass for `/chat` (including SSE streaming) → `backend:8000`
- Proxy pass for `/api` → `backend:8000`
- SPA fallback (all other routes serve `index.html`)

---

## Development Guide

### Project Structure

```
E.sapiens-Sprint-2/
├── backend/
│   ├── .venv/                  # Python virtual environment
│   ├── .env                    # Local environment variables (gitignored)
│   ├── .env.example            # Environment variable template
│   ├── Dockerfile              # Production Docker image
│   ├── requirements.txt        # Python dependencies
│   ├── app.py                  # FastAPI application entry point
│   ├── main.py                 # LangGraph agent orchestration
│   ├── agent.py                # StateGraph definition & ReAct loop
│   ├── streaming.py            # Chat & session REST endpoints
│   ├── intent_classifier.py    # Query classification → skill loading
│   ├── skill_loader.py         # Dynamic skill/module loading
│   └── tools.py                # Bioinformatic tool definitions
├── frontend/
│   ├── Dockerfile              # Multi-stage build (Node → Nginx)
│   ├── nginx.conf              # Nginx configuration for production
│   ├── package.json            # Node dependencies & scripts
│   ├── vite.config.ts          # Vite configuration + dev proxy
│   ├── tsconfig.json           # TypeScript configuration
│   ├── dist/                   # Build output (gitignored in .gitignore)
│   ├── src/
│   │   ├── App.tsx             # Root React component
│   │   ├── lib/
│   │   │   └── api.ts          # API client (chat, stream, sessions)
│   │   ├── components/
│   │   │   ├── Chat/           # Chat conversation components
│   │   │   ├── Layout/         # App shell, header, sidebar
│   │   │   └── Visualizations/ # Chart & viewer components
│   │   └── ...
│   └── index.html              # HTML entry point
├── scripts/
│   ├── start-dev.sh            # Start both services in dev mode
│   └── start-prod.sh           # Start with Docker Compose
├── docker-compose.yml          # Production orchestration
└── README.md                   # This file
```

### Dev Script

Use the development helper to start both services with one command:

```bash
./scripts/start-dev.sh
```

This will:
1. Create/activate the Python virtual environment
2. Install backend dependencies
3. Start uvicorn with hot-reload on port 8000
4. Install frontend dependencies
5. Start Vite dev server on port 5173

Press **Ctrl+C** to stop both services.

### Working on the Backend

- **Hot reload**: `uvicorn app:app --host 0.0.0.0 --port 8000 --reload` — the server restarts automatically on file changes.
- **API docs**: Available at http://localhost:8000/docs (Swagger UI) or http://localhost:8000/redoc.
- **Adding tools**: Add new functions to `backend/tools.py` and register them in the tool definitions.
- **Adding skills**: Create skill modules and update the classifier in `backend/intent_classifier.py`.

### Working on the Frontend

- **Hot module replacement**: Vite automatically applies changes without full page reloads.
- **Viz components**: Located in `src/components/Visualizations/` — add new visualization types there.
- **API client**: All backend communication is centralized in `src/lib/api.ts`.

### Verifying Endpoints

```bash
# Health check
curl http://localhost:8000/health

# Synchronous chat
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"query": "Hello!", "session_id": "test"}'

# List sessions
curl http://localhost:8000/sessions

# Get session details
curl http://localhost:8000/sessions/test
```

---

## Docker Images

### Backend (`backend/Dockerfile`)

- Base: `python:3.12-slim`
- Installs `requirements.txt` via pip
- Runs `uvicorn app:app --host 0.0.0.0 --port 8000`
- Exposes port 8000

### Frontend (`frontend/Dockerfile`)

- **Stage 1 (build)**: `node:22-alpine` — runs `npm install --legacy-peer-deps` and `npm run build`
- **Stage 2 (serve)**: `nginx:alpine` — serves `/usr/share/nginx/html` with custom `nginx.conf`
- Exposes port 80 (mapped to 5173 in compose file)

---

## Troubleshooting

| Problem | Solution |
|---------|----------|
| `OPENROUTER_API_KEY` not set | Ensure the env var is set before running, or add it to `backend/.env` |
| Backend won't start | Check that port 8000 is free and `.venv` is activated |
| Frontend can't reach backend | In dev, Vite proxying is configured in `vite.config.ts`. In Docker, verify `depends_on` ordering. |
| SSE streaming not working | Ensure `proxy_buffering off;` is set in nginx for `/chat` location |
| `npm install` errors | Use `--legacy-peer-deps` flag — some Mantine peer deps need it |
| Docker build fails | Try `docker compose build --no-cache` to clear build cache |
| Frontend shows blank page | Check browser console for errors; ensure `dist/` was built successfully |

---

## License

Proprietary — internal use. E.sapiens v2 — Nous Research.