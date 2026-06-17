"use client";

import { useState } from "react";
import Link from "next/link";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api, type SessionRead } from "@/lib/api";
import { cn, formatRelativeDate, statusColorClass } from "@/lib/utils";
import { DashboardSkeleton } from "@/components/ui/Skeleton";
import { toast } from "@/store/toastStore";
import {
  Plus,
  GitBranch,
  FlaskConical,
  Clock,
  ArrowRight,
  Trash2,
} from "lucide-react";

// ── Dashboard home page — macOS style ────────────────────────────────────

export default function DashboardPage() {
  const queryClient = useQueryClient();
  const [isNewSessionModalOpen, setIsNewSessionModalOpen] = useState(false);
  const [newSessionTitle, setNewSessionTitle] = useState("");

  const {
    data: sessions = [],
    isLoading: sessionsLoading,
  } = useQuery({
    queryKey: ["sessions"],
    queryFn: () => api.listSessions(),
  });

  const { data: grants = [] } = useQuery({
    queryKey: ["grants"],
    queryFn: () => api.listGrants(),
  });

  const createSessionMutation = useMutation({
    mutationFn: (title: string) => api.createSession({ title }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["sessions"] });
      setIsNewSessionModalOpen(false);
      setNewSessionTitle("");
      toast.success("Session created", "Ready to start planning pipelines");
    },
    onError: (err) => {
      toast.error("Failed to create session", err instanceof Error ? err.message : String(err));
    },
  });

  const deleteSessionMutation = useMutation({
    mutationFn: (id: string) => api.deleteSession(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["sessions"] });
      toast.info("Session deleted");
    },
  });

  const handleCreateSession = () => {
    const title = newSessionTitle.trim();
    if (!title) return;
    createSessionMutation.mutate(title);
  };

  return (
    <div className="flex h-full flex-col overflow-auto">
      {sessionsLoading ? (
        <DashboardSkeleton />
      ) : (
        <>
          {/* ── macOS Toolbar ──────────────────────────────────────────── */}
          <div className="mac-toolbar">
            <div className="flex items-center gap-2 flex-1">
              <h1 className="text-sm font-semibold" style={{ color: "var(--mac-label)" }}>
                Dashboard
              </h1>
              <span className="text-xs" style={{ color: "var(--mac-tertiary-label)" }}>
                {sessions.length} session{sessions.length !== 1 ? "s" : ""}
              </span>
            </div>
            <button
              onClick={() => setIsNewSessionModalOpen(true)}
              className="mac-btn mac-btn-accent"
            >
              <Plus className="h-3.5 w-3.5" />
              New Session
            </button>
          </div>

          {/* ── Quick stats ────────────────────────────────────────────── */}
          <div className="grid grid-cols-3 gap-3 px-4 py-3">
            <StatCard
              label="Active Sessions"
              value={sessions.filter((s) => s.status === "active").length}
              icon={<FlaskConical className="h-4 w-4" />}
              color="var(--brand-gold)"
            />
            <StatCard
              label="Total Pipelines"
              value={0}
              icon={<GitBranch className="h-4 w-4" />}
              color="var(--mac-blue)"
            />
            <StatCard
              label="Active Grants"
              value={grants.filter((g) => g.status === "active").length}
              icon={<Clock className="h-4 w-4" />}
              color="var(--mac-green)"
            />
          </div>

          {/* ── Sessions grid ──────────────────────────────────────────── */}
          <div className="flex-1 overflow-auto px-4 pb-4">
            <div className="mb-3 flex items-center justify-between">
              <h2 className="text-xs font-semibold uppercase tracking-wider" style={{ color: "var(--mac-secondary-label)" }}>
                Research Sessions
              </h2>
            </div>

            {sessions.length === 0 ? (
              <div className="flex flex-col items-center justify-center py-16 text-center">
                <div className="mb-3 flex h-12 w-12 items-center justify-center rounded-full" style={{ background: "rgba(201, 168, 76, 0.1)" }}>
                  <FlaskConical className="h-6 w-6" style={{ color: "var(--brand-gold)" }} />
                </div>
                <h3 className="mb-1 text-sm font-medium" style={{ color: "var(--mac-label)" }}>
                  No sessions yet
                </h3>
                <p className="mb-4 text-xs" style={{ color: "var(--mac-secondary-label)" }}>
                  Create your first research session to get started.
                </p>
                <button
                  onClick={() => setIsNewSessionModalOpen(true)}
                  className="mac-btn mac-btn-accent"
                >
                  <Plus className="h-3.5 w-3.5" />
                  New Session
                </button>
              </div>
            ) : (
              <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
                {sessions.map((session) => (
                  <SessionCard key={session.id} session={session} />
                ))}
              </div>
            )}
          </div>

          {/* ── macOS Sheet modal ─────────────────────────────────────── */}
          {isNewSessionModalOpen && (
            <div className="mac-sheet-backdrop" onClick={() => setIsNewSessionModalOpen(false)}>
              <div className="mac-sheet w-full max-w-sm p-5" onClick={(e) => e.stopPropagation()}>
                <h3 className="mb-1 text-sm font-semibold" style={{ color: "var(--mac-label)" }}>
                  Create New Session
                </h3>
                <p className="mb-4 text-xs" style={{ color: "var(--mac-secondary-label)" }}>
                  Give your research session a descriptive title.
                </p>
                <input
                  type="text"
                  value={newSessionTitle}
                  onChange={(e) => setNewSessionTitle(e.target.value)}
                  placeholder="e.g. RNA-seq differential expression"
                  className="mac-input mb-4"
                  autoFocus
                  onKeyDown={(e) => {
                    if (e.key === "Enter") handleCreateSession();
                  }}
                />
                <div className="flex items-center justify-end gap-2">
                  <button
                    onClick={() => {
                      setIsNewSessionModalOpen(false);
                      setNewSessionTitle("");
                    }}
                    className="mac-btn mac-btn-ghost"
                  >
                    Cancel
                  </button>
                  <button
                    onClick={handleCreateSession}
                    disabled={!newSessionTitle.trim() || createSessionMutation.isPending}
                    className="mac-btn mac-btn-accent"
                  >
                    {createSessionMutation.isPending ? "Creating..." : "Create"}
                  </button>
                </div>
              </div>
            </div>
          )}
        </>
      )}
    </div>
  );
}

// ── Stat card ────────────────────────────────────────────────────────────

function StatCard({
  label,
  value,
  icon,
  color,
}: {
  label: string;
  value: number;
  icon: React.ReactNode;
  color: string;
}) {
  return (
    <div className="mac-card flex items-center gap-3 px-4 py-3">
      <div
        className="flex h-9 w-9 items-center justify-center rounded-lg"
        style={{ background: `${color}12` }}
      >
        <div style={{ color }}>{icon}</div>
      </div>
      <div>
        <p className="text-lg font-bold" style={{ color: "var(--mac-label)" }}>{value}</p>
        <p className="text-[11px]" style={{ color: "var(--mac-secondary-label)" }}>{label}</p>
      </div>
    </div>
  );
}

// ── Session card ─────────────────────────────────────────────────────────

function SessionCard({ session }: { session: SessionRead }) {
  const queryClient = useQueryClient();

  const deleteMutation = useMutation({
    mutationFn: () => api.deleteSession(session.id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["sessions"] });
    },
  });

  return (
    <div className="mac-card mac-card-interactive flex flex-col justify-between p-4">
      <div>
        <div className="mb-1 flex items-center justify-between">
          <h3 className="text-sm font-semibold truncate" style={{ color: "var(--mac-label)" }}>
            {session.title}
          </h3>
          <span
            className={cn(
              "mac-badge",
              statusColorClass(session.status)
                .replace("status-draft", "mac-badge-draft")
                .replace("status-submitted", "mac-badge-submitted")
                .replace("status-pending", "mac-badge-pending")
                .replace("status-running", "mac-badge-running")
                .replace("status-completed", "mac-badge-completed")
                .replace("status-failed", "mac-badge-failed")
                .replace("status-active", "mac-badge-active")
                .replace("status-archived", "mac-badge-archived")
            )}
          >
            {session.status}
          </span>
        </div>
        <p className="text-[11px]" style={{ color: "var(--mac-tertiary-label)" }}>
          Created {formatRelativeDate(session.created_at)}
        </p>
      </div>
      <div className="mt-3 flex items-center justify-between">
        <Link
          href={`/dashboard/session/${session.id}`}
          className="mac-btn mac-btn-primary text-xs"
        >
          Open
          <ArrowRight className="h-3 w-3" />
        </Link>
        <button
          onClick={() => deleteMutation.mutate()}
          className="text-xs opacity-0 group-hover:opacity-100 transition-opacity"
          style={{ color: "var(--mac-tertiary-label)" }}
          title="Delete session"
        >
          <Trash2 className="h-3.5 w-3.5" />
        </button>
      </div>
    </div>
  );
}