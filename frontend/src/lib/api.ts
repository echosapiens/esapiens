// ── API client for E.sapiens backend ────────────────────────────────────
// Typesafe fetch wrapper with JWT auth and endpoint methods

import type { ServerEvent } from "@/types/events";

// ── Config ──────────────────────────────────────────────────────────────

const API_BASE = "/api";

// ── Auth token management ────────────────────────────────────────────────

let authToken: string | null = null;

export function setAuthToken(token: string | null) {
  authToken = token;
  if (typeof window !== "undefined") {
    if (token) {
      localStorage.setItem("esapiens_token", token);
    } else {
      localStorage.removeItem("esapiens_token");
    }
  }
}

export function getAuthToken(): string | null {
  if (authToken) return authToken;
  if (typeof window !== "undefined") {
    authToken = localStorage.getItem("esapiens_token");
  }
  return authToken;
}

// ── Types ───────────────────────────────────────────────────────────────

export interface SessionRead {
  id: string;
  title: string;
  user_id: string;
  status: string;
  created_at: string;
  updated_at: string;
}

export interface SessionCreate {
  title: string;
}

export interface SessionUpdate {
  title?: string;
  status?: string;
}

export interface PipelineRead {
  id: string;
  session_id: string;
  name: string;
  description: string | null;
  dag_json: Record<string, unknown>;
  status: string;
  created_at: string;
  updated_at: string;
}

export interface PipelineCreate {
  name: string;
  description?: string;
  dag_json: Record<string, unknown>;
}

export interface PipelineUpdate {
  name?: string;
  description?: string;
  dag_json?: Record<string, unknown>;
  status?: string;
}

export interface RunRead {
  id: string;
  pipeline_id: string;
  step_name: string;
  container_ref: string | null;
  command_args: Record<string, unknown> | null;
  status: string;
  exit_code: number | null;
  modal_sandbox_id: string | null;
  started_at: string | null;
  completed_at: string | null;
  created_at: string;
}

export interface RunLogChunk {
  run_id: string;
  stream: string;
  offset: number;
  text: string;
}

export interface GrantRead {
  id: string;
  user_id: string;
  name: string;
  institution: string | null;
  total_budget: string;
  spent_budget: string;
  currency: string;
  status: string;
  created_at: string;
  updated_at: string;
}

export interface GrantCreate {
  name: string;
  institution?: string;
  total_budget: number;
  currency?: string;
}

export interface GrantBalance {
  grant_id: string;
  total_budget: string;
  spent_budget: string;
  remaining_budget: string;
  currency: string;
}

export interface ProjectedState {
  session_id: string;
  pipelines: Array<{
    id: string;
    name: string;
    status: string;
    created_at: string;
  }>;
  runs: Array<{
    id: string;
    step_name: string;
    status: string;
    created_at: string;
  }>;
  metrics: Record<string, unknown>;
  agent_state: {
    last_plan: Record<string, unknown> | null;
    approval_status: string | null;
  };
  events_count: number;
  projected_at: string;
}

export interface LoginRequest {
  email: string;
  password: string;
}

export interface TokenResponse {
  access_token: string;
  token_type: string;
}

export interface EventResponse {
  id: number;
  session_id: string;
  event_type: string;
  payload: Record<string, unknown>;
  created_at: string;
  seq_id: number;
}

// ── Fetch helper ────────────────────────────────────────────────────────

async function apiFetch<T>(
  path: string,
  options: RequestInit = {}
): Promise<T> {
  const token = getAuthToken();
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(options.headers as Record<string, string> | undefined),
  };

  if (token) {
    headers["Authorization"] = `Bearer ${token}`;
  }

  const response = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers,
  });

  if (!response.ok) {
    const errorBody = await response.text().catch(() => "");
    throw new Error(
      `API Error ${response.status}: ${errorBody || response.statusText}`
    );
  }

  // Handle 204 No Content
  if (response.status === 204) {
    return undefined as unknown as T;
  }

  return response.json();
}

// ── API endpoints ────────────────────────────────────────────────────────

export interface ChatResponse {
  pipeline_id: string;
  title: string;
  description: string;
  steps: Array<{
    step_id: string;
    tool_name: string;
    description: string;
    inputs: string[];
    outputs: string[];
    depends_on: string[];
    estimated_cpu: number;
    estimated_memory_mb: number;
  }>;
  estimated_cost: number;
  status: string;
  message: string;
}

export interface ChatRequest {
  prompt: string;
  grant_id?: string;
}

export const api = {
  // ── Auth ────────────────────────────────────────────────────────
  login: (data: LoginRequest) =>
    apiFetch<TokenResponse>("/auth/login", {
      method: "POST",
      body: JSON.stringify(data),
    }),

  /** Dev-only: auto-login as the seeded dev user. Stores the token. */
  devLogin: async (): Promise<string> => {
    const res = await apiFetch<TokenResponse>("/auth/dev-login", {
      method: "POST",
    });
    setAuthToken(res.access_token);
    return res.access_token;
  },

  // ── Sessions ─────────────────────────────────────────────────────
  listSessions: () => apiFetch<SessionRead[]>("/sessions/"),

  getSession: (id: string) => apiFetch<SessionRead>(`/sessions/${id}`),

  createSession: (data: SessionCreate) =>
    apiFetch<SessionRead>("/sessions/", {
      method: "POST",
      body: JSON.stringify(data),
    }),

  updateSession: (id: string, data: SessionUpdate) =>
    apiFetch<SessionRead>(`/sessions/${id}`, {
      method: "PATCH",
      body: JSON.stringify(data),
    }),

  deleteSession: (id: string) =>
    apiFetch<void>(`/sessions/${id}`, { method: "DELETE" }),

  // ── Pipelines ───────────────────────────────────────────────────
  listPipelines: (sessionId: string) =>
    apiFetch<PipelineRead[]>(
      `/sessions/${sessionId}/pipelines`
    ),

  createPipeline: (sessionId: string, data: PipelineCreate) =>
    apiFetch<PipelineRead>(
      `/sessions/${sessionId}/pipelines`,
      {
        method: "POST",
        body: JSON.stringify(data),
      }
    ),

  getPipeline: (pipelineId: string) =>
    apiFetch<PipelineRead>(`/pipelines/${pipelineId}`),

  updatePipeline: (pipelineId: string, data: PipelineUpdate) =>
    apiFetch<PipelineRead>(`/pipelines/${pipelineId}`, {
      method: "PATCH",
      body: JSON.stringify(data),
    }),

  submitPipeline: (pipelineId: string) =>
    apiFetch<PipelineRead>(`/pipelines/${pipelineId}/submit`, {
      method: "POST",
    }),

  // ── Runs ─────────────────────────────────────────────────────────
  listRuns: (pipelineId: string) =>
    apiFetch<RunRead[]>(`/pipelines/${pipelineId}/runs`),

  getRun: (runId: string) => apiFetch<RunRead>(`/runs/${runId}`),

  cancelRun: (runId: string) =>
    apiFetch<RunRead>(`/runs/${runId}/cancel`, { method: "POST" }),

  getRunLogs: (runId: string, stream: string = "stdout") =>
    apiFetch<RunLogChunk[]>(
      `/runs/${runId}/logs?stream=${stream}`
    ),

  // ── Grants ───────────────────────────────────────────────────────
  listGrants: () => apiFetch<GrantRead[]>("/grants/"),

  getGrant: (id: string) => apiFetch<GrantRead>(`/grants/${id}`),

  createGrant: (data: GrantCreate) =>
    apiFetch<GrantRead>("/grants/", {
      method: "POST",
      body: JSON.stringify(data),
    }),

  getGrantBalance: (id: string) =>
    apiFetch<GrantBalance>(`/grants/${id}/balance`),

  // ── Events (reconciliation) ─────────────────────────────────────
  getEventsAfter: (sessionId: string, afterSeqId: number = 0) =>
    apiFetch<EventResponse[]>(
      `/sessions/${sessionId}/events?after_seq_id=${afterSeqId}`
    ),

  // ── Projected state ──────────────────────────────────────────────
  getProjectedState: (sessionId: string) =>
    apiFetch<ProjectedState>(`/sessions/${sessionId}/state`),

  // ── Chat (agent) ─────────────────────────────────────────────────
  sendChat: (sessionId: string, data: ChatRequest) =>
    apiFetch<ChatResponse>(`/sessions/${sessionId}/chat`, {
      method: "POST",
      body: JSON.stringify(data),
    }),
};