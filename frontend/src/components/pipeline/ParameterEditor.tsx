"use client";

import { useState, useCallback } from "react";
import { cn } from "@/lib/utils";
import { Check, X, RotateCcw } from "lucide-react";

interface StepInfo {
  name: string;
  status: string;
  container_image: string;
  command_args: string[];
  depends_on: string[];
  started_at?: string | null;
  completed_at?: string | null;
  progress?: number;
}

interface ParameterEditorProps {
  step: StepInfo;
  pipelineId: string;
}

// ── Parameter editor ────────────────────────────────────────────────────

export function ParameterEditor({ step, pipelineId }: ParameterEditorProps) {
  const [args, setArgs] = useState<string[]>([...step.command_args]);
  const [originalArgs] = useState<string[]>([...step.command_args]);
  const [isEditing, setIsEditing] = useState(false);

  // ── Compute diff ─────────────────────────────────────────────────
  const changedIndices = new Set<number>();
  args.forEach((arg, i) => {
    if (arg !== (originalArgs[i] ?? "")) changedIndices.add(i);
  });
  // New args added
  for (let i = originalArgs.length; i < args.length; i++) {
    changedIndices.add(i);
  }

  const hasChanges =
    args.length !== originalArgs.length ||
    args.some((arg, i) => arg !== (originalArgs[i] ?? ""));

  // ── Handlers ──────────────────────────────────────────────────────
  const handleArgChange = useCallback((index: number, value: string) => {
    setArgs((prev) => {
      const next = [...prev];
      next[index] = value;
      return next;
    });
  }, []);

  const handleAddArg = useCallback(() => {
    setArgs((prev) => [...prev, ""]);
  }, []);

  const handleRemoveArg = useCallback((index: number) => {
    setArgs((prev) => prev.filter((_, i) => i !== index));
  }, []);

  const handleReset = useCallback(() => {
    setArgs([...originalArgs]);
    setIsEditing(false);
  }, [originalArgs]);

  const handleSave = useCallback(() => {
    // TODO: Call API to update pipeline DAG
    // api.updatePipeline(pipelineId, { dag_json: { ... } })
    setIsEditing(false);
  }, [pipelineId]);

  return (
    <div className="glass rounded-xl p-4">
      <div className="mb-3 flex items-center justify-between">
        <div>
          <h4 className="text-sm font-semibold text-navy">
            Parameters: {step.name}
          </h4>
          <p className="mt-0.5 font-mono text-xs text-muted-foreground">
            {step.container_image}
          </p>
        </div>
        <div className="flex items-center gap-2">
          {hasChanges && (
            <>
              <button
                onClick={handleSave}
                className="btn-accent inline-flex items-center gap-1 text-xs"
              >
                <Check className="h-3 w-3" />
                Apply
              </button>
              <button
                onClick={handleReset}
                className="btn-ghost inline-flex items-center gap-1 text-xs"
              >
                <RotateCcw className="h-3 w-3" />
                Reset
              </button>
            </>
          )}
          {!isEditing && !hasChanges && (
            <button
              onClick={() => setIsEditing(true)}
              className="btn-ghost text-xs"
            >
              Edit
            </button>
          )}
        </div>
      </div>

      {/* ── Command args list ──────────────────────────────────────── */}
      <div className="space-y-1">
        {args.map((arg, index) => {
          const isChanged = changedIndices.has(index);
          return (
            <div
              key={index}
              className={cn(
                "flex items-center gap-2 rounded px-2 py-1 text-sm",
                isChanged
                  ? "bg-gold/10 border border-gold/30"
                  : "glass rounded-lg"
              )}
            >
              {isEditing ? (
                <>
                  <input
                    type="text"
                    value={arg}
                    onChange={(e) => handleArgChange(index, e.target.value)}
                    className="input-base flex-1 py-0.5 text-xs font-mono"
                  />
                  <button
                    onClick={() => handleRemoveArg(index)}
                    className="text-red-400 hover:text-red-600"
                  >
                    <X className="h-3.5 w-3.5" />
                  </button>
                </>
              ) : (
                <code
                  className={cn(
                    "flex-1 font-mono text-xs",
                    isChanged ? "text-gold-700 font-semibold" : "text-navy"
                  )}
                >
                  {arg}
                </code>
              )}
            </div>
          );
        })}

        {isEditing && (
          <button
            onClick={handleAddArg}
            className="mt-1 text-xs text-gold hover:text-gold-600"
          >
            + Add argument
          </button>
        )}
      </div>

      {/* ── Diff summary ───────────────────────────────────────────── */}
      {hasChanges && (
        <div className="mt-3 glass rounded-lg border border-gold/30 px-3 py-2 text-xs text-navy">
          <span className="font-medium">
            {changedIndices.size} parameter{changedIndices.size !== 1 ? "s" : ""} modified
          </span>
        </div>
      )}
    </div>
  );
}