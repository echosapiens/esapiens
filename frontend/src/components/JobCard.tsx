"use client";

import { useState } from "react";
import Link from "next/link";
import StatusBadge from "./StatusBadge";
import type { JobExecution } from "@/types";

export default function JobCard({ job }: { job: JobExecution }) {
  const [expanded, setExpanded] = useState(false);

  const truncatedPrompt =
    job.user_prompt.length > 80
      ? job.user_prompt.slice(0, 80) + "..."
      : job.user_prompt;

  const shortId = job.id.length > 12 ? job.id.slice(0, 12) + "..." : job.id;

  const createdDate = new Date(job.created_at);
  const formattedDate = createdDate.toLocaleDateString("en-US", {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });

  return (
    <div className="bg-slate-800 border border-slate-700 rounded-lg overflow-hidden transition-colors hover:border-slate-600">
      <button
        onClick={() => setExpanded(!expanded)}
        className="w-full text-left p-4 focus:outline-none focus:ring-2 focus:ring-inset focus:ring-cyan-500"
      >
        <div className="flex items-start justify-between gap-4">
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2 mb-1">
              <span className="text-xs font-mono text-slate-500">
                {shortId}
              </span>
              <StatusBadge status={job.status} />
            </div>
            <p className="text-sm text-slate-200 truncate">{truncatedPrompt}</p>
          </div>
          <div className="flex items-center gap-3 shrink-0">
            <span className="text-xs text-slate-500">{formattedDate}</span>
            <svg
              className={`w-4 h-4 text-slate-500 transition-transform ${
                expanded ? "rotate-180" : ""
              }`}
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M19 9l-7 7-7-7"
              />
            </svg>
          </div>
        </div>
      </button>

      {expanded && (
        <div className="px-4 pb-4 border-t border-slate-700 pt-3 space-y-3">
          <p className="text-sm text-slate-400">{job.user_prompt}</p>

          {job.cost_estimate && (
            <div className="flex gap-4 text-xs text-slate-400">
              <span>
                Cost:{" "}
                <span className="font-mono text-cyan-400">
                  ${job.cost_estimate.total_cost_usd.toFixed(4)}
                </span>
              </span>
              <span>
                Est. runtime:{" "}
                <span className="font-mono text-slate-300">
                  ~{job.cost_estimate.estimated_minutes} min
                </span>
              </span>
            </div>
          )}

          <div className="flex gap-3">
            <Link
              href={`/jobs/${job.id}`}
              className="text-xs text-cyan-400 hover:text-cyan-300 transition-colors font-medium"
            >
              View Details &rarr;
            </Link>
            {job.completed_at && (
              <span className="text-xs text-slate-500">
                Completed:{" "}
                {new Date(job.completed_at).toLocaleDateString("en-US", {
                  month: "short",
                  day: "numeric",
                  hour: "2-digit",
                  minute: "2-digit",
                })}
              </span>
            )}
          </div>
        </div>
      )}
    </div>
  );
}