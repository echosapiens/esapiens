"use client";

import { useParams } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { useStateSync } from "@/hooks/useStateSync";
import { useSessionStore } from "@/store/sessionStore";
import { ChatPanel } from "@/components/chat/ChatPanel";
import { WorkspaceCanvas } from "@/components/workspace/WorkspaceCanvas";
import { SessionSkeleton } from "@/components/ui/Skeleton";
import { cn } from "@/lib/utils";
import { AlertCircle } from "lucide-react";

export default function SessionDetailPage() {
  const params = useParams();
  const sessionId = params.id as string;

  const { state, isLoading, error } = useStateSync(sessionId);
  const connectionStatus = useSessionStore((s) => s.connectionStatus);

  const { data: session } = useQuery({
    queryKey: ["session", sessionId],
    queryFn: () => api.getSession(sessionId),
  });

  if (isLoading && !session) {
    return <SessionSkeleton />;
  }

  if (error && !session) {
    return (
      <div className="flex h-full items-center justify-center">
        <div className="card flex flex-col items-center gap-3 p-8 text-center">
          <AlertCircle className="h-8 w-8" style={{ color: "var(--accent-red)" }} />
          <p className="text-sm" style={{ color: "var(--accent-red)" }}>{error}</p>
          <button onClick={() => window.location.reload()} className="btn btn-ghost">
            Retry
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="flex h-full flex-col" style={{ background: "var(--bg-base)" }}>
      {/* ── Top bar ──────────────────────────────────────────────────── */}
      <div className="topbar">
        <div className="flex items-center gap-3 flex-1 min-w-0">
          <h1 className="topbar-title">{session?.title ?? "Session"}</h1>
          <span
            className={cn(
              "badge",
              connectionStatus === "connected"
                ? "badge-active"
                : connectionStatus === "reconnecting"
                ? "badge-pending"
                : "badge-failed"
            )}
          >
            {connectionStatus === "connected"
              ? "Live"
              : connectionStatus === "reconnecting"
              ? "Reconnecting..."
              : "Offline"}
          </span>
        </div>
        <div className="flex items-center gap-2 text-xs" style={{ color: "var(--text-muted)" }}>
          <span>ID: {sessionId.slice(0, 8)}&hellip;</span>
          {state && (
            <span>&middot; {state.pipelines.length} pipelines &middot; {state.runs.length} runs</span>
          )}
        </div>
      </div>

      {/* ── Split pane ────────────────────────────────────────────────── */}
      <div className="flex flex-1 overflow-hidden">
        {/* ── Left: Chat (40%) ────────────────────────────────────── */}
        <div className="w-2/5 min-w-[320px]" style={{ borderRight: "1px solid var(--border-default)" }}>
          <ChatPanel />
        </div>

        {/* ── Right: Workspace (60%) ───────────────────────────────── */}
        <div className="flex-1">
          <WorkspaceCanvas sessionId={sessionId} />
        </div>
      </div>
    </div>
  );
}