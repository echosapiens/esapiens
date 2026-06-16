"use client";

import { useState } from "react";
import Link from "next/link";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api, type SessionRead } from "@/lib/api";
import { cn, formatRelativeDate, statusColorClass } from "@/lib/utils";
import {
  Plus,
  GitBranch,
  FlaskConical,
  Clock,
  ArrowRight,
  Loader2,
  Trash2,
} from "lucide-react";

// ── Dashboard home page ─────────────────────────────────────────────────

export default function DashboardPage() {
  const queryClient = useQueryClient();
  const [isNewSessionModalOpen, setIsNewSessionModalOpen] = useState(false);
  const [newSessionTitle, setNewSessionTitle] = useState("");

  // ── Fetch sessions ───────────────────────────────────────────────
  const {
    data: sessions = [],
    isLoading: sessionsLoading,
  } = useQuery({
    queryKey: ["sessions"],
    queryFn: () => api.listSessions(),
  });

  // ── Fetch grants ─────────────────────────────────────────────────
  const { data: grants = [] } = useQuery({
    queryKey: ["grants"],
    queryFn: () => api.listGrants(),
  });

  // ── Create session mutation ──────────────────────────────────────
  const createSessionMutation = useMutation({
    mutationFn: (title: string) => api.createSession({ title }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["sessions"] });
      setIsNewSessionModalOpen(false);
      setNewSessionTitle("");
    },
  });

  // ── Delete session mutation ──────────────────────────────────────
  const deleteSessionMutation = useMutation({
    mutationFn: (id: string) => api.deleteSession(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["sessions"] });
    },
  });

  const handleCreateSession = () => {
    const title = newSessionTitle.trim();
    if (!title) return;
    createSessionMutation.mutate(title);
  };

  return (
    <div className="flex h-full flex-col overflow-auto">
      {/* ── Header ─────────────────────────────────────────────────── */}
      <div className="glass-heavy flex items-center justify-between border-b border-border px-6 py-4">
        <div>
          <h1 className="text-2xl font-bold text-navy">Dashboard</h1>
          <p className="text-sm text-muted-foreground">
            Manage your research sessions and pipelines
          </p>
        </div>
        <button
          onClick={() => setIsNewSessionModalOpen(true)}
          className="btn-accent inline-flex items-center gap-2"
        >
          <Plus className="h-4 w-4" />
          New Session
        </button>
      </div>

      {/* ── Quick stats ────────────────────────────────────────────── */}
      <div className="grid grid-cols-3 gap-4 border-b border-border px-6 py-4">
        <StatCard
          label="Active Sessions"
          value={sessions.filter((s) => s.status === "active").length}
          icon={<FlaskConical className="h-5 w-5 text-gold" />}
        />
        <StatCard
          label="Total Pipelines"
          value={0}
          icon={<GitBranch className="h-5 w-5 text-blue-500" />}
        />
        <StatCard
          label="Active Grants"
          value={grants.filter((g) => g.status === "active").length}
          icon={<Clock className="h-5 w-5 text-green-500" />}
        />
      </div>

      {/* ── Sessions grid ──────────────────────────────────────────── */}
      <div className="flex-1 overflow-auto p-6">
        <div className="mb-4 flex items-center justify-between">
          <h2 className="text-lg font-semibold text-navy">Research Sessions</h2>
        </div>

        {sessionsLoading ? (
          <div className="flex items-center justify-center py-12">
            <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
          </div>
        ) : sessions.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-16 text-center">
            <div className="mb-4 flex h-16 w-16 items-center justify-center rounded-2xl bg-cream-200">
              <FlaskConical className="h-8 w-8 text-muted-foreground" />
            </div>
            <h3 className="mb-2 text-lg font-medium text-navy">
              No sessions yet
            </h3>
            <p className="mb-4 text-sm text-muted-foreground">
              Create your first research session to get started.
            </p>
            <button
              onClick={() => setIsNewSessionModalOpen(true)}
              className="btn-accent inline-flex items-center gap-2"
            >
              <Plus className="h-4 w-4" />
              New Session
            </button>
          </div>
        ) : (
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {sessions.map((session) => (
              <SessionCard key={session.id} session={session} />
            ))}
          </div>
        )}
      </div>

      {/* ── New session modal ───────────────────────────────────────── */}
      {isNewSessionModalOpen && (
        <div className="glass-modal-backdrop fixed inset-0 z-50 flex items-center justify-center">
          <div className="glass-heavy w-full max-w-md p-6 rounded-2xl">
            <h3 className="mb-4 text-lg font-semibold text-navy">
              Create New Session
            </h3>
            <input
              type="text"
              value={newSessionTitle}
              onChange={(e) => setNewSessionTitle(e.target.value)}
              placeholder="Session title..."
              className="input-base mb-4"
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
                className="btn-ghost"
              >
                Cancel
              </button>
              <button
                onClick={handleCreateSession}
                disabled={!newSessionTitle.trim() || createSessionMutation.isPending}
                className="btn-accent"
              >
                {createSessionMutation.isPending ? "Creating..." : "Create"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

// ── Stat card ────────────────────────────────────────────────────────────

function StatCard({
  label,
  value,
  icon,
}: {
  label: string;
  value: number;
  icon: React.ReactNode;
}) {
  return (
    <div className="glass flex items-center gap-3 px-4 py-3 rounded-xl">
      <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-cream-200">
        {icon}
      </div>
      <div>
        <p className="text-2xl font-bold text-navy">{value}</p>
        <p className="text-xs text-muted-foreground">{label}</p>
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
    <div className="glass group flex flex-col justify-between p-5 rounded-xl transition-all hover:shadow-lg hover:-translate-y-0.5">
      <div>
        <div className="mb-2 flex items-center justify-between">
          <h3 className="text-base font-semibold text-navy truncate">
            {session.title}
          </h3>
          <span
            className={cn(
              "rounded-full px-2 py-0.5 text-[10px] font-medium",
              statusColorClass(session.status)
            )}
          >
            {session.status}
          </span>
        </div>
        <p className="text-xs text-muted-foreground">
          Created {formatRelativeDate(session.created_at)}
        </p>
      </div>
      <div className="mt-4 flex items-center justify-between">
        <Link
          href={`/dashboard/session/${session.id}`}
          className="btn-primary inline-flex items-center gap-1 text-sm"
        >
          Open
          <ArrowRight className="h-3.5 w-3.5" />
        </Link>
        <button
          onClick={() => deleteMutation.mutate()}
          className="text-muted-foreground hover:text-red-500 opacity-0 group-hover:opacity-100 transition-opacity"
          title="Delete session"
        >
          <Trash2 className="h-4 w-4" />
        </button>
      </div>
    </div>
  );
}