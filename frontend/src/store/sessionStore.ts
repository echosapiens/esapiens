import { create } from "zustand";
import type {
  AgentPlanGenerated,
  RunStepLog,
  RunProgress,
  RunStatusChanged,
  MetricsUpdated,
  PipelineStatusChanged,
  ServerEvent,
  EventEnvelope,
  SessionState,
  LogEntry,
  ConnectionStatus,
  PipelineSummary,
  RunSummary,
  MetricsState,
  AgentState,
} from "@/types/events";
import { api } from "@/lib/api";

// ── State shape ────────────────────────────────────────────────────────

interface SessionStoreState {
  // Current session
  currentSessionId: string | null;
  currentSession: {
    id: string;
    title: string;
    status: string;
    created_at: string;
    updated_at: string;
  } | null;

  // Event-sourced projections
  pipelines: PipelineSummary[];
  runs: RunSummary[];
  metrics: MetricsState;
  agentState: AgentState;

  // Logs accumulated from RUN_STEP_LOG events
  logs: LogEntry[];

  // Connection
  connectionStatus: ConnectionStatus;
  lastSeqId: number;

  // Loading flags
  isLoading: boolean;
  error: string | null;
}

// ── Actions ─────────────────────────────────────────────────────────────

interface SessionStoreActions {
  setSession: (sessionId: string, session: SessionStoreState["currentSession"]) => void;
  applyEvent: (envelope: EventEnvelope) => void;
  setConnectionStatus: (status: ConnectionStatus) => void;
  setLastSeqId: (seqId: number) => void;
  clearLogs: () => void;
  reset: () => void;

  // Async actions
  fetchSession: (sessionId: string) => Promise<void>;
  fetchProjectState: (sessionId: string) => Promise<void>;
}

// ── Initial state ───────────────────────────────────────────────────────

const initialState: SessionStoreState = {
  currentSessionId: null,
  currentSession: null,
  pipelines: [],
  runs: [],
  metrics: {
    total_cpu_hours: 0,
    total_cost: 0,
    total_runs: 0,
    completed_runs: 0,
    failed_runs: 0,
  },
  agentState: {
    last_plan: null,
    approval_status: null,
  },
  logs: [],
  connectionStatus: "disconnected",
  lastSeqId: 0,
  isLoading: false,
  error: null,
};

// ── Session reducer (matches blueprint) ─────────────────────────────────

function sessionReducer(
  state: SessionStoreState,
  event: ServerEvent,
  envelope: EventEnvelope
): Partial<SessionStoreState> {
  switch (event.event_type) {
    case "AGENT_PLAN_GENERATED": {
      const e = event as AgentPlanGenerated;
      return {
        agentState: {
          last_plan: e.plan,
          approval_status: "pending",
        },
        lastSeqId: Math.max(state.lastSeqId, envelope.id),
      };
    }

    case "RUN_STEP_LOG": {
      const e = event as RunStepLog;
      const logEntry: LogEntry = {
        id: `log-${envelope.id}`,
        run_id: e.run_id,
        step_name: e.step_name,
        stream: e.stream,
        text: e.text,
        timestamp: new Date(envelope.created_at).getTime(),
      };
      return {
        logs: [...state.logs, logEntry],
        lastSeqId: Math.max(state.lastSeqId, envelope.id),
      };
    }

    case "RUN_PROGRESS": {
      // Live progress update from Modal sandbox — non-blocking, just merge
      const e = event as RunProgress;
      return {
        runs: state.runs.map((r) =>
          r.id === e.run_id ? { ...r, progress: e.progress } : r
        ),
        lastSeqId: Math.max(state.lastSeqId, envelope.id),
      };
    }

    case "RUN_STATUS_CHANGED": {
      // Run transitioned (e.g. pending→running→completed/failed)
      const e = event as RunStatusChanged;
      return {
        runs: state.runs.map((r) =>
          r.id === e.run_id
            ? {
                ...r,
                status: e.new_status,
                ...(e.new_status === "completed" ? { progress: 100 } : {}),
              }
            : r
        ),
        lastSeqId: Math.max(state.lastSeqId, envelope.id),
      };
    }

    case "METRICS_UPDATED": {
      const e = event as MetricsUpdated;
      const updatedMetrics = { ...state.metrics };
      for (const [key, value] of Object.entries(e.metrics)) {
        if (typeof value === "number") {
          updatedMetrics[key] = (updatedMetrics[key] as number | undefined ?? 0) + value;
        } else {
          updatedMetrics[key] = value;
        }
      }
      return {
        metrics: updatedMetrics,
        lastSeqId: Math.max(state.lastSeqId, envelope.id),
      };
    }

    case "PIPELINE_STATUS_CHANGED": {
      const e = event as PipelineStatusChanged;
      return {
        pipelines: state.pipelines.map((p) =>
          p.id === e.pipeline_id
            ? { ...p, status: e.new_status }
            : p
        ),
        lastSeqId: Math.max(state.lastSeqId, envelope.id),
      };
    }

    default:
      return { lastSeqId: Math.max(state.lastSeqId, envelope.id) };
  }
}

// ── Store ───────────────────────────────────────────────────────────────

export const useSessionStore = create<SessionStoreState & SessionStoreActions>((set, get) => ({
  ...initialState,

  setSession: (sessionId, session) =>
    set({
      currentSessionId: sessionId,
      currentSession: session,
      error: null,
    }),

  applyEvent: (envelope) =>
    set((state) => sessionReducer(state, envelope.event, envelope)),

  setConnectionStatus: (status) => set({ connectionStatus: status }),

  setLastSeqId: (seqId) => set({ lastSeqId: seqId }),

  clearLogs: () => set({ logs: [] }),

  reset: () => set(initialState),

  fetchSession: async (sessionId) => {
    set({ isLoading: true, error: null });
    try {
      const session = await api.getSession(sessionId);
      set({
        currentSessionId: sessionId,
        currentSession: session,
        isLoading: false,
      });
    } catch (err) {
      set({
        error: err instanceof Error ? err.message : "Failed to fetch session",
        isLoading: false,
      });
    }
  },

  fetchProjectState: async (sessionId) => {
    set({ isLoading: true, error: null });
    try {
      const projectedState = await api.getProjectedState(sessionId);
      const metrics: MetricsState = {
        total_cpu_hours: 0,
        total_cost: 0,
        total_runs: 0,
        completed_runs: 0,
        failed_runs: 0,
        ...(typeof projectedState.metrics === "object" && projectedState.metrics !== null
          ? projectedState.metrics as Partial<MetricsState>
          : {}),
      };
      // Normalize runs to RunSummary shape (projected runs lack progress)
      const runs: RunSummary[] = (projectedState.runs ?? []).map((r) => ({
        id: r.id,
        step_name: r.step_name,
        status: r.status,
        progress: r.status === "completed" ? 100 : r.status === "failed" ? 0 : 0,
        started_at: null,
        completed_at: null,
        created_at: r.created_at,
      }));
      set({
        pipelines: projectedState.pipelines,
        runs,
        metrics,
        agentState: projectedState.agent_state as AgentState,
        isLoading: false,
      });
    } catch (err) {
      set({
        error: err instanceof Error ? err.message : "Failed to fetch projected state",
        isLoading: false,
      });
    }
  },
}));