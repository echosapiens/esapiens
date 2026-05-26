import { useState, useEffect, useCallback } from "react";
import { Text, Badge, Progress, ActionIcon, Tooltip, ScrollArea, Divider } from "@mantine/core";
import { IconX, IconRefresh, IconCheck, IconAlertTriangle, IconLoader2, IconClock } from "@tabler/icons-react";

interface Job {
  job_id: string;
  tool: string;
  name: string;
  command: string;
  status: "running" | "completed" | "failed" | "unknown";
  start_time: number;
  end_time: number | null;
  exit_code: number | null;
  result_preview: string | null;
  error: string | null;
}

interface JobMonitorProps {
  opened: boolean;
  onClose: () => void;
}

function formatElapsed(start: number, end: number | null): string {
  const secs = Math.floor((end ?? Date.now() / 1000) - start);
  if (secs < 60) return `${secs}s`;
  if (secs < 3600) return `${Math.floor(secs / 60)}m ${secs % 60}s`;
  return `${Math.floor(secs / 3600)}h ${Math.floor((secs % 3600) / 60)}m`;
}

function statusConfig(status: string) {
  switch (status) {
    case "running":
      return { color: "cyan", icon: IconLoader2, label: "Running" };
    case "completed":
      return { color: "green", icon: IconCheck, label: "Completed" };
    case "failed":
      return { color: "red", icon: IconAlertTriangle, label: "Failed" };
    default:
      return { color: "gray", icon: IconClock, label: "Unknown" };
  }
}

function StatusBadge({ status }: { status: string }) {
  const { color, icon: Icon, label } = statusConfig(status);
  return (
    <Badge
      size="xs"
      variant="light"
      color={color}
      leftSection={<Icon size={10} style={{ animation: status === "running" ? "spin 1s linear infinite" : undefined }} />}
      style={{ animation: status === "running" ? "spin 1s linear infinite" : undefined }}
    >
      {label}
    </Badge>
  );
}

function JobRow({ job, onRefresh }: { job: Job; onRefresh: (job_id: string) => void }) {
  const { color, icon: Icon } = statusConfig(job.status);
  const elapsed = formatElapsed(job.start_time, job.end_time);

  return (
    <div style={{
      padding: "12px 16px",
      borderBottom: "1px solid var(--e-border)",
      display: "flex",
      flexDirection: "column",
      gap: 6,
    }}>
      {/* Header row */}
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
          <Icon size={14} style={{ color: `var(--mantine-color-${color}-6)` }} />
          <Text style={{ fontSize: "0.7rem", fontWeight: 600, color: "var(--e-text-primary)" }}>
            {job.name || job.tool}
          </Text>
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
          <Text style={{ fontSize: "0.6rem", color: "var(--e-text-muted)" }}>
            {elapsed}
          </Text>
          <StatusBadge status={job.status} />
        </div>
      </div>

      {/* Tool name */}
      <Text style={{ fontSize: "0.6rem", color: "var(--e-text-muted)" }}>
        {job.tool}
      </Text>

      {/* Exit code / result preview */}
      {job.status === "completed" && job.result_preview && (
        <Text style={{ fontSize: "0.6rem", color: "var(--mantine-color-green-6)" }}>
          {job.result_preview}
        </Text>
      )}

      {/* Error message */}
      {job.status === "failed" && job.error && (
        <Text style={{ fontSize: "0.6rem", color: "var(--mantine-color-red-5)" }}>
          {job.error}
        </Text>
      )}

      {/* Exit code */}
      {job.exit_code !== null && (
        <Text style={{ fontSize: "0.55rem", color: job.exit_code === 0 ? "var(--mantine-color-green-6)" : "var(--mantine-color-red-5)" }}>
          exit code: {job.exit_code}
        </Text>
      )}
    </div>
  );
}

export function JobMonitor({ opened, onClose }: JobMonitorProps) {
  const [jobs, setJobs] = useState<Job[]>([]);
  const [loading, setLoading] = useState(false);
  const [filter, setFilter] = useState<"all" | "running" | "completed" | "failed">("all");

  const fetchJobs = useCallback(async () => {
    setLoading(true);
    try {
      const token = localStorage.getItem("esapiens_token");
      const params = filter !== "all" ? `?status=${filter}` : "";
      const res = await fetch(`/api/jobs${params}`, {
        headers: token ? { Authorization: `Bearer ${token}` } : {},
      });
      if (res.ok) {
        const data = await res.json();
        setJobs(data);
      }
    } catch {
      // silent
    } finally {
      setLoading(false);
    }
  }, [filter]);

  useEffect(() => {
    if (opened) fetchJobs();
  }, [opened, fetchJobs]);

  // Auto-refresh running jobs every 3s
  useEffect(() => {
    if (!opened) return;
    const hasRunning = jobs.some((j) => j.status === "running");
    if (!hasRunning) return;
    const id = setInterval(fetchJobs, 3000);
    return () => clearInterval(id);
  }, [opened, jobs, fetchJobs]);

  if (!opened) return null;

  const runningCount = jobs.filter((j) => j.status === "running").length;
  const completedCount = jobs.filter((j) => j.status === "completed").length;
  const failedCount = jobs.filter((j) => j.status === "failed").length;

  return (
    <div style={{
      position: "fixed",
      top: 0,
      right: 0,
      width: 420,
      height: "100dvh",
      backgroundColor: "var(--e-bg-surface)",
      borderLeft: "1px solid var(--e-border)",
      boxShadow: "var(--e-shadow-xl)",
      display: "flex",
      flexDirection: "column",
      zIndex: 200,
    }}>
      {/* Header */}
      <div style={{
        padding: "16px 20px",
        borderBottom: "1px solid var(--e-border)",
        display: "flex",
        alignItems: "center",
        justifyContent: "space-between",
        flexShrink: 0,
      }}>
        <div>
          <Text style={{ fontSize: "0.85rem", fontWeight: 700, color: "var(--e-text-primary)", letterSpacing: "0.02em" }}>
            Job Monitor
          </Text>
          <div style={{ display: "flex", gap: 8, marginTop: 4 }}>
            {runningCount > 0 && <Badge size="xs" color="cyan" variant="light">{runningCount} running</Badge>}
            {completedCount > 0 && <Badge size="xs" color="green" variant="light">{completedCount} done</Badge>}
            {failedCount > 0 && <Badge size="xs" color="red" variant="light">{failedCount} failed</Badge>}
          </div>
        </div>
        <div style={{ display: "flex", gap: 4 }}>
          <Tooltip label="Refresh">
            <ActionIcon variant="subtle" color="gray" onClick={fetchJobs} size="lg">
              <IconRefresh size={16} />
            </ActionIcon>
          </Tooltip>
          <ActionIcon variant="subtle" color="gray" onClick={onClose} size="lg">
            <IconX size={16} />
          </ActionIcon>
        </div>
      </div>

      {/* Filter tabs */}
      <div style={{
        display: "flex",
        borderBottom: "1px solid var(--e-border)",
        flexShrink: 0,
      }}>
        {(["all", "running", "completed", "failed"] as const).map((f) => (
          <div
            key={f}
            onClick={() => setFilter(f)}
            style={{
              flex: 1,
              padding: "8px 4px",
              textAlign: "center",
              cursor: "pointer",
              borderBottom: filter === f ? "2px solid var(--e-accent-cyan)" : "2px solid transparent",
              backgroundColor: filter === f ? "var(--e-bg-subtle)" : "transparent",
              transition: "all 0.15s",
            }}
          >
            <Text style={{
              fontSize: "0.6rem",
              fontWeight: filter === f ? 700 : 400,
              textTransform: "capitalize",
              color: filter === f ? "var(--e-text-primary)" : "var(--e-text-muted)",
            }}>
              {f}
            </Text>
          </div>
        ))}
      </div>

      {/* Job list */}
      <ScrollArea style={{ flex: 1 }}>
        {loading && jobs.length === 0 ? (
          <div style={{ padding: "40px 20px", textAlign: "center" }}>
            <IconLoader2 size={24} style={{ color: "var(--e-text-muted)", animation: "spin 1s linear infinite" }} />
          </div>
        ) : jobs.length === 0 ? (
          <div style={{ padding: "40px 20px", textAlign: "center" }}>
            <IconClock size={24} style={{ color: "var(--e-text-muted)" }} />
            <Text style={{ fontSize: "0.7rem", color: "var(--e-text-muted)", marginTop: 8 }}>
              {filter === "all" ? "No background jobs yet" : `No ${filter} jobs`}
            </Text>
            <Text style={{ fontSize: "0.55rem", color: "var(--e-text-muted)", marginTop: 4 }}>
              Long-running tasks (e.g. bio pipelines) will appear here
            </Text>
          </div>
        ) : (
          jobs.map((job) => <JobRow key={job.job_id} job={job} onRefresh={fetchJobs} />)
        )}
      </ScrollArea>

      {/* Footer */}
      <div style={{
        padding: "10px 20px",
        borderTop: "1px solid var(--e-border)",
        flexShrink: 0,
      }}>
        <Text style={{ fontSize: "0.55rem", color: "var(--e-text-muted)", textAlign: "center" }}>
          Auto-refreshes every 3s while jobs are running — Ctrl+J to toggle
        </Text>
      </div>

      <style>{`
        @keyframes spin { from { transform: rotate(0deg); } to { transform: rotate(360deg); } }
      `}</style>
    </div>
  );
}
