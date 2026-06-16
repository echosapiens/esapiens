"use client";

import { useQuery } from "@tanstack/react-query";
import { api, type JobSummary } from "@/lib/api";
import { cn, formatRelativeDate } from "@/lib/utils";
import {
  Activity,
  CheckCircle2,
  XCircle,
  Clock,
  Loader2,
  Server,
  ExternalLink,
} from "lucide-react";

// ── Job Monitor page ─────────────────────────────────────────────────────
// Live progress bars for all running computations. All compute is
// dispatched to Modal sandboxes — the VPS just polls the database for
// progress updates that the sandbox publish to Redis.

export default function JobMonitorPage() {
  // Poll every 2 seconds for live progress
  const { data, isLoading, error, isFetching } = useQuery({
    queryKey: ["jobs"],
    queryFn: () => api.listJobs(false),
    refetchInterval: 2000,
    refetchIntervalInBackground: true,
  });

  const active = data?.active ?? [];
  const recent = data?.recent ?? [];

  return (
    <div className="flex h-full flex-col p-6">
      {/* ── Header ─────────────────────────────────────────────── */}
      <div className="mb-6 flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-navy">Job Monitor</h1>
          <p className="mt-1 text-sm text-muted-foreground">
            Live progress for all running computations on Modal sandboxes
          </p>
        </div>
        <div className="flex items-center gap-2 text-xs text-muted-foreground">
          {isFetching && <Loader2 className="h-3.5 w-3.5 animate-spin" />}
          <span>Auto-refresh: 2s</span>
        </div>
      </div>

      {/* ── Stats row ─────────────────────────────────────────── */}
      <div className="mb-6 grid grid-cols-4 gap-3">
        <StatCard
          label="Active"
          value={data?.total_active ?? 0}
          icon={Activity}
          color="text-blue-600"
        />
        <StatCard
          label="Running"
          value={active.filter((j) => j.status === "running").length}
          icon={Loader2}
          color="text-blue-500"
        />
        <StatCard
          label="Completed (24h)"
          value={recent.filter((j) => j.status === "completed").length}
          icon={CheckCircle2}
          color="text-green-600"
        />
        <StatCard
          label="Failed (24h)"
          value={recent.filter((j) => j.status === "failed").length}
          icon={XCircle}
          color="text-red-600"
        />
      </div>

      {isLoading && (
        <div className="flex items-center justify-center py-12">
          <Loader2 className="h-6 w-6 animate-spin text-gold" />
        </div>
      )}

      {error && (
        <div className="rounded-lg border border-red-200 bg-red-50 p-4 text-sm text-red-700">
          Failed to load jobs: {String(error)}
        </div>
      )}

      {/* ── Active jobs with progress bars ────────────────────── */}
      {active.length > 0 && (
        <section className="mb-6">
          <h2 className="mb-3 text-sm font-semibold uppercase tracking-wider text-muted-foreground">
            Active Computations
          </h2>
          <div className="space-y-2">
            {active.map((job) => (
              <JobRow key={job.run_id} job={job} />
            ))}
          </div>
        </section>
      )}

      {/* ── Empty state ───────────────────────────────────────── */}
      {!isLoading && active.length === 0 && recent.length === 0 && (
        <div className="glass rounded-xl p-8 text-center">
          <Server className="mx-auto h-10 w-10 text-gold/50" />
          <h3 className="mt-3 text-sm font-medium text-navy">No jobs yet</h3>
          <p className="mt-1 text-xs text-muted-foreground">
            Run a pipeline from a session to see live progress here.
          </p>
        </div>
      )}

      {/* ── Recent jobs ───────────────────────────────────────── */}
      {recent.length > 0 && (
        <section>
          <h2 className="mb-3 text-sm font-semibold uppercase tracking-wider text-muted-foreground">
            Recent (last 50)
          </h2>
          <div className="space-y-2">
            {recent.map((job) => (
              <JobRow key={job.run_id} job={job} />
            ))}
          </div>
        </section>
      )}
    </div>
  );
}

// ── Stat card ───────────────────────────────────────────────────────────

function StatCard({
  label,
  value,
  icon: Icon,
  color,
}: {
  label: string;
  value: number;
  icon: React.ComponentType<{ className?: string }>;
  color: string;
}) {
  return (
    <div className="glass rounded-xl p-4">
      <div className="flex items-center justify-between">
        <span className="text-xs text-muted-foreground">{label}</span>
        <Icon className={cn("h-4 w-4", color)} />
      </div>
      <div className="mt-2 text-2xl font-bold text-navy">{value}</div>
    </div>
  );
}

// ── Job row with progress bar ───────────────────────────────────────────

function JobRow({ job }: { job: JobSummary }) {
  const isActive = job.status === "running" || job.status === "pending";
  const isCompleted = job.status === "completed";
  const isFailed = job.status === "failed";

  return (
    <a
      href={`/dashboard/session/${job.session_id}`}
      className="block glass rounded-xl p-4 transition-all hover:shadow-md"
    >
      <div className="flex items-start justify-between gap-4">
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2">
            <StatusBadge status={job.status} />
            <span className="truncate text-sm font-medium text-navy">
              {job.step_name}
            </span>
            <span className="text-xs text-muted-foreground">·</span>
            <span className="truncate text-xs text-muted-foreground">
              {job.pipeline_name}
            </span>
          </div>
          <div className="mt-1.5 flex items-center gap-2 text-xs text-muted-foreground">
            <span>Session: {job.session_title.slice(0, 20)}{job.session_title.length > 20 ? "…" : ""}</span>
            {job.modal_sandbox_id && (
              <>
                <span>·</span>
                <span className="font-code text-[10px]">
                  sandbox: {job.modal_sandbox_id.slice(0, 16)}…
                </span>
              </>
            )}
          </div>
        </div>
        <div className="flex shrink-0 items-center gap-2 text-right">
          <div className="text-xs text-muted-foreground">
            {job.completed_at
              ? formatRelativeDate(job.completed_at)
              : job.started_at
                ? formatRelativeDate(job.started_at)
                : formatRelativeDate(job.created_at)}
          </div>
          <ExternalLink className="h-3.5 w-3.5 text-muted-foreground" />
        </div>
      </div>

      {/* ── Progress bar ────────────────────────────────────── */}
      {isActive && (
        <div className="mt-3">
          <div className="flex items-center justify-between text-xs text-muted-foreground">
            <span>Running on Modal sandbox</span>
            <span className="font-mono font-medium text-navy">{job.progress}%</span>
          </div>
          <div className="mt-1 h-2 overflow-hidden rounded-full bg-navy-100">
            <div
              className="h-full rounded-full bg-gradient-to-r from-gold to-gold/80 transition-all duration-500 ease-out"
              style={{ width: `${job.progress}%` }}
            />
          </div>
        </div>
      )}

      {isCompleted && (
        <div className="mt-3 flex items-center gap-2 text-xs text-green-700">
          <CheckCircle2 className="h-3.5 w-3.5" />
          <span>Completed</span>
          {job.exit_code !== null && (
            <span className="font-code text-muted-foreground">
              exit_code: {job.exit_code}
            </span>
          )}
        </div>
      )}

      {isFailed && (
        <div className="mt-3 flex items-center gap-2 text-xs text-red-700">
          <XCircle className="h-3.5 w-3.5" />
          <span>Failed</span>
          {job.exit_code !== null && (
            <span className="font-code text-muted-foreground">
              exit_code: {job.exit_code}
            </span>
          )}
        </div>
      )}
    </a>
  );
}

// ── Status badge ─────────────────────────────────────────────────────────

function StatusBadge({ status }: { status: string }) {
  const config: Record<string, { icon: React.ComponentType<{ className?: string }>; color: string; label: string }> = {
    pending: { icon: Clock, color: "bg-yellow-100 text-yellow-700", label: "Pending" },
    running: { icon: Loader2, color: "bg-blue-100 text-blue-700", label: "Running" },
    completed: { icon: CheckCircle2, color: "bg-green-100 text-green-700", label: "Completed" },
    failed: { icon: XCircle, color: "bg-red-100 text-red-700", label: "Failed" },
  };
  const c = config[status] ?? config.pending;
  const Icon = c.icon;
  return (
    <span
      className={cn(
        "inline-flex shrink-0 items-center gap-1 rounded-full px-2 py-0.5 text-[10px] font-medium",
        c.color
      )}
    >
      <Icon
        className={cn("h-3 w-3", status === "running" && "animate-spin")}
      />
      {c.label}
    </span>
  );
}