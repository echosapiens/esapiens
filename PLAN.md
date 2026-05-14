# E.sapiens v2 — Mantine UI + LangGraph Implementation Plan

> **Goal:** Rebuild the E.sapiens bioinformatics chat/agent platform with Mantine UI v7 (React frontend) and LangGraph (backend agent framework).

**Architecture:** Vite + React 18 + TypeScript + Mantine UI v7 frontend → FastAPI + LangGraph backend with SSE streaming for real-time agent responses.

**Deployment:** Local development first. Modal optional for production.

---

## Phase 1: Project Scaffold
- Initialize Vite + React + TypeScript project
- Install Mantine UI v7 + dependencies
- Set up Python FastAPI backend skeleton
- Establish project structure

## Phase 2: Backend — FastAPI + LangGraph Core
- FastAPI server with CORS, health check
- LangGraph agent with ReAct loop + OpenRouter
- SSE streaming endpoint (`/chat/stream`)
- Session management with SQLite checkpoints
- Port intent classifier + skill loader from Sprint 1

## Phase 3: Frontend — Core Chat UI
- Mantine theme (dark/light, custom bioinformatics color palette)
- AppShell layout (navbar, header, main content)
- Chat component with streaming text rendering
- Message bubbles with markdown rendering
- Session sidebar (new chat, resume, delete)

## Phase 4: Frontend — Tool Calls & Thinking
- Tool call display (collapsible, with timing)
- Skill loading indicator
- Abort/cancel in-flight requests

## Phase 5: Frontend — Visualizations
- Port visualization components into Mantine:
  - Volcano Plot (recharts/plotly)
  - Heatmap
  - Structure Viewer (NGL.js)
  - DataTable
  - Line Plot
- VisualizationPanel component that auto-detects type

## Phase 6: Integration & Polish
- Connect frontend to backend
- Streaming event handling (SSE parser)
- Error handling, loading states
- Docker Compose for local dev

---

## Task List

### Task 1: Scaffold Vite + Mantine frontend
`npm create vite` with react-ts template, then add Mantine v7 + deps.

### Task 2: Scaffold FastAPI backend
Python FastAPI skeleton with CORS, health, configuration.

### Task 3: Build LangGraph agent
ReAct loop agent with OpenRouter, intent classifier, skill loader.

### Task 4: Add streaming endpoint
SSE streaming for real-time agent responses.

### Task 5: Build Mantine theme + AppShell
Dark/light theme, custom colors, responsive layout.

### Task 6: Build Chat component
Message list, input box, streaming text, markdown rendering.

### Task 7: Build Session sidebar
Session list, new/resume/delete, mobile responsive.

### Task 8: Build ToolCall display
Collapsible tool call cards, skill loading indicators.

### Task 9: Port visualization components
Volcano, heatmap, structure viewer, data table, line plot.

### Task 10: Wire everything together
API client, SSE parser, end-to-end chat flow, error states.