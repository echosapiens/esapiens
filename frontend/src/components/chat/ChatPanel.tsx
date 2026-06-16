"use client";

import { useState, useRef, useEffect, useCallback } from "react";
import { useSessionStore } from "@/store/sessionStore";
import { cn, formatTimestamp, generateId } from "@/lib/utils";
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
} from "lucide-react";
import type { LogEntry } from "@/types/events";

// ── Types ───────────────────────────────────────────────────────────────

interface ChatMessage {
  id: string;
  role: "user" | "agent" | "system";
  content: string;
  timestamp: number;
  traces?: ActionTrace[];
}

interface ActionTrace {
  step: string;
  label: string;
  status: "pending" | "running" | "completed" | "failed";
  detail?: string;
}

// ── ChatPanel ────────────────────────────────────────────────────────────

export function ChatPanel() {
  const [messages, setMessages] = useState<ChatMessage[]>([
    {
      id: "welcome",
      role: "system",
      content:
        "Welcome to E.sapiens. Describe your analysis goal, and I'll plan a reproducible pipeline for you.",
      timestamp: Date.now(),
    },
  ]);
  const [input, setInput] = useState("");
  const [isSending, setIsSending] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const agentState = useSessionStore((s) => s.agentState);
  const logs = useSessionStore((s) => s.logs);

  // ── Auto-scroll on new messages ────────────────────────────────────
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, logs]);

  // ── When agent plan is generated, add a message ──────────────────
  useEffect(() => {
    if (agentState.last_plan && agentState.approval_status === "pending") {
      const planName =
        (agentState.last_plan as Record<string, unknown>)?.name as string ||
        "Pipeline Plan";
      setMessages((prev) => {
        const already = prev.some((m) => m.id === "plan-pending");
        if (already) return prev;
        return [
          ...prev,
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
    }
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
  const handleSend = useCallback(() => {
    const text = input.trim();
    if (!text || isSending) return;

    const userMsg: ChatMessage = {
      id: generateId(),
      role: "user",
      content: text,
      timestamp: Date.now(),
    };
    setMessages((prev) => [...prev, userMsg]);
    setInput("");
    setIsSending(true);

    // TODO: Replace with actual API call to send message to agent
    setTimeout(() => {
      setMessages((prev) => [
        ...prev,
        {
          id: generateId(),
          role: "agent",
          content:
            "I'll analyze your request and generate a pipeline plan. Check the Pipeline tab for details.",
          timestamp: Date.now(),
        },
      ]);
      setIsSending(false);
    }, 1500);
  }, [input, isSending]);

  // ── Approval handlers ─────────────────────────────────────────────
  const handleApprove = useCallback(() => {
    setMessages((prev) => [
      ...prev,
      {
        id: generateId(),
        role: "system",
        content: "✅ Pipeline plan approved. Submitting for execution...",
        timestamp: Date.now(),
      },
    ]);
  }, []);

  const handleModify = useCallback(() => {
    setMessages((prev) => [
      ...prev,
      {
        id: generateId(),
        role: "system",
        content: "You can modify parameters in the Pipeline tab. Make your changes and then approve.",
        timestamp: Date.now(),
      },
    ]);
  }, []);

  // ── Render ─────────────────────────────────────────────────────────
  return (
    <div className="flex h-full flex-col bg-cream">
      {/* ── Header ─────────────────────────────────────────────────── */}
      <div className="flex items-center justify-between border-b border-border px-4 py-3">
        <div className="flex items-center gap-2">
          <Bot className="h-5 w-5 text-gold" />
          <h2 className="text-sm font-semibold text-navy">Agent Chat</h2>
        </div>
        <div className="flex items-center gap-2">
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
        <div className="border-t border-border bg-cream-200 px-4 py-3">
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
      <div className="border-t border-border px-4 py-3">
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
            placeholder="Describe your analysis goal..."
            className="input-base flex-1"
            disabled={isSending}
          />
          <button
            type="submit"
            disabled={isSending || !input.trim()}
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
      <div className="rounded-md border border-gold/20 bg-gold/5 px-3 py-2 text-xs text-navy-700">
        {message.content}
      </div>
    );
  }

  const isAgent = message.role === "agent";

  return (
    <div
      className={cn("flex gap-3", isAgent ? "flex-row" : "flex-row-reverse")}
    >
      <div
        className={cn(
          "flex h-8 w-8 shrink-0 items-center justify-center rounded-full",
          isAgent ? "bg-navy text-white" : "bg-gold text-navy"
        )}
      >
        {isAgent ? <Bot className="h-4 w-4" /> : <User className="h-4 w-4" />}
      </div>
      <div
        className={cn(
          "max-w-[80%] rounded-lg px-3 py-2 text-sm",
          isAgent
            ? "bg-white border border-border text-navy"
            : "bg-navy text-white"
        )}
      >
        <p className="whitespace-pre-wrap">{message.content}</p>
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