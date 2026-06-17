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
  } catch {}
}

export function ChatPanel() {
  const currentSessionId = useSessionStore.getState().currentSessionId;
  const [messages, setMessages] = useState<ChatMessage[]>(() => {
    const stored = loadChatFromStorage(currentSessionId);
    if (stored.length > 0) return stored;
    return [{
      id: "welcome",
      role: "system",
      content: "Welcome to E.sapiens. Describe your analysis goal, and I'll plan a reproducible pipeline for you.",
      timestamp: Date.now(),
    }];
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
        setMessages(stored.length > 0 ? stored : [{
          id: "welcome-" + Date.now(),
          role: "system",
          content: "Welcome to E.sapiens. Describe your analysis goal, and I'll plan a reproducible pipeline for you.",
          timestamp: Date.now(),
        }]);
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
    const planKey = JSON.stringify({ name: plan.name ?? plan.title, steps: (plan.steps as unknown[])?.length ?? 0 });
    if (lastPlanRef.current === planKey) return;
    lastPlanRef.current = planKey;
    const planName = (plan.name as string) ?? (plan.title as string) ?? "Pipeline Plan";
    setMessages((prev) => {
      const filtered = prev.filter((m) => m.id !== "plan-pending");
      return [...filtered, {
        id: "plan-pending",
        role: "agent",
        content: `I've generated a pipeline plan: **${planName}**. Review the steps and parameters in the Pipeline tab, then approve or request modifications.`,
        timestamp: Date.now(),
        traces: [
          { step: "plan", label: "Pipeline plan generated", status: "completed" },
          { step: "review", label: "Awaiting your review", status: "running" },
        ],
      }];
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
      if (prev.length > 0 && prev[prev.length - 1].id === logMsg.id) return prev;
      return [...prev, logMsg];
    });
  }, [logs]);

  const handleSend = useCallback(async () => {
    const text = input.trim();
    if (!text || isSending) return;
    if (mode === "supervisor" && supervisorDisabled) return;

    const userMsg: ChatMessage = { id: generateId(), role: "user", content: text, timestamp: Date.now() };
    setMessages((prev) => [...prev, userMsg]);
    setInput("");
    setIsSending(true);

    try {
      const sessionId = useSessionStore.getState().currentSessionId;
      if (!sessionId) {
        setMessages((prev) => [...prev, { id: generateId(), role: "system", content: "No active session. Please create or select a session first.", timestamp: Date.now() }]);
        setIsSending(false);
        return;
      }

      if (mode === "supervisor") {
        const response = await api.sendSupervisor(sessionId, { prompt: text });
        setMessages((prev) => [...prev, {
          id: generateId(), role: "agent", content: response.answer, timestamp: Date.now(),
          supervisor: { subagent_results: response.subagent_results ?? [], iterations: response.iterations ?? 0, phase: response.phase ?? "unknown" },
        }]);
      } else {
        const response = await api.sendChat(sessionId, { prompt: text });
        setMessages((prev) => [...prev, {
          id: generateId(), role: "agent", content: response.message, timestamp: Date.now(),
          traces: response.steps.map((step) => ({
            step: step.step_id, label: `${step.tool_name}: ${step.description}`, status: "completed" as const,
            detail: `CPU: ${step.estimated_cpu} · RAM: ${step.estimated_memory_mb}MB`,
          })),
        }]);
      }
    } catch (err) {
      const message = err instanceof Error ? err.message : "Failed to get response from agent";
      if (mode === "supervisor" && /llm|api[_\\s-]?key|openai|anthropic|model/i.test(message)) {
        setSupervisorDisabled(true);
        toast.warning("Supervisor mode unavailable", "No LLM is configured on the backend");
      } else {
        toast.error("Agent error", message);
      }
      setMessages((prev) => [...prev, { id: generateId(), role: "system", content: `Error: ${message}`, timestamp: Date.now() }]);
    } finally {
      setIsSending(false);
    }
  }, [input, isSending, mode, supervisorDisabled]);

  const handleModeChange = useCallback((next: ChatMode) => {
    if (next === mode) return;
    setMode(next);
    setMessages([{
      id: "welcome", role: "system",
      content: next === "supervisor"
        ? "Supervisor mode: your prompt is dispatched to specialist subagents (biology, math, code, literature). Each subagent's findings are shown in a trace below the final synthesized answer."
        : "Welcome to E.sapiens. Describe your analysis goal, and I'll plan a reproducible pipeline for you.",
      timestamp: Date.now(),
    }]);
  }, [mode]);

  const handleApprove = useCallback(async () => {
    const pipelineId = agentState.last_plan
      ? (agentState.last_plan as Record<string, unknown>).id as string | undefined
      : undefined;
    if (!pipelineId) {
      setMessages((prev) => [...prev, { id: generateId(), role: "system", content: "⚠ No pipeline plan to approve. Generate a plan first.", timestamp: Date.now() }]);
      return;
    }
    setMessages((prev) => [...prev, { id: generateId(), role: "system", content: "Approving pipeline plan and dispatching to Modal sandboxes...", timestamp: Date.now() }]);
    try {
      const submitted = await api.submitPipeline(pipelineId);
      setMessages((prev) => [...prev, { id: generateId(), role: "system", content: `✅ Pipeline **${submitted.name}** approved (status: ${submitted.status}). Compute dispatched to Modal. Track live progress in the Pipeline tab or the Job Monitor.`, timestamp: Date.now() }]);
      toast.success("Pipeline approved", "Compute dispatched to Modal sandboxes");
      useSessionStore.setState((s) => ({ agentState: { ...s.agentState, approval_status: "approved" } }));
    } catch (err) {
      const errMsg = err instanceof Error ? err.message : String(err);
      toast.error("Failed to submit pipeline", errMsg);
      setMessages((prev) => [...prev, { id: generateId(), role: "system", content: `❌ Failed to submit pipeline: ${errMsg}`, timestamp: Date.now() }]);
    }
  }, [agentState.last_plan]);

  const handleModify = useCallback(() => {
    setMessages((prev) => [...prev, { id: generateId(), role: "system", content: "Switch to the **Pipeline** tab to edit step parameters, then come back and approve.", timestamp: Date.now() }]);
  }, []);

  return (
    <div className="flex h-full flex-col" style={{ background: "var(--bg-base)" }}>
      {/* ── Header ─────────────────────────────────────────────────── */}
      <div className="flex items-center justify-between px-3 py-2 border-b" style={{ borderColor: "var(--border-default)", background: "var(--bg-surface)" }}>
        <div className="flex items-center gap-2">
          <Bot className="h-4 w-4" style={{ color: "var(--accent-gold)" }} />
          <h2 className="text-xs font-semibold" style={{ color: "var(--text-primary)" }}>Agent Chat</h2>
        </div>
        <div className="flex items-center gap-2">
          <ModeToggle mode={mode} onChange={handleModeChange} disabled={supervisorDisabled} />
          <ConnectionIndicator />
        </div>
      </div>

      {/* ── Messages ────────────────────────────────────────────────── */}
      <div className="flex-1 overflow-y-auto px-3 py-3 space-y-3">
        {messages.map((msg) => <MessageBubble key={msg.id} message={msg} />)}
        {isSending && (
          <div className="flex items-center gap-2 text-xs" style={{ color: "var(--text-muted)" }}>
            <Loader2 className="h-3.5 w-3.5 animate-spin" />
            Thinking...
          </div>
        )}
        <div ref={messagesEndRef} />
      </div>

      {/* ── Approval bar ────────────────────────────────────────────── */}
      {agentState.approval_status === "pending" && (
        <div className="px-3 py-2 border-t" style={{ borderColor: "var(--border-default)", background: "var(--bg-surface)" }}>
          <p className="mb-2 text-xs font-medium" style={{ color: "var(--text-primary)" }}>
            Pipeline plan awaiting your approval:
          </p>
          <div className="flex gap-2">
            <button onClick={handleApprove} className="btn btn-primary text-xs">
              <CheckCircle2 className="h-3.5 w-3.5" />
              Approve Plan
            </button>
            <button onClick={handleModify} className="btn btn-ghost text-xs">
              <AlertCircle className="h-3.5 w-3.5" />
              Modify Parameters
            </button>
          </div>
        </div>
      )}

      {/* ── Input bar ──────────────────────────────────────────────── */}
      <div className="px-3 py-2 border-t" style={{ borderColor: "var(--border-default)", background: "var(--bg-surface)" }}>
        {mode === "supervisor" && supervisorDisabled && (
          <div className="mb-2 flex items-center gap-2 rounded-md px-2 py-1.5 text-xs" style={{ background: "rgba(245, 158, 11, 0.08)", color: "var(--accent-orange)" }}>
            <AlertCircle className="h-3 w-3 shrink-0" />
            Supervisor mode is unavailable — no LLM configured.
          </div>
        )}
        <form onSubmit={(e) => { e.preventDefault(); handleSend(); }} className="flex items-center gap-2">
          <input
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder={mode === "supervisor" ? (supervisorDisabled ? "Supervisor unavailable" : "Ask the supervisor to research\u2026") : "Describe your analysis goal..."}
            className="input flex-1"
            disabled={isSending || (mode === "supervisor" && supervisorDisabled)}
          />
          <button type="submit" disabled={isSending || !input.trim() || (mode === "supervisor" && supervisorDisabled)} className="btn btn-primary">
            <Send className="h-3.5 w-3.5" />
          </button>
        </form>
      </div>
    </div>
  );
}

function ConnectionIndicator() {
  const status = useSessionStore((s) => s.connectionStatus);
  const colors: Record<string, string> = {
    connected: "bg-accent-green",
    connecting: "bg-accent-orange animate-pulse",
    disconnected: "bg-accent-red",
    reconnecting: "bg-accent-orange animate-pulse",
  };
  const labels: Record<string, string> = {
    connected: "Connected",
    connecting: "Connecting...",
    disconnected: "Disconnected",
    reconnecting: "Reconnecting...",
  };
  return (
    <div className="flex items-center gap-1.5">
      <span className={cn("h-1.5 w-1.5 rounded-full", colors[status] ?? "bg-gray-500")} />
      <span className="text-xs" style={{ color: "var(--text-muted)" }}>{labels[status] ?? status}</span>
    </div>
  );
}

function MessageBubble({ message }: { message: ChatMessage }) {
  const [expanded, setExpanded] = useState(true);

  if (message.role === "system") {
    return (
      <div className="chat-system px-3 py-2 text-xs">
        <MarkdownRenderer content={message.content} />
      </div>
    );
  }

  const isAgent = message.role === "agent";
  const hasSupervisor = isAgent && message.supervisor && message.supervisor.subagent_results.length > 0;

  return (
    <div className={cn("flex gap-2", isAgent ? "flex-row" : "flex-row-reverse")}>
      <div className={cn("flex h-7 w-7 shrink-0 items-center justify-center rounded-full", isAgent ? "bg-surface-raised" : "bg-gold")}
        style={isAgent ? { background: "var(--bg-raised)" } : { background: "var(--accent-gold)" }}>
        {isAgent ? <Bot className="h-3.5 w-3.5" style={{ color: "var(--text-secondary)" }} /> : <User className="h-3.5 w-3.5" style={{ color: "var(--text-inverse)" }} />}
      </div>
      <div className={cn("max-w-[85%] px-3 py-2 text-sm", isAgent ? (hasSupervisor ? "chat-agent w-full max-w-full" : "chat-agent") : "chat-user")}>
        {hasSupervisor && message.supervisor && (
          <div className="mb-2 flex items-center gap-2 border-b pb-2 text-xs" style={{ borderColor: "var(--border-default)", color: "var(--text-muted)" }}>
            <Sparkles className="h-3 w-3" style={{ color: "var(--accent-gold)" }} />
            <span className="font-semibold" style={{ color: "var(--text-primary)" }}>Supervisor</span>
            <span>&middot;</span>
            <span>phase: {message.supervisor.phase}</span>
            <span>&middot;</span>
            <span>{message.supervisor.subagent_results.length} subagent(s)</span>
          </div>
        )}
        <div className="prose-chat">
          <MarkdownRenderer content={message.content} />
        </div>
        {hasSupervisor && message.supervisor && <SupervisorTrace results={message.supervisor.subagent_results} />}
        {message.traces && message.traces.length > 0 && (
          <div className="mt-2 border-t pt-2" style={{ borderColor: "var(--border-default)" }}>
            <button onClick={() => setExpanded(!expanded)} className="flex items-center gap-1 text-xs" style={{ color: "var(--text-muted)" }}>
              {expanded ? <ChevronDown className="h-3 w-3" /> : <ChevronRight className="h-3 w-3" />}
              Action traces
            </button>
            {expanded && <div className="mt-1 space-y-1">{message.traces.map((trace) => <TraceLine key={trace.step} trace={trace} />)}</div>}
          </div>
        )}
        <div className="mt-1 text-right text-[10px] opacity-50" style={{ color: "var(--text-muted)" }}>
          {formatTimestamp(new Date(message.timestamp))}
        </div>
      </div>
    </div>
  );
}

function TraceLine({ trace }: { trace: ActionTrace }) {
  const icons: Record<string, React.ReactNode> = {
    completed: <CheckCircle2 className="h-3 w-3" style={{ color: "var(--accent-green)" }} />,
    running: <Loader2 className="h-3 w-3 animate-spin" style={{ color: "var(--accent-blue)" }} />,
    pending: <div className="h-3 w-3 rounded-full border" style={{ borderColor: "var(--text-muted)" }} />,
    failed: <XCircle className="h-3 w-3" style={{ color: "var(--accent-red)" }} />,
  };
  return (
    <div className="flex items-center gap-1.5 text-xs">
      {icons[trace.status] ?? icons.pending}
      <span className="font-medium">{trace.label}</span>
      {trace.detail && <span style={{ color: "var(--text-muted)" }}>&mdash; {trace.detail}</span>}
    </div>
  );
}

function ModeToggle({ mode, onChange, disabled }: { mode: ChatMode; onChange: (m: ChatMode) => void; disabled?: boolean }) {
  return (
    <div className="segmented">
      <button type="button" onClick={() => onChange("pipeline")} className={cn("segmented-item", mode === "pipeline" && "active")}>
        <Network className="h-3 w-3" />
        Pipeline
      </button>
      <button type="button" onClick={() => !disabled && onChange("supervisor")} className={cn("segmented-item", mode === "supervisor" && "active")} disabled={disabled}>
        <Sparkles className="h-3 w-3" />
        Supervisor
      </button>
    </div>
  );
}

const SUBAGENT_META: Record<SubagentRole, { label: string; icon: React.ReactNode; accent: string }> = {
  biology: { label: "Biology", icon: <Dna className="h-4 w-4" />, accent: "text-emerald-500" },
  math: { label: "Math", icon: <Calculator className="h-4 w-4" />, accent: "text-sky-500" },
  code: { label: "Code", icon: <Code2 className="h-4 w-4" />, accent: "text-indigo-500" },
  literature: { label: "Literature", icon: <BookOpen className="h-4 w-4" />, accent: "text-rose-500" },
};

function subagentMeta(role: SubagentRole) {
  return SUBAGENT_META[role] ?? { label: role, icon: <Bot className="h-4 w-4" />, accent: "text-gray-400" };
}

function SupervisorTrace({ results }: { results: SubagentSummary[] }) {
  if (!results || results.length === 0) return null;
  return (
    <div className="mt-3">
      <div className="mb-2 flex items-center gap-1.5 text-[10px] font-semibold uppercase tracking-wider" style={{ color: "var(--text-muted)" }}>
        <Network className="h-3 w-3" />
        Subagent trace
      </div>
      <div className="relative space-y-2 border-l-2 border-dashed pl-4" style={{ borderColor: "rgba(201, 168, 76, 0.3)" }}>
        {results.map((r, idx) => <SubagentCard key={`${r.role}-${idx}`} result={r} index={idx} />)}
      </div>
    </div>
  );
}

function SubagentCard({ result, index }: { result: SubagentSummary; index: number }) {
  const [showData, setShowData] = useState(false);
  const [showCitations, setShowCitations] = useState(false);
  const meta = subagentMeta(result.role);
  const confidencePct = Math.max(0, Math.min(100, Math.round(result.confidence * 100)));
  const confidenceColor = confidencePct >= 80 ? "bg-accent-green" : confidencePct >= 50 ? "bg-accent-orange" : "bg-accent-red";

  return (
    <div className="card relative -ml-7 px-3 py-2.5 text-xs">
      <div className="absolute -left-[26px] top-3 flex h-5 w-5 items-center justify-center rounded-full" style={{ background: "var(--bg-raised)", boxShadow: "0 0 0 2px rgba(201, 168, 76, 0.3)" }}>
        {meta.icon}
      </div>
      <div className="flex items-center justify-between gap-2">
        <div className="flex items-center gap-1.5 font-semibold" style={{ color: "var(--text-primary)" }}>
          <span className={meta.accent}>{meta.icon}</span>
          <span>{meta.label}</span>
          <span style={{ color: "var(--text-muted)" }}>&middot;</span>
          <span style={{ color: "var(--text-muted)" }}>step {index + 1}</span>
        </div>
        <div className="flex items-center gap-1.5">
          <span className="text-[10px] font-medium" style={{ color: "var(--text-muted)" }}>{confidencePct}%</span>
          <div className="progress w-16">
            <div className={cn("progress-fill", confidenceColor)} style={{ width: `${confidencePct}%` }} />
          </div>
        </div>
      </div>
      {result.task && <p className="mt-1 text-[11px] italic" style={{ color: "var(--text-muted)" }}>{result.task}</p>}
      {result.findings && <p className="mt-1.5 whitespace-pre-wrap text-xs" style={{ color: "var(--text-primary)" }}>{result.findings}</p>}
      {result.structured_data && Object.keys(result.structured_data).length > 0 && (
        <div className="mt-2">
          <button type="button" onClick={() => setShowData((s) => !s)} className="flex items-center gap-1 text-[10px] font-medium" style={{ color: "var(--text-muted)" }}>
            {showData ? <ChevronDown className="h-3 w-3" /> : <ChevronRight className="h-3 w-3" />}
            Structured data
          </button>
          {showData && (
            <pre className="mt-1 max-h-48 overflow-auto rounded-md p-2 text-[10px] leading-snug" style={{ background: "rgba(0,0,0,0.3)" }}>
              <code>{JSON.stringify(result.structured_data, null, 2)}</code>
            </pre>
          )}
        </div>
      )}
      {result.citations && result.citations.length > 0 && (
        <div className="mt-2">
          <button type="button" onClick={() => setShowCitations((s) => !s)} className="flex items-center gap-1 text-[10px] font-medium" style={{ color: "var(--text-muted)" }}>
            {showCitations ? <ChevronDown className="h-3 w-3" /> : <ChevronRight className="h-3 w-3" />}
            <Quote className="h-3 w-3" />
            {result.citations.length} citation{result.citations.length === 1 ? "" : "s"}
          </button>
          {showCitations && (
            <ul className="mt-1 space-y-0.5 pl-1">
              {result.citations.map((c, i) => (
                <li key={`${c}-${i}`} className="break-all font-mono text-[10px]" style={{ color: "var(--text-secondary)" }}>&bull; {c}</li>
              ))}
            </ul>
          )}
        </div>
      )}
    </div>
  );
}