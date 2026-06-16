"use client";

import { useState, useRef, useEffect, useCallback } from "react";
import { useSessionStore } from "@/store/sessionStore";
import { cn, formatTimestamp, generateId } from "@/lib/utils";
import { api } from "@/lib/api";
import {
  Send,
  CheckCircle2,
  XCircle,
  ChevronDown,
  ChevronRight,
  Bot,
  User,
  AlertCircle,
  Loader2,
  Dna,
  Calculator,
  Code2,
  BookOpen,
  Sparkles,
  Quote,
  Network,
} from "lucide-react";
import type { SubagentSummary, SubagentRole } from "@/lib/api";
import type { LogEntry } from "@/types/events";

// ── Types ───────────────────────────────────────────────────────────────

interface ChatMessage {
  id: string;
  role: "user" | "agent" | "system";
  content: string;
  timestamp: number;
  traces?: ActionTrace[];
  supervisor?: {
    subagent_results: SubagentSummary[];
    iterations: number;
    phase: string;
  };
}

interface ActionTrace {
  step: string;
  label: string;
  status: "pending" | "running" | "completed" | "failed";
  detail?: string;
}

type ChatMode = "pipeline" | "supervisor";

const CHAT_STORAGE_PREFIX = "esapiens:chat:";

function loadChatFromStorage(sessionId: string | null): ChatMessage[] {
  if (typeof window === "undefined" || !sessionId) return [];
  try {
    const raw = localStorage.getItem(CHAT_STORAGE_PREFIX + sessionId);
    if (!raw) return [];
    const parsed = JSON.parse(raw);
    if (!Array.isArray(parsed)) return [];
    return parsed;
  } catch {
    return [];
  }
}

function saveChatToStorage(sessionId: string | null, messages: ChatMessage[]): void {
  if (typeof window === "undefined" || !sessionId) return;
  try {
    // Cap at 200 messages to avoid localStorage bloat
    const capped = messages.slice(-200);
    localStorage.setItem(CHAT_STORAGE_PREFIX + sessionId, JSON.stringify(capped));
  } catch {
    // Ignore quota errors
  }
}

// ── ChatPanel ────────────────────────────────────────────────────────────

export function ChatPanel() {
  // Load the current session id at mount time (we read from the store via getState)
  const currentSessionId = useSessionStore.getState().currentSessionId;
  const [messages, setMessages] = useState<ChatMessage[]>(() => {
    const stored = loadChatFromStorage(currentSessionId);
    if (stored.length > 0) return stored;
    return [
      {
        id: "welcome",
        role: "system",
        content:
          "Welcome to E.sapiens. Describe your analysis goal, and I'll plan a reproducible pipeline for you.",
        timestamp: Date.now(),
      },
    ];
  });
  const [input, setInput] = useState("");
  const [isSending, setIsSending] = useState(false);
  const [mode, setMode] = useState<ChatMode>("pipeline");
  const [supervisorDisabled, setSupervisorDisabled] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const agentState = useSessionStore((s) => s.agentState);
  const logs = useSessionStore((s) => s.logs);

  // Persist messages to localStorage on every change so chat survives navigation
  useEffect(() => {
    const sid = useSessionStore.getState().currentSessionId;
    saveChatToStorage(sid, messages);
  }, [messages]);

  // When the active session changes, reload the chat from storage
  useEffect(() => {
    const unsub = useSessionStore.subscribe((state, prev) => {
      if (state.currentSessionId !== prev.currentSessionId) {
        const stored = loadChatFromStorage(state.currentSessionId);
        if (stored.length > 0) {
          setMessages(stored);
        } else {
          // New session — show welcome
          setMessages([
            {
              id: "welcome-" + Date.now(),
              role: "system",
              content: "Welcome to E.sapiens. Describe your analysis goal, and I'll plan a reproducible pipeline for you.",
              timestamp: Date.now(),
            },
          ]);
        }
      }
    });
    return unsub;
  }, []);

  // ── Auto-scroll on new messages ────────────────────────────────────
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, logs]);

  // ── When agent plan is generated, add a message ──────────────────
  // Track which plans we've already announced so the "awaiting review" badge
  // resets between plans. We key by the plan's content hash, not a static id.
  const lastPlanRef = useRef<string | null>(null);
  useEffect(() => {
    const plan = agentState.last_plan as Record<string, unknown> | null;
    if (!plan || agentState.approval_status !== "pending") return;

    // Use a stable key derived from the plan to detect "new plan arrived"
    const planKey = JSON.stringify({
      name: plan.name ?? plan.title,
      steps: (plan.steps as unknown[])?.length ?? 0,
    });
    if (lastPlanRef.current === planKey) return;
    lastPlanRef.current = planKey;

    const planName = (plan.name as string) ?? (plan.title as string) ?? "Pipeline Plan";
    setMessages((prev) => {
      // Remove any prior "plan-pending" badge from a previous plan
      const filtered = prev.filter((m) => m.id !== "plan-pending");
      return [
        ...filtered,
        {
          id: "plan-pending",
          role: "agent",
          content: `I've generated a pipeline plan: **${planName}**. Review the steps and parameters in the Pipeline tab, then approve or request modifications.`,
          timestamp: Date.now(),
          traces: [
            { step: "plan", label: "Pipeline plan generated", status: "completed" },
            { step: "review", label: "Awaiting your review", status: "running" },
          ],
        },
      ];
    });
  }, [agentState.last_plan, agentState.approval_status]);

  // ── Add log messages as system traces ──────────────────────────────
  useEffect(() => {
    if (logs.length === 0) return;
    const lastLog = logs[logs.length - 1];
    setMessages((prev) => {
      const logMsg: ChatMessage = {
        id: `log-${lastLog.id}`,
        role: "system",
        content: `[${lastLog.step_name}] ${lastLog.stream === "stderr" ? "⚠ " : ""}${lastLog.text}`,
        timestamp: lastLog.timestamp,
      };
      // Avoid duplicate log messages
      if (prev.length > 0 && prev[prev.length - 1].id === logMsg.id) {
        return prev;
      }
      return [...prev, logMsg];
    });
  }, [logs]);

  // ── Send message handler ──────────────────────────────────────────
  const handleSend = useCallback(async () => {
    const text = input.trim();
    if (!text || isSending) return;
    if (mode === "supervisor" && supervisorDisabled) return;

    const userMsg: ChatMessage = {
      id: generateId(),
      role: "user",
      content: text,
      timestamp: Date.now(),
    };
    setMessages((prev) => [...prev, userMsg]);
    setInput("");
    setIsSending(true);

    try {
      const sessionId = useSessionStore.getState().currentSessionId;
      if (!sessionId) {
        setMessages((prev) => [
          ...prev,
          {
            id: generateId(),
            role: "system",
            content: "No active session. Please create or select a session first.",
            timestamp: Date.now(),
          },
        ]);
        setIsSending(false);
        return;
      }

      if (mode === "supervisor") {
        const response = await api.sendSupervisor(sessionId, { prompt: text });
        setMessages((prev) => [
          ...prev,
          {
            id: generateId(),
            role: "agent",
            content: response.answer,
            timestamp: Date.now(),
            supervisor: {
              subagent_results: response.subagent_results ?? [],
              iterations: response.iterations ?? 0,
              phase: response.phase ?? "unknown",
            },
          },
        ]);
      } else {
        const response = await api.sendChat(sessionId, { prompt: text });
        setMessages((prev) => [
          ...prev,
          {
            id: generateId(),
            role: "agent",
            content: response.message,
            timestamp: Date.now(),
            traces: response.steps.map((step) => ({
              step: step.step_id,
              label: `${step.tool_name}: ${step.description}`,
              status: "completed" as const,
              detail: `CPU: ${step.estimated_cpu} · RAM: ${step.estimated_memory_mb}MB`,
            })),
          },
        ]);
      }
    } catch (err) {
      const message = err instanceof Error ? err.message : "Failed to get response from agent";
      // Detect "no LLM configured" style errors and lock out supervisor mode gracefully
      if (
        mode === "supervisor" &&
        /llm|api[_\s-]?key|openai|anthropic|model/i.test(message)
      ) {
        setSupervisorDisabled(true);
      }
      setMessages((prev) => [
        ...prev,
        {
          id: generateId(),
          role: "system",
          content: `Error: ${message}`,
          timestamp: Date.now(),
        },
      ]);
    } finally {
      setIsSending(false);
    }
  }, [input, isSending, mode, supervisorDisabled]);

  // ── Mode toggle handler ──────────────────────────────────────────
  const handleModeChange = useCallback((next: ChatMode) => {
    if (next === mode) return;
    setMode(next);
    // Clear messages so each mode has a clean transcript
    setMessages([
      {
        id: "welcome",
        role: "system",
        content:
          next === "supervisor"
            ? "Supervisor mode: your prompt is dispatched to specialist subagents (biology, math, code, literature). Each subagent's findings are shown in a trace below the final synthesized answer."
            : "Welcome to E.sapiens. Describe your analysis goal, and I'll plan a reproducible pipeline for you.",
        timestamp: Date.now(),
      },
    ]);
  }, [mode]);

  // ── Approval handlers ─────────────────────────────────────────────
  const handleApprove = useCallback(async () => {
    const pipelineId = agentState.last_plan
      ? (agentState.last_plan as Record<string, unknown>).id as string | undefined
      : undefined;
    if (!pipelineId) {
      setMessages((prev) => [
        ...prev,
        {
          id: generateId(),
          role: "system",
          content: "⚠ No pipeline plan to approve. Generate a plan first.",
          timestamp: Date.now(),
        },
      ]);
      return;
    }
    // Optimistic UI update
    setMessages((prev) => [
      ...prev,
      {
        id: generateId(),
        role: "system",
        content: "Approving pipeline plan and dispatching to Modal sandboxes...",
        timestamp: Date.now(),
      },
    ]);
    try {
      const submitted = await api.submitPipeline(pipelineId);
      setMessages((prev) => [
        ...prev,
        {
          id: generateId(),
          role: "system",
          content: `✅ Pipeline **${submitted.name}** approved (status: ${submitted.status}). Compute dispatched to Modal. Track live progress in the Pipeline tab or the Job Monitor.`,
          timestamp: Date.now(),
        },
      ]);
      // Mark approval as completed in the store
      useSessionStore.setState((s) => ({
        agentState: { ...s.agentState, approval_status: "approved" },
      }));
    } catch (err) {
      setMessages((prev) => [
        ...prev,
        {
          id: generateId(),
          role: "system",
          content: `❌ Failed to submit pipeline: ${err instanceof Error ? err.message : String(err)}`,
          timestamp: Date.now(),
        },
      ]);
    }
  }, [agentState.last_plan]);

  const handleModify = useCallback(() => {
    setMessages((prev) => [
      ...prev,
      {
        id: generateId(),
        role: "system",
        content: "Switch to the **Pipeline** tab to edit step parameters, then come back and approve.",
        timestamp: Date.now(),
      },
    ]);
  }, []);

  // ── Render ─────────────────────────────────────────────────────────
  return (
    <div className="flex h-full flex-col glass">
      {/* ── Header ─────────────────────────────────────────────────── */}
      <div className="flex items-center justify-between border-b border-border px-4 py-3 glass-heavy">
        <div className="flex items-center gap-2">
          <Bot className="h-5 w-5 text-gold" />
          <h2 className="text-sm font-semibold text-navy">Agent Chat</h2>
        </div>
        <div className="flex items-center gap-3">
          <ModeToggle mode={mode} onChange={handleModeChange} disabled={supervisorDisabled} />
          <ConnectionIndicator />
        </div>
      </div>

      {/* ── Messages ────────────────────────────────────────────────── */}
      <div className="flex-1 overflow-y-auto px-4 py-3 space-y-4">
        {messages.map((msg) => (
          <MessageBubble key={msg.id} message={msg} />
        ))}
        {isSending && (
          <div className="flex items-center gap-2 text-sm text-muted-foreground">
            <Loader2 className="h-4 w-4 animate-spin" />
            Thinking...
          </div>
        )}
        <div ref={messagesEndRef} />
      </div>

      {/* ── Approval buttons (when plan is pending) ────────────────── */}
      {agentState.approval_status === "pending" && (
        <div className="border-t border-border glass-heavy px-4 py-3">
          <p className="mb-2 text-xs font-medium text-navy">
            Pipeline plan awaiting your approval:
          </p>
          <div className="flex gap-2">
            <button
              onClick={handleApprove}
              className="btn-accent inline-flex items-center gap-1.5 text-sm"
            >
              <CheckCircle2 className="h-4 w-4" />
              Approve Plan
            </button>
            <button
              onClick={handleModify}
              className="btn-ghost inline-flex items-center gap-1.5 text-sm"
            >
              <AlertCircle className="h-4 w-4" />
              Modify Parameters
            </button>
          </div>
        </div>
      )}

      {/* ── Input bar ──────────────────────────────────────────────── */}
      <div className="border-t border-border glass-heavy px-4 py-3">
        {mode === "supervisor" && supervisorDisabled && (
          <div className="mb-2 flex items-center gap-2 rounded-lg border border-amber-300/60 bg-amber-50/60 px-3 py-2 text-xs text-amber-900">
            <AlertCircle className="h-3.5 w-3.5 shrink-0" />
            Supervisor mode is unavailable — no LLM is configured on the backend.
            Switch back to Pipeline mode to continue.
          </div>
        )}
        <form
          onSubmit={(e) => {
            e.preventDefault();
            handleSend();
          }}
          className="flex items-center gap-2"
        >
          <input
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder={
              mode === "supervisor"
                ? supervisorDisabled
                  ? "Supervisor unavailable — see note above"
                  : "Ask the supervisor to research, analyse, or plan…"
                : "Describe your analysis goal..."
            }
            className="input-base flex-1"
            disabled={isSending || (mode === "supervisor" && supervisorDisabled)}
          />
          <button
            type="submit"
            disabled={
              isSending ||
              !input.trim() ||
              (mode === "supervisor" && supervisorDisabled)
            }
            className="btn-primary inline-flex items-center gap-1.5"
          >
            <Send className="h-4 w-4" />
            Send
          </button>
        </form>
      </div>
    </div>
  );
}

// ── Connection indicator ────────────────────────────────────────────────

function ConnectionIndicator() {
  const status = useSessionStore((s) => s.connectionStatus);
  const colors: Record<string, string> = {
    connected: "bg-green-500",
    connecting: "bg-yellow-500 animate-pulse",
    disconnected: "bg-red-500",
    reconnecting: "bg-yellow-500 animate-pulse",
  };
  const labels: Record<string, string> = {
    connected: "Connected",
    connecting: "Connecting...",
    disconnected: "Disconnected",
    reconnecting: "Reconnecting...",
  };
  return (
    <div className="flex items-center gap-1.5">
      <span className={cn("h-2 w-2 rounded-full", colors[status] ?? "bg-gray-400")} />
      <span className="text-xs text-muted-foreground">{labels[status] ?? status}</span>
    </div>
  );
}

// ── Message bubble ──────────────────────────────────────────────────────

function MessageBubble({ message }: { message: ChatMessage }) {
  const [expanded, setExpanded] = useState(true);

  if (message.role === "system") {
    return (
      <div className="glass rounded-xl border border-gold/20 px-3 py-2 text-xs text-navy-700">
        {message.content}
      </div>
    );
  }

  const isAgent = message.role === "agent";
  const hasSupervisor =
    isAgent && message.supervisor && message.supervisor.subagent_results.length > 0;

  return (
    <div
      className={cn("flex gap-3", isAgent ? "flex-row" : "flex-row-reverse")}
    >
      <div
        className={cn(
          "flex h-8 w-8 shrink-0 items-center justify-center rounded-full",
          isAgent ? "bg-navy rounded-full text-white" : "bg-gold text-navy"
        )}
      >
        {isAgent ? <Bot className="h-4 w-4" /> : <User className="h-4 w-4" />}
      </div>
      <div
        className={cn(
          "max-w-[80%] rounded-lg px-3 py-2 text-sm",
          isAgent
            ? hasSupervisor
              ? "glass-heavy rounded-xl text-navy w-full max-w-full"
              : "glass rounded-xl text-navy"
            : "bg-navy text-white"
        )}
      >
        {hasSupervisor && message.supervisor && (
          <div className="mb-2 flex items-center gap-2 border-b border-border pb-2 text-xs text-muted-foreground">
            <Sparkles className="h-3.5 w-3.5 text-gold" />
            <span className="font-semibold text-navy">Supervisor</span>
            <span>·</span>
            <span>phase: {message.supervisor.phase}</span>
            <span>·</span>
            <span>iterations: {message.supervisor.iterations}</span>
            <span>·</span>
            <span>{message.supervisor.subagent_results.length} subagent(s)</span>
          </div>
        )}
        <p className="whitespace-pre-wrap">{message.content}</p>
        {hasSupervisor && message.supervisor && (
          <SupervisorTrace
            results={message.supervisor.subagent_results}
          />
        )}
        {message.traces && message.traces.length > 0 && (
          <div className="mt-2 border-t border-border pt-2">
            <button
              onClick={() => setExpanded(!expanded)}
              className="flex items-center gap-1 text-xs text-muted-foreground hover:text-navy"
            >
              {expanded ? (
                <ChevronDown className="h-3 w-3" />
              ) : (
                <ChevronRight className="h-3 w-3" />
              )}
              Action traces
            </button>
            {expanded && (
              <div className="mt-1 space-y-1">
                {message.traces.map((trace) => (
                  <TraceLine key={trace.step} trace={trace} />
                ))}
              </div>
            )}
          </div>
        )}
        <div className="mt-1 text-right text-[10px] opacity-50">
          {formatTimestamp(new Date(message.timestamp))}
        </div>
      </div>
    </div>
  );
}

// ── Trace line ──────────────────────────────────────────────────────────

function TraceLine({ trace }: { trace: ActionTrace }) {
  const icons: Record<string, React.ReactNode> = {
    completed: <CheckCircle2 className="h-3 w-3 text-green-500" />,
    running: <Loader2 className="h-3 w-3 animate-spin text-blue-500" />,
    pending: <div className="h-3 w-3 rounded-full border border-gray-400" />,
    failed: <XCircle className="h-3 w-3 text-red-500" />,
  };
  return (
    <div className="flex items-center gap-1.5 text-xs">
      {icons[trace.status] ?? icons.pending}
      <span className="font-medium">{trace.label}</span>
      {trace.detail && (
        <span className="text-muted-foreground">— {trace.detail}</span>
      )}
    </div>
  );
}

// ── Mode toggle (Pipeline / Supervisor) ─────────────────────────────────

function ModeToggle({
  mode,
  onChange,
  disabled,
}: {
  mode: ChatMode;
  onChange: (m: ChatMode) => void;
  disabled?: boolean;
}) {
  return (
    <div
      role="tablist"
      aria-label="Chat mode"
      className="inline-flex items-center rounded-full border border-border bg-white/40 p-0.5 text-xs shadow-sm backdrop-blur"
    >
      <button
        type="button"
        role="tab"
        aria-selected={mode === "pipeline"}
        onClick={() => onChange("pipeline")}
        className={cn(
          "inline-flex items-center gap-1 rounded-full px-2.5 py-1 transition-colors",
          mode === "pipeline"
            ? "bg-navy text-white shadow-sm"
            : "text-navy/70 hover:text-navy"
        )}
      >
        <Network className="h-3 w-3" />
        Pipeline
      </button>
      <button
        type="button"
        role="tab"
        aria-selected={mode === "supervisor"}
        onClick={() => !disabled && onChange("supervisor")}
        title={
          disabled
            ? "Supervisor mode unavailable — no LLM configured"
            : "Supervisor mode"
        }
        className={cn(
          "inline-flex items-center gap-1 rounded-full px-2.5 py-1 transition-colors",
          mode === "supervisor"
            ? "bg-gold text-navy shadow-sm"
            : "text-navy/70 hover:text-navy",
          disabled && "cursor-not-allowed opacity-50"
        )}
      >
        <Sparkles className="h-3 w-3" />
        Supervisor
      </button>
    </div>
  );
}

// ── Subagent role metadata ──────────────────────────────────────────────

const SUBAGENT_META: Record<
  SubagentRole,
  { label: string; icon: React.ReactNode; accent: string }
> = {
  biology: {
    label: "Biology",
    icon: <Dna className="h-4 w-4" />,
    accent: "text-emerald-600",
  },
  math: {
    label: "Math",
    icon: <Calculator className="h-4 w-4" />,
    accent: "text-sky-600",
  },
  code: {
    label: "Code",
    icon: <Code2 className="h-4 w-4" />,
    accent: "text-indigo-600",
  },
  literature: {
    label: "Literature",
    icon: <BookOpen className="h-4 w-4" />,
    accent: "text-rose-600",
  },
};

function subagentMeta(role: SubagentRole) {
  return (
    SUBAGENT_META[role] ?? {
      label: role,
      icon: <Bot className="h-4 w-4" />,
      accent: "text-navy",
    }
  );
}

// ── Supervisor trace (timeline of subagent cards) ───────────────────────

function SupervisorTrace({ results }: { results: SubagentSummary[] }) {
  if (!results || results.length === 0) return null;
  return (
    <div className="mt-3">
      <div className="mb-2 flex items-center gap-1.5 text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">
        <Network className="h-3 w-3" />
        Subagent trace
      </div>
      <div className="relative space-y-2 border-l-2 border-dashed border-gold/40 pl-4">
        {results.map((r, idx) => (
          <SubagentCard key={`${r.role}-${idx}`} result={r} index={idx} />
        ))}
      </div>
    </div>
  );
}

// ── Subagent card ───────────────────────────────────────────────────────

function SubagentCard({
  result,
  index,
}: {
  result: SubagentSummary;
  index: number;
}) {
  const [showData, setShowData] = useState(false);
  const [showCitations, setShowCitations] = useState(false);
  const meta = subagentMeta(result.role);
  const confidencePct = Math.max(0, Math.min(100, Math.round(result.confidence * 100)));
  const confidenceColor =
    confidencePct >= 80
      ? "bg-emerald-500"
      : confidencePct >= 50
        ? "bg-amber-500"
        : "bg-rose-500";

  return (
    <div className="glass relative -ml-7 rounded-xl border border-border/60 px-3 py-2.5 text-xs shadow-sm">
      {/* Node marker on the timeline */}
      <div
        className={cn(
          "absolute -left-[26px] top-3 flex h-5 w-5 items-center justify-center rounded-full bg-white shadow ring-2 ring-gold/40",
          meta.accent
        )}
      >
        {meta.icon}
      </div>

      {/* Header: role • confidence */}
      <div className="flex items-center justify-between gap-2">
        <div className="flex items-center gap-1.5 font-semibold text-navy">
          <span className={meta.accent}>{meta.icon}</span>
          <span>{meta.label}</span>
          <span className="text-muted-foreground">·</span>
          <span className="text-muted-foreground">step {index + 1}</span>
        </div>
        <div className="flex items-center gap-1.5">
          <span className="text-[10px] font-medium text-muted-foreground">
            {confidencePct}%
          </span>
          <div className="h-1.5 w-16 overflow-hidden rounded-full bg-navy/10">
            <div
              className={cn("h-full", confidenceColor)}
              style={{ width: `${confidencePct}%` }}
            />
          </div>
        </div>
      </div>

      {/* Task */}
      {result.task && (
        <p className="mt-1 text-[11px] italic text-muted-foreground">
          {result.task}
        </p>
      )}

      {/* Findings */}
      {result.findings && (
        <p className="mt-1.5 whitespace-pre-wrap text-xs text-navy/90">
          {result.findings}
        </p>
      )}

      {/* Structured data toggle */}
      {result.structured_data &&
        Object.keys(result.structured_data).length > 0 && (
          <div className="mt-2">
            <button
              type="button"
              onClick={() => setShowData((s) => !s)}
              className="flex items-center gap-1 text-[10px] font-medium text-muted-foreground hover:text-navy"
            >
              {showData ? (
                <ChevronDown className="h-3 w-3" />
              ) : (
                <ChevronRight className="h-3 w-3" />
              )}
              Structured data
            </button>
            {showData && (
              <pre className="mt-1 max-h-48 overflow-auto rounded-md bg-navy/5 p-2 text-[10px] leading-snug text-navy/90">
                <code>{JSON.stringify(result.structured_data, null, 2)}</code>
              </pre>
            )}
          </div>
        )}

      {/* Citations toggle */}
      {result.citations && result.citations.length > 0 && (
        <div className="mt-2">
          <button
            type="button"
            onClick={() => setShowCitations((s) => !s)}
            className="flex items-center gap-1 text-[10px] font-medium text-muted-foreground hover:text-navy"
          >
            {showCitations ? (
              <ChevronDown className="h-3 w-3" />
            ) : (
              <ChevronRight className="h-3 w-3" />
            )}
            <Quote className="h-3 w-3" />
            {result.citations.length} citation
            {result.citations.length === 1 ? "" : "s"}
          </button>
          {showCitations && (
            <ul className="mt-1 space-y-0.5 pl-1">
              {result.citations.map((c, i) => (
                <li
                  key={`${c}-${i}`}
                  className="break-all font-mono text-[10px] text-navy/80"
                >
                  • {c}
                </li>
              ))}
            </ul>
          )}
        </div>
      )}
    </div>
  );
}