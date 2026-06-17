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
import { MarkdownRenderer } from "./MarkdownRenderer";
import { toast } from "@/store/toastStore";

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
    const capped = messages.slice(-200);
    localStorage.setItem(CHAT_STORAGE_PREFIX + sessionId, JSON.stringify(capped));
  } catch {
    // Ignore quota errors
  }
}

// ── ChatPanel ────────────────────────────────────────────────────────────

export function ChatPanel() {
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

  useEffect(() => {
    const sid = useSessionStore.getState().currentSessionId;
    saveChatToStorage(sid, messages);
  }, [messages]);

  useEffect(() => {
    const unsub = useSessionStore.subscribe((state, prev) => {
      if (state.currentSessionId !== prev.currentSessionId) {
        const stored = loadChatFromStorage(state.currentSessionId);
        if (stored.length > 0) {
          setMessages(stored);
        } else {
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

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, logs]);

  const lastPlanRef = useRef<string | null>(null);
  useEffect(() => {
    const plan = agentState.last_plan as Record<string, unknown> | null;
    if (!plan || agentState.approval_status !== "pending") return;

    const planKey = JSON.stringify({
      name: plan.name ?? plan.title,
      steps: (plan.steps as unknown[])?.length ?? 0,
    });
    if (lastPlanRef.current === planKey) return;
    lastPlanRef.current = planKey;

    const planName = (plan.name as string) ?? (plan.title as string) ?? "Pipeline Plan";
    setMessages((prev) => {
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
      if (prev.length > 0 && prev[prev.length - 1].id === logMsg.id) {
        return prev;
      }
      return [...prev, logMsg];
    });
  }, [logs]);

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
      if (
        mode === "supervisor" &&
        /llm|api[_\\s-]?key|openai|anthropic|model/i.test(message)
      ) {
        setSupervisorDisabled(true);
        toast.warning("Supervisor mode unavailable", "No LLM is configured on the backend");
      } else {
        toast.error("Agent error", message);
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

  const handleModeChange = useCallback((next: ChatMode) => {
    if (next === mode) return;
    setMode(next);
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
      toast.success("Pipeline approved", "Compute dispatched to Modal sandboxes");
      useSessionStore.setState((s) => ({
        agentState: { ...s.agentState, approval_status: "approved" },
      }));
    } catch (err) {
      const errMsg = err instanceof Error ? err.message : String(err);
      toast.error("Failed to submit pipeline", errMsg);
      setMessages((prev) => [
        ...prev,
        {
          id: generateId(),
          role: "system",
          content: `❌ Failed to submit pipeline: ${errMsg}`,
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
    <div className="flex h-full flex-col" style={{ background: "var(--mac-window-bg)" }}>
      {/* ── Header ─────────────────────────────────────────────────── */}
      <div className="flex items-center justify-between px-3 py-2 border-b" style={{ borderColor: "var(--mac-toolbar-separator)", background: "var(--mac-toolbar-bg)" }}>
        <div className="flex items-center gap-2">
          <Bot className="h-4 w-4" style={{ color: "var(--brand-gold)" }} />
          <h2 className="text-xs font-semibold" style={{ color: "var(--mac-label)" }}>Agent Chat</h2>
        </div>
        <div className="flex items-center gap-2">
          <ModeToggle mode={mode} onChange={handleModeChange} disabled={supervisorDisabled} />
          <ConnectionIndicator />
        </div>
      </div>

      {/* ── Messages ────────────────────────────────────────────────── */}
      <div className="flex-1 overflow-y-auto px-3 py-3 space-y-3">
        {messages.map((msg) => (
          <MessageBubble key={msg.id} message={msg} />
        ))}
        {isSending && (
          <div className="flex items-center gap-2 text-xs" style={{ color: "var(--mac-tertiary-label)" }}>
            <Loader2 className="h-3.5 w-3.5 animate-spin" />
            Thinking...
          </div>
        )}
        <div ref={messagesEndRef} />
      </div>

      {/* ── Approval buttons (when plan is pending) ────────────────── */}
      {agentState.approval_status === "pending" && (
        <div className="px-3 py-2 border-t" style={{ borderColor: "var(--mac-toolbar-separator)", background: "var(--mac-toolbar-bg)" }}>
          <p className="mb-2 text-[11px] font-medium" style={{ color: "var(--mac-label)" }}>
            Pipeline plan awaiting your approval:
          </p>
          <div className="flex gap-2">
            <button
              onClick={handleApprove}
              className="mac-btn mac-btn-accent text-xs"
            >
              <CheckCircle2 className="h-3.5 w-3.5" />
              Approve Plan
            </button>
            <button
              onClick={handleModify}
              className="mac-btn mac-btn-ghost text-xs"
            >
              <AlertCircle className="h-3.5 w-3.5" />
              Modify Parameters
            </button>
          </div>
        </div>
      )}

      {/* ── macOS Input bar ──────────────────────────────────────────── */}
      <div className="px-3 py-2 border-t" style={{ borderColor: "var(--mac-toolbar-separator)", background: "var(--mac-toolbar-bg)" }}>
        {mode === "supervisor" && supervisorDisabled && (
          <div className="mb-2 flex items-center gap-2 rounded-md px-2 py-1.5 text-[11px]" style={{ background: "rgba(255,149,0,0.08)", color: "var(--mac-orange)" }}>
            <AlertCircle className="h-3 w-3 shrink-0" />
            Supervisor mode is unavailable — no LLM configured.
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
                  ? "Supervisor unavailable"
                  : "Ask the supervisor to research…"
                : "Describe your analysis goal..."
            }
            className="mac-input flex-1"
            disabled={isSending || (mode === "supervisor" && supervisorDisabled)}
          />
          <button
            type="submit"
            disabled={
              isSending ||
              !input.trim() ||
              (mode === "supervisor" && supervisorDisabled)
            }
            className="mac-btn mac-btn-primary"
          >
            <Send className="h-3.5 w-3.5" />
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
    connected: "bg-system-green",
    connecting: "bg-system-yellow animate-pulse",
    disconnected: "bg-system-red",
    reconnecting: "bg-system-yellow animate-pulse",
  };
  const labels: Record<string, string> = {
    connected: "Connected",
    connecting: "Connecting...",
    disconnected: "Disconnected",
    reconnecting: "Reconnecting...",
  };
  return (
    <div className="flex items-center gap-1.5">
      <span className={cn("h-1.5 w-1.5 rounded-full", colors[status] ?? "bg-system-gray")} />
      <span className="text-[11px]" style={{ color: "var(--mac-tertiary-label)" }}>{labels[status] ?? status}</span>
    </div>
  );
}

// ── Message bubble ──────────────────────────────────────────────────────

function MessageBubble({ message }: { message: ChatMessage }) {
  const [expanded, setExpanded] = useState(true);

  if (message.role === "system") {
    return (
      <div className="mac-chat-bubble-system px-3 py-2 text-xs">
        <MarkdownRenderer content={message.content} />
      </div>
    );
  }

  const isAgent = message.role === "agent";
  const hasSupervisor =
    isAgent && message.supervisor && message.supervisor.subagent_results.length > 0;

  return (
    <div className={cn("flex gap-2", isAgent ? "flex-row" : "flex-row-reverse")}>
      <div
        className={cn(
          "flex h-7 w-7 shrink-0 items-center justify-center rounded-full",
          isAgent ? "bg-navy text-white" : "bg-gold text-navy"
        )}
      >
        {isAgent ? <Bot className="h-3.5 w-3.5" /> : <User className="h-3.5 w-3.5" />}
      </div>
      <div
        className={cn(
          "max-w-[85%] px-3 py-2 text-sm",
          isAgent
            ? hasSupervisor
              ? "mac-chat-bubble-agent w-full max-w-full"
              : "mac-chat-bubble-agent"
            : "mac-chat-bubble-user"
        )}
      >
        {hasSupervisor && message.supervisor && (
          <div className="mb-2 flex items-center gap-2 border-b pb-2 text-[11px]" style={{ borderColor: "var(--mac-separator)", color: "var(--mac-tertiary-label)" }}>
            <Sparkles className="h-3 w-3" style={{ color: "var(--brand-gold)" }} />
            <span className="font-semibold" style={{ color: "var(--mac-label)" }}>Supervisor</span>
            <span>·</span>
            <span>phase: {message.supervisor.phase}</span>
            <span>·</span>
            <span>{message.supervisor.subagent_results.length} subagent(s)</span>
          </div>
        )}
        <div className="mac-prose">
          <MarkdownRenderer content={message.content} />
        </div>
        {hasSupervisor && message.supervisor && (
          <SupervisorTrace results={message.supervisor.subagent_results} />
        )}
        {message.traces && message.traces.length > 0 && (
          <div className="mt-2 border-t pt-2" style={{ borderColor: "var(--mac-separator)" }}>
            <button
              onClick={() => setExpanded(!expanded)}
              className="flex items-center gap-1 text-[11px]"
              style={{ color: "var(--mac-tertiary-label)" }}
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
        <div className="mt-1 text-right text-[10px] opacity-50" style={{ color: "var(--mac-tertiary-label)" }}>
          {formatTimestamp(new Date(message.timestamp))}
        </div>
      </div>
    </div>
  );
}

// ── Trace line ──────────────────────────────────────────────────────────

function TraceLine({ trace }: { trace: ActionTrace }) {
  const icons: Record<string, React.ReactNode> = {
    completed: <CheckCircle2 className="h-3 w-3" style={{ color: "var(--mac-green)" }} />,
    running: <Loader2 className="h-3 w-3 animate-spin" style={{ color: "var(--mac-blue)" }} />,
    pending: <div className="h-3 w-3 rounded-full border border-gray-400" />,
    failed: <XCircle className="h-3 w-3" style={{ color: "var(--mac-red)" }} />,
  };
  return (
    <div className="flex items-center gap-1.5 text-xs">
      {icons[trace.status] ?? icons.pending}
      <span className="font-medium">{trace.label}</span>
      {trace.detail && (
        <span style={{ color: "var(--mac-tertiary-label)" }}>— {trace.detail}</span>
      )}
    </div>
  );
}

// ── Mode toggle (macOS NSSegmentedControl style) ────────────────────────

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
    <div className="mac-segmented">
      <button
        type="button"
        onClick={() => onChange("pipeline")}
        className={cn("mac-segmented-item", mode === "pipeline" && "active")}
      >
        <Network className="h-3 w-3" />
        Pipeline
      </button>
      <button
        type="button"
        onClick={() => !disabled && onChange("supervisor")}
        className={cn("mac-segmented-item", mode === "supervisor" && "active")}
        disabled={disabled}
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

// ── Supervisor trace ───────────────────────────────────────────

function SupervisorTrace({ results }: { results: SubagentSummary[] }) {
  if (!results || results.length === 0) return null;
  return (
    <div className="mt-3">
      <div className="mb-2 flex items-center gap-1.5 text-[10px] font-semibold uppercase tracking-wider" style={{ color: "var(--mac-tertiary-label)" }}>
        <Network className="h-3 w-3" />
        Subagent trace
      </div>
      <div className="relative space-y-2 border-l-2 border-dashed pl-4" style={{ borderColor: "rgba(201, 168, 76, 0.3)" }}>
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
      ? "bg-system-green"
      : confidencePct >= 50
        ? "bg-system-orange"
        : "bg-system-red";

  return (
    <div className="mac-card relative -ml-7 px-3 py-2.5 text-xs">
      {/* Node marker on the timeline */}
      <div className="absolute -left-[26px] top-3 flex h-5 w-5 items-center justify-center rounded-full bg-white shadow-sm" style={{ boxShadow: "0 0 0 2px rgba(201, 168, 76, 0.3)" }}>
        {meta.icon}
      </div>

      {/* Header: role • confidence */}
      <div className="flex items-center justify-between gap-2">
        <div className="flex items-center gap-1.5 font-semibold" style={{ color: "var(--mac-label)" }}>
          <span className={meta.accent}>{meta.icon}</span>
          <span>{meta.label}</span>
          <span style={{ color: "var(--mac-tertiary-label)" }}>·</span>
          <span style={{ color: "var(--mac-tertiary-label)" }}>step {index + 1}</span>
        </div>
        <div className="flex items-center gap-1.5">
          <span className="text-[10px] font-medium" style={{ color: "var(--mac-tertiary-label)" }}>
            {confidencePct}%
          </span>
          <div className="mac-progress w-16">
            <div
              className={cn("mac-progress-fill", confidenceColor)}
              style={{ width: `${confidencePct}%` }}
            />
          </div>
        </div>
      </div>

      {/* Task */}
      {result.task && (
        <p className="mt-1 text-[11px] italic" style={{ color: "var(--mac-tertiary-label)" }}>
          {result.task}
        </p>
      )}

      {/* Findings */}
      {result.findings && (
        <p className="mt-1.5 whitespace-pre-wrap text-xs" style={{ color: "var(--mac-label)" }}>
          {result.findings}
        </p>
      )}

      {/* Structured data */}
      {result.structured_data &&
        Object.keys(result.structured_data).length > 0 && (
          <div className="mt-2">
            <button
              type="button"
              onClick={() => setShowData((s) => !s)}
              className="flex items-center gap-1 text-[10px] font-medium"
              style={{ color: "var(--mac-tertiary-label)" }}
            >
              {showData ? (
                <ChevronDown className="h-3 w-3" />
              ) : (
                <ChevronRight className="h-3 w-3" />
              )}
              Structured data
            </button>
            {showData && (
              <pre className="mt-1 max-h-48 overflow-auto rounded-md p-2 text-[10px] leading-snug" style={{ background: "rgba(0,0,0,0.04)" }}>
                <code>{JSON.stringify(result.structured_data, null, 2)}</code>
              </pre>
            )}
          </div>
        )}

      {/* Citations */}
      {result.citations && result.citations.length > 0 && (
        <div className="mt-2">
          <button
            type="button"
            onClick={() => setShowCitations((s) => !s)}
            className="flex items-center gap-1 text-[10px] font-medium"
            style={{ color: "var(--mac-tertiary-label)" }}
          >
            {showCitations ? (
              <ChevronDown className="h-3 w-3" />
            ) : (
              <ChevronRight className="h-3 w-3" />
            )}
            <Quote className="h-3 w-3" />
            {result.citations.length} citation{result.citations.length === 1 ? "" : "s"}
          </button>
          {showCitations && (
            <ul className="mt-1 space-y-0.5 pl-1">
              {result.citations.map((c, i) => (
                <li
                  key={`${c}-${i}`}
                  className="break-all font-mono text-[10px]"
                  style={{ color: "var(--mac-secondary-label)" }}
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