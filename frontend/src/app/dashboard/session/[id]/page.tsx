"use client";

import { useParams } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { useStateSync } from "@/hooks/useStateSync";
import { useSessionStore } from "@/store/sessionStore";
import { ChatPanel } from "@/components/chat/ChatPanel";
import { WorkspaceCanvas } from "@/components/workspace/WorkspaceCanvas";
import { cn } from "@/lib/utils";
import { Loader2, AlertCircle } from "lucide-react";

// ── Session detail page ─────────────────────────────────────────────────
// Full split-pane IDE layout: ChatPanel on left, WorkspaceCanvas on right

export default function SessionDetailPage() {
  const params = useParams();
  const sessionId = params.id as string;

  // ── Sync state via REST + WebSocket ──────────────────────────────
  const { state, isLoading, error } = useStateSync(sessionId);
  const connectionStatus = useSessionStore((s) => s.connectionStatus);

  // ── Fetch session details ────────────────────────────────────────
  const { data: session } = useQuery({
    queryKey: ["session", sessionId],
    queryFn: () => api.getSession(sessionId),
  });

  // ── Loading state ────────────────────────────────────────────────
  if (isLoading && !session) {
    return (
      <div className="flex h-full items-center justify-center">
        <div className="flex flex-col items-center gap-3">
          <Loader2 className="h-8 w-8 animate-spin text-gold" />
          <p className="text-sm text-muted-foreground">Loading session...</p>
        </div>
      </div>
    );
  }

  // ── Error state ──────────────────────────────────────────────────
  if (error && !session) {
    return (
      <div className="flex h-full items-center justify-center">
        <div className="flex flex-col items-center gap-3 text-center">
          <AlertCircle className="h-8 w-8 text-red-500" />
          <p className="text-sm text-red-600">{error}</p>
          <button
            onClick={() => window.location.reload()}
            className="btn-ghost text-sm"
          >
            Retry
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="flex h-full flex-col">
      {/* ── Session header ─────────────────────────────────────────── */}
      <div className="flex items-center justify-between border-b border-border bg-white px-4 py-2">
        <div className="flex items-center gap-3">
          <h1 className="text-sm font-semibold text-navy">
            {session?.title ?? "Session"}
          </h1>
          <span
            className={cn(
              "rounded-full px-2 py-0.5 text-[10px] font-medium",
              connectionStatus === "connected"
                ? "bg-green-50 text-green-700"
                : connectionStatus === "reconnecting"
                ? "bg-yellow-50 text-yellow-700"
                : "bg-red-50 text-red-700"
            )}
          >
            {connectionStatus === "connected"
              ? "Live"
              : connectionStatus === "reconnecting"
              ? "Reconnecting..."
              : "Offline"}
          </span>
        </div>
        <div className="flex items-center gap-2 text-xs text-muted-foreground">
          <span>ID: {sessionId.slice(0, 8)}…</span>
          {state && (
            <span>• {state.pipelines.length} pipelines • {state.runs.length} runs</span>
          )}
        </div>
      </div>

      {/* ── Split-pane IDE layout ──────────────────────────────────── */}
      <div className="flex flex-1 overflow-hidden">
        {/* ── Left pane: Chat (40%) ──────────────────────────────── */}
        <div className="w-2/5 min-w-[320px] border-r border-border">
          <ChatPanel />
        </div>

        {/* ── Right pane: Workspace (60%) ────────────────────────── */}
        <div className="flex-1">
          <WorkspaceCanvas sessionId={sessionId} />
        </div>
      </div>
    </div>
  );
}