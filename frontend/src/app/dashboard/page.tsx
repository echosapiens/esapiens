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
          {/* ── Top bar ──────────────────────────────────────────────── */}
          <div className="topbar">
            <div className="flex items-center gap-3 flex-1">
              <h1 className="topbar-title">Dashboard</h1>
              <span className="topbar-subtitle">
                {sessions.length} session{sessions.length !== 1 ? "s" : ""}
              </span>
            </div>
            <button
              onClick={() => setIsNewSessionModalOpen(true)}
              className="btn btn-primary"
            >
              <Plus className="h-3.5 w-3.5" />
              New Session
            </button>
          </div>

          {/* ── Quick stats ──────────────────────────────────────────── */}
          <div className="grid grid-cols-3 gap-3 px-4 py-3">
            <StatCard
              label="Active Sessions"
              value={sessions.filter((s) => s.status === "active").length}
              icon={<FlaskConical className="h-4 w-4" />}
              color="var(--accent-gold)"
            />
            <StatCard
              label="Total Pipelines"
              value={0}
              icon={<GitBranch className="h-4 w-4" />}
              color="var(--accent-blue)"
            />
            <StatCard
              label="Active Grants"
              value={grants.filter((g) => g.status === "active").length}
              icon={<Clock className="h-4 w-4" />}
              color="var(--accent-green)"
            />
          </div>

          {/* ── Sessions grid ────────────────────────────────────────── */}
          <div className="flex-1 overflow-auto px-4 pb-4">
            <div className="mb-3 flex items-center justify-between">
              <h2 className="text-xs font-semibold uppercase tracking-wider" style={{ color: "var(--text-muted)" }}>
                Research Sessions
              </h2>
            </div>

            {sessions.length === 0 ? (
              <div className="flex flex-col items-center justify-center py-16 text-center">
                <div className="mb-3 flex h-12 w-12 items-center justify-center rounded-full" style={{ background: "var(--brand-gold-dim)" }}>
                  <FlaskConical className="h-6 w-6" style={{ color: "var(--accent-gold)" }} />
                </div>
                <h3 className="mb-1 text-sm font-medium" style={{ color: "var(--text-primary)" }}>
                  No sessions yet
                </h3>
                <p className="mb-4 text-xs" style={{ color: "var(--text-muted)" }}>
                  Create your first research session to get started.
                </p>
                <button
                  onClick={() => setIsNewSessionModalOpen(true)}
                  className="btn btn-primary"
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

          {/* ── Modal ────────────────────────────────────────────────── */}
          {isNewSessionModalOpen && (
            <div className="modal-backdrop" onClick={() => setIsNewSessionModalOpen(false)}>
              <div className="modal w-full max-w-sm p-5" onClick={(e) => e.stopPropagation()}>
                <h3 className="mb-1 text-sm font-semibold" style={{ color: "var(--text-primary)" }}>
                  Create New Session
                </h3>
                <p className="mb-4 text-xs" style={{ color: "var(--text-muted)" }}>
                  Give your research session a descriptive title.
                </p>
                <input
                  type="text"
                  value={newSessionTitle}
                  onChange={(e) => setNewSessionTitle(e.target.value)}
                  placeholder="e.g. RNA-seq differential expression"
                  className="input mb-4"
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
                    className="btn btn-ghost"
                  >
                    Cancel
                  </button>
                  <button
                    onClick={handleCreateSession}
                    disabled={!newSessionTitle.trim() || createSessionMutation.isPending}
                    className="btn btn-primary"
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
    <div className="card flex items-center gap-3 px-4 py-3">
      <div
        className="flex h-9 w-9 items-center justify-center rounded-lg"
        style={{ background: `${color}15` }}
      >
        <div style={{ color }}>{icon}</div>
      </div>
      <div>
        <p className="text-lg font-bold" style={{ color: "var(--text-primary)" }}>{value}</p>
        <p className="text-xs" style={{ color: "var(--text-muted)" }}>{label}</p>
      </div>
    </div>
  );
}

function SessionCard({ session }: { session: SessionRead }) {
  const queryClient = useQueryClient();

  const deleteMutation = useMutation({
    mutationFn: () => api.deleteSession(session.id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["sessions"] });
    },
  });

  return (
    <div className="card card-interactive flex flex-col justify-between p-4">
      <div>
        <div className="mb-1 flex items-center justify-between">
          <h3 className="text-sm font-semibold truncate" style={{ color: "var(--text-primary)" }}>
            {session.title}
          </h3>
          <span
            className={cn(
              "badge",
              statusColorClass(session.status)
                .replace("status-draft", "badge-draft")
                .replace("status-submitted", "badge-submitted")
                .replace("status-pending", "badge-pending")
                .replace("status-running", "badge-running")
                .replace("status-completed", "badge-completed")
                .replace("status-failed", "badge-failed")
                .replace("status-active", "badge-active")
                .replace("status-archived", "badge-archived")
            )}
          >
            {session.status}
          </span>
        </div>
        <p className="text-xs" style={{ color: "var(--text-muted)" }}>
          Created {formatRelativeDate(session.created_at)}
        </p>
      </div>
      <div className="mt-3 flex items-center justify-between">
        <Link
          href={`/dashboard/session/${session.id}`}
          className="btn btn-primary text-xs"
        >
          Open
          <ArrowRight className="h-3 w-3" />
        </Link>
        <button
          onClick={() => deleteMutation.mutate()}
          className="opacity-0 group-hover:opacity-100 transition-opacity"
          style={{ color: "var(--text-muted)" }}
          title="Delete session"
        >
          <Trash2 className="h-3.5 w-3.5" />
        </button>
      </div>
    </div>
  );
}