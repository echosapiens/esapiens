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

// ── Session detail page — macOS split pane ──────────────────────────────

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
        <div className="mac-card flex flex-col items-center gap-3 p-8 text-center">
          <AlertCircle className="h-8 w-8" style={{ color: "var(--mac-red)" }} />
          <p className="text-sm" style={{ color: "var(--mac-red)" }}>{error}</p>
          <button
            onClick={() => window.location.reload()}
            className="mac-btn mac-btn-ghost"
          >
            Retry
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="mac-window">
      {/* ── macOS Unified Titlebar ──────────────────────────────────── */}
      <div className="mac-titlebar">
        <div className="mac-traffic-lights">
          <div className="mac-traffic-light mac-traffic-close" title="Close" />
          <div className="mac-traffic-light mac-traffic-minimize" title="Minimize" />
          <div className="mac-traffic-light mac-traffic-zoom" title="Zoom" />
        </div>
        <div className="mac-titlebar-title">
          {session?.title ?? "Session"}
        </div>
        <div className="flex items-center gap-2 pr-2">
          <span
            className={cn(
              "mac-badge",
              connectionStatus === "connected"
                ? "mac-badge-active"
                : connectionStatus === "reconnecting"
                ? "mac-badge-pending"
                : "mac-badge-failed"
            )}
          >
            {connectionStatus === "connected"
              ? "Live"
              : connectionStatus === "reconnecting"
              ? "Reconnecting..."
              : "Offline"}
          </span>
          {state && (
            <span className="text-[11px]" style={{ color: "var(--mac-tertiary-label)" }}>
              {state.pipelines.length} pipelines · {state.runs.length} runs
            </span>
          )}
        </div>
      </div>

      {/* ── macOS Split Pane ──────────────────────────────────────────── */}
      <div className="mac-split-pane">
        {/* ── Left pane: Chat (40%) ────────────────────────────────── */}
        <div className="w-2/5 min-w-[320px]">
          <ChatPanel />
        </div>

        <div className="mac-split-divider" />

        {/* ── Right pane: Workspace (60%) ──────────────────────────── */}
        <div className="flex-1">
          <WorkspaceCanvas sessionId={sessionId} />
        </div>
      </div>
    </div>
  );
}