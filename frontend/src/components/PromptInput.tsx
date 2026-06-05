"use client";

import { useState } from "react";
import { submitPipeline } from "@/lib/api";
import type { PipelineResponse } from "@/types";

export default function PromptInput({
  onSubmitted,
}: {
  onSubmitted?: (result: PipelineResponse) => void;
}) {
  const [prompt, setPrompt] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async () => {
    const trimmed = prompt.trim();
    if (!trimmed) return;

    setLoading(true);
    setError(null);

    try {
      const result = await submitPipeline(trimmed);
      setPrompt("");
      onSubmitted?.(result);
    } catch (err: unknown) {
      const apiErr = err as { status?: number; message?: string };
      setError(
        apiErr.message ?? "Failed to submit pipeline. Please try again."
      );
    } finally {
      setLoading(false);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) {
      e.preventDefault();
      handleSubmit();
    }
  };

  return (
    <div className="w-full space-y-3">
      <textarea
        value={prompt}
        onChange={(e) => setPrompt(e.target.value)}
        onKeyDown={handleKeyDown}
        rows={5}
        disabled={loading}
        placeholder='Describe your bioinformatics analysis... e.g., "Align RNA-seq reads and quantify gene expression"'
        className="w-full px-4 py-3 bg-slate-800 border border-slate-700 rounded-lg text-slate-100 placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-cyan-500 focus:border-transparent resize-none text-sm disabled:opacity-50 disabled:cursor-not-allowed"
      />
      <div className="flex items-center justify-between">
        <p className="text-xs text-slate-500">
          Press <kbd className="px-1 py-0.5 bg-slate-800 rounded text-slate-400 font-mono text-xs">⌘+Enter</kbd> to submit
        </p>
        <button
          onClick={handleSubmit}
          disabled={loading || !prompt.trim()}
          className="px-6 py-2 bg-cyan-600 hover:bg-cyan-500 disabled:bg-slate-700 disabled:text-slate-500 text-white rounded-lg font-medium text-sm transition-colors focus:outline-none focus:ring-2 focus:ring-cyan-500 focus:ring-offset-2 focus:ring-offset-slate-900"
        >
          {loading ? (
            <span className="flex items-center gap-2">
              <svg
                className="animate-spin h-4 w-4"
                viewBox="0 0 24 24"
                fill="none"
              >
                <circle
                  className="opacity-25"
                  cx="12"
                  cy="12"
                  r="10"
                  stroke="currentColor"
                  strokeWidth="4"
                />
                <path
                  className="opacity-75"
                  fill="currentColor"
                  d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"
                />
              </svg>
              Running pipeline...
            </span>
          ) : (
            "Run Pipeline"
          )}
        </button>
      </div>
      {error && (
        <div className="p-3 bg-red-500/10 border border-red-500/30 rounded-lg text-red-400 text-sm">
          {error}
        </div>
      )}
    </div>
  );
}