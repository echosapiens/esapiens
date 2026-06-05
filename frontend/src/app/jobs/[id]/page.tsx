"use client";

import { useState, useEffect } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import StatusBadge from "@/components/StatusBadge";
import CostPreview from "@/components/CostPreview";
import ResultsViewer from "@/components/ResultsViewer";
import { getJob } from "@/lib/api";
import type { JobExecution } from "@/types";

const PHASE_ORDER = [
  "pending",
  "researching",
  "contracting",
  "queued",
  "running",
  "streaming",
  "completed",
] as const;

const PHASE_LABELS: Record<string, string> = {
  pending: "Pending",
  researching: "Researching",
  contracting: "Contracting",
  queued: "Queued",
  running: "Running",
  streaming: "Streaming",
  completed: "Completed",
};

export default function JobDetailPage() {
  const params = useParams();
  const jobId = params.id as string;

  const [job, setJob] = useState<JobExecution | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;

    const fetchJob = async () => {
      try {
        const data = await getJob(jobId);
        if (!cancelled) {
          setJob(data);
          setError(null);
        }
      } catch (err: unknown) {
        const e = err as { status?: number; message?: string };
        if (!cancelled) {
          if (e.status === 404) {
            setError("Job not found");
          } else {
            setError(e.message ?? "Failed to fetch job");
          }
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    };

    fetchJob();

    // Poll if active
    const activeStatuses = [
      "pending",
      "researching",
      "contracting",
      "queued",
      "running",
      "streaming",
    ];

    const interval = setInterval(async () => {
      const data = await getJob(jobId);
      if (!cancelled) {
        setJob(data);
        if (!activeStatuses.includes(data.status)) {
          clearInterval(interval);
        }
      }
    }, 5000);

    return () => {
      cancelled = true;
      clearInterval(interval);
    };
  }, [jobId]);

  if (loading) {
    return (
      <div className="max-w-3xl mx-auto px-4 py-8">
        <div className="animate-pulse space-y-4">
          <div className="h-8 w-48 bg-slate-800 rounded" />
          <div className="h-4 w-32 bg-slate-800 rounded" />
          <div className="h-32 bg-slate-800 rounded-lg" />
          <div className="h-64 bg-slate-800 rounded-lg" />
        </div>
      </div>
    );
  }

  if (error || !job) {
    return (
      <div className="max-w-3xl mx-auto px-4 py-8">
        <div className="text-center py-12">
          <div className="text-4xl mb-3">
            {error === "Job not found" ? "🔍" : "⚠️"}
          </div>
          <h2 className="text-lg font-semibold text-slate-200 mb-2">
            {error === "Job not found"
              ? "Job Not Found"
              : "Error Loading Job"}
          </h2>
          <p className="text-sm text-slate-400 mb-4">
            {error ?? "An unexpected error occurred."}
          </p>
          <Link
            href="/dashboard"
            className="text-sm text-cyan-400 hover:text-cyan-300 font-medium"
          >
            ← Back to Dashboard
          </Link>
        </div>
      </div>
    );
  }

  const currentPhaseIndex = PHASE_ORDER.indexOf(
    job.status === "failed" ? "completed" : job.status
  );
  const isFailed = job.status === "failed";

  return (
    <div className="max-w-3xl mx-auto px-4 py-8">
      {/* Header */}
      <div className="mb-6">
        <Link
          href="/dashboard"
          className="text-sm text-cyan-400 hover:text-cyan-300 font-medium mb-4 inline-block"
        >
          ← Back to Dashboard
        </Link>
        <div className="flex items-start justify-between gap-4 mt-2">
          <div>
            <h1 className="text-xl font-bold text-slate-100 font-mono">
              {job.id}
            </h1>
            <p className="text-sm text-slate-400 mt-1">{job.user_prompt}</p>
          </div>
          <StatusBadge status={job.status} />
        </div>
        <div className="flex gap-4 mt-2 text-xs text-slate-500">
          <span>
            Created:{" "}
            {new Date(job.created_at).toLocaleString("en-US", {
              month: "short",
              day: "numeric",
              hour: "2-digit",
              minute: "2-digit",
              second: "2-digit",
            })}
          </span>
          {job.completed_at && (
            <span>
              Completed:{" "}
              {new Date(job.completed_at).toLocaleString("en-US", {
                month: "short",
                day: "numeric",
                hour: "2-digit",
                minute: "2-digit",
                second: "2-digit",
              })}
            </span>
          )}
        </div>
      </div>

      {/* Status Timeline */}
      <div className="bg-slate-800 rounded-lg border border-slate-700 p-4 mb-6">
        <h3 className="text-sm font-semibold text-slate-300 uppercase tracking-wider mb-3">
          Pipeline Progress
        </h3>
        <div className="flex items-center gap-1">
          {PHASE_ORDER.map((phase, i) => {
            const isCompleted = i <= currentPhaseIndex && !isFailed;
            const isCurrent = i === currentPhaseIndex && !isFailed;
            const isErrorPhase = isFailed && i === currentPhaseIndex;

            return (
              <div key={phase} className="flex-1 flex items-center">
                <div className="flex flex-col items-center flex-1">
                  <div
                    className={`w-8 h-8 rounded-full flex items-center justify-center text-xs font-bold transition-colors ${
                      isErrorPhase
                        ? "bg-red-500/20 text-red-400 border-2 border-red-500"
                        : isCurrent
                        ? "bg-cyan-500/20 text-cyan-400 border-2 border-cyan-500 animate-pulse"
                        : isCompleted
                        ? "bg-green-500/20 text-green-400 border-2 border-green-500"
                        : "bg-slate-700 text-slate-500 border-2 border-slate-600"
                    }`}
                  >
                    {isCompleted && !isErrorPhase ? "✓" : i + 1}
                  </div>
                  <span
                    className={`text-[10px] mt-1 text-center leading-tight ${
                      isCurrent || isCompleted
                        ? "text-slate-300"
                        : "text-slate-600"
                    }`}
                  >
                    {PHASE_LABELS[phase]}
                  </span>
                </div>
                {i < PHASE_ORDER.length - 1 && (
                  <div
                    className={`flex-1 h-0.5 mx-1 ${
                      i < currentPhaseIndex || (isFailed && i < currentPhaseIndex)
                        ? "bg-green-500/50"
                        : "bg-slate-700"
                    }`}
                  />
                )}
              </div>
            );
          })}
        </div>
        {isFailed && (
          <p className="text-xs text-red-400 mt-3 text-center">
            Pipeline failed during {PHASE_LABELS[job.status === "failed" ? "running" : job.status]} phase
          </p>
        )}
      </div>

      {/* Cost Preview */}
      {job.cost_estimate && (
        <div className="mb-6">
          <CostPreview cost={job.cost_estimate} />
        </div>
      )}

      {/* Results */}
      <ResultsViewer job={job} />
    </div>
  );
}