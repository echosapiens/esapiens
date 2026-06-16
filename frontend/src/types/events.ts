// ── TypeScript types mirroring backend event schemas ────────────────────
// These types correspond 1:1 to the Pydantic models in backend/app/schemas/event.py

// ── Individual event payloads ───────────────────────────────────────────

export interface AgentPlanGenerated {
  event_type: "AGENT_PLAN_GENERATED";
  session_id: string;
  plan: Record<string, unknown>;
}

export interface RunStepLog {
  event_type: "RUN_STEP_LOG";
  run_id: string;
  step_name: string;
  stream: "stdout" | "stderr";
  text: string;
}

export interface MetricsUpdated {
  event_type: "METRICS_UPDATED";
  session_id: string;
  metrics: Record<string, unknown>;
}

export interface PipelineStatusChanged {
  event_type: "PIPELINE_STATUS_CHANGED";
  pipeline_id: string;
  old_status: string;
  new_status: string;
}

// ── Discriminated union ─────────────────────────────────────────────────

export type ServerEvent =
  | AgentPlanGenerated
  | RunStepLog
  | MetricsUpdated
  | PipelineStatusChanged;

// ── Event envelope ──────────────────────────────────────────────────────

export interface EventEnvelope {
  id: number;
  session_id: string;
  event: ServerEvent;
  created_at: string;
}

// ── Convenience type map ────────────────────────────────────────────────

export type ServerEventType = ServerEvent["event_type"];

export const SERVER_EVENT_TYPES: ServerEventType[] = [
  "AGENT_PLAN_GENERATED",
  "RUN_STEP_LOG",
  "METRICS_UPDATED",
  "PIPELINE_STATUS_CHANGED",
];

// ── Session state shape ────────────────────────────────────────────────

export interface PipelineSummary {
  id: string;
  name: string;
  status: string;
  created_at: string;
}

export interface RunSummary {
  id: string;
  step_name: string;
  status: string;
  started_at?: string | null;
  completed_at?: string | null;
  created_at: string;
}

export interface AgentState {
  last_plan: Record<string, unknown> | null;
  approval_status: "pending" | "approved" | "rejected" | null;
}

export interface MetricsState {
  total_cpu_hours: number;
  total_cost: number;
  total_runs: number;
  completed_runs: number;
  failed_runs: number;
  [key: string]: unknown;
}

export interface SessionState {
  session_id: string;
  pipelines: PipelineSummary[];
  runs: RunSummary[];
  metrics: MetricsState;
  agent_state: AgentState;
  events_count: number;
  projected_at: string;
}

// ── Log entry stored in the frontend ────────────────────────────────────

export interface LogEntry {
  id: string;
  run_id: string;
  step_name: string;
  stream: "stdout" | "stderr";
  text: string;
  timestamp: number;
}

// ── Connection status ───────────────────────────────────────────────────

export type ConnectionStatus = "connected" | "connecting" | "disconnected" | "reconnecting";