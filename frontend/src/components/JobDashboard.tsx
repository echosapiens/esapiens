"use client";

import { useState, useEffect, useCallback, useRef } from "react";
import JobCard from "./JobCard";
import { listJobs } from "@/lib/api";
import type { JobExecution, JobStatus } from "@/types";

const ACTIVE_STATUSES: JobStatus[] = [
  "pending",
  "researching",
  "contracting",
  "queued",
  "running",
  "streaming",
];

export default function JobDashboard() {
  const [jobs, setJobs] = useState<JobExecution[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [statusFilter, setStatusFilter] = useState<JobStatus | "all">("all");
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const hasActiveJobs = jobs.some((j) => ACTIVE_STATUSES.includes(j.status));

  const fetchJobs = useCallback(async () => {
    try {
      const data = await listJobs(50);
      setJobs(data);
      setError(null);
    } catch (err: unknown) {
      const e = err as { message?: string };
      setError(e.message ?? "Failed to fetch jobs");
    } finally {
      setLoading(false);
    }
  }, []);

  // Initial fetch
  useEffect(() => {
    fetchJobs();
  }, [fetchJobs]);

  // Poll every 5s when there are active jobs
  useEffect(() => {
    if (hasActiveJobs) {
      intervalRef.current = setInterval(fetchJobs, 5000);
    } else if (intervalRef.current) {
      clearInterval(intervalRef.current);
      intervalRef.current = null;
    }

    return () => {
      if (intervalRef.current) {
        clearInterval(intervalRef.current);
      }
    };
  }, [hasActiveJobs, fetchJobs]);

  const filteredJobs =
    statusFilter === "all"
      ? jobs
      : jobs.filter((j) => j.status === statusFilter);

  // Loading skeleton
  if (loading) {
    return (
      <div className="space-y-3">
        {[1, 2, 3, 4].map((i) => (
          <div
            key={i}
            className="bg-slate-800 border border-slate-700 rounded-lg p-4 animate-pulse"
          >
            <div className="flex items-center gap-2 mb-2">
              <div className="h-3 w-20 bg-slate-700 rounded" />
              <div className="h-5 w-16 bg-slate-700 rounded-full" />
            </div>
            <div className="h-4 w-3/4 bg-slate-700 rounded" />
          </div>
        ))}
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {/* Error banner */}
      {error && (
        <div className="p-3 bg-red-500/10 border border-red-500/30 rounded-lg text-red-400 text-sm flex items-center justify-between">
          <span>{error}</span>
          <button
            onClick={fetchJobs}
            className="text-xs text-cyan-400 hover:text-cyan-300 font-medium"
          >
            Retry
          </button>
        </div>
      )}

      {/* Status filter bar */}
      <div className="flex items-center gap-2 flex-wrap">
        <span className="text-xs text-slate-500 uppercase tracking-wider">
          Filter:
        </span>
        {(["all", ...ACTIVE_STATUSES, "completed", "failed"] as const).map(
          (s) => (
            <button
              key={s}
              onClick={() => setStatusFilter(s)}
              className={`px-2.5 py-1 rounded-full text-xs font-medium transition-colors ${
                statusFilter === s
                  ? "bg-cyan-500/20 text-cyan-300 border border-cyan-500/40"
                  : "bg-slate-800 text-slate-400 border border-slate-700 hover:border-slate-600"
              }`}
            >
              {s === "all" ? "All" : s.charAt(0).toUpperCase() + s.slice(1)}
            </button>
          )
        )}
        {hasActiveJobs && (
          <span className="ml-auto flex items-center gap-1.5 text-xs text-green-400">
            <span className="w-2 h-2 bg-green-400 rounded-full animate-pulse" />
            Live
          </span>
        )}
      </div>

      {/* Job list */}
      {filteredJobs.length === 0 ? (
        <div className="text-center py-12">
          <div className="text-4xl mb-3">🔬</div>
          <p className="text-slate-400 text-sm">
            No jobs yet. Submit your first pipeline from the home page.
          </p>
        </div>
      ) : (
        <div className="space-y-2">
          {filteredJobs.map((job) => (
            <JobCard key={job.id} job={job} />
          ))}
        </div>
      )}
    </div>
  );
}