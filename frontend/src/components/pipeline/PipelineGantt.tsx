"use client";

import { useState, useCallback } from "react";
import { useSessionStore } from "@/store/sessionStore";
import { useQuery } from "@tanstack/react-query";
import { api, type PipelineRead, type RunRead } from "@/lib/api";
import { cn, statusColorClass, formatRelativeDate } from "@/lib/utils";
import {
  ChevronDown,
  ChevronRight,
  CheckCircle2,
  XCircle,
  Loader2,
  Clock,
  Play,
  AlertTriangle,
  GitGraph,
  List,
} from "lucide-react";
import { ParameterEditor } from "./ParameterEditor";
import { DagGraph } from "./DagGraph";

// ── Pipeline Gantt chart ────────────────────────────────────────────────

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

export function PipelineGantt({ sessionId }: { sessionId: string }) {
  const [selectedStep, setSelectedStep] = useState<string | null>(null);
  const [viewMode, setViewMode] = useState<"graph" | "list">("graph");

  // ── Fetch pipelines ──────────────────────────────────────────────
  const {
    data: pipelines,
    isLoading: pipelinesLoading,
  } = useQuery({
    queryKey: ["pipelines", sessionId],
    queryFn: () => api.listPipelines(sessionId),
  });

  // ── Use the first pipeline (or from store) ────────────────────────
  const storePipelines = useSessionStore((s) => s.pipelines);
  const activePipeline = pipelines?.[0] ?? null;

  // ── Fetch runs for the active pipeline (with live polling for progress) ────
  const { data: runs } = useQuery({
    queryKey: ["runs", activePipeline?.id],
    queryFn: () => api.listRuns(activePipeline!.id),
    enabled: !!activePipeline,
    refetchInterval: (query) => {
      // Poll every 2s while any run is active, otherwise stop
      const data = query.state.data as RunRead[] | undefined;
      if (!data) return false;
      return data.some((r) => r.status === "pending" || r.status === "running") ? 2000 : false;
    },
  });

  // ── Derive steps from DAG + runs ─────────────────────────────────
  const steps = deriveSteps(activePipeline, runs ?? []);

  if (pipelinesLoading) {
    return (
      <div className="flex h-full items-center justify-center">
        <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
      </div>
    );
  }

  if (!activePipeline) {
    return (
      <div className="flex h-full items-center justify-center text-muted-foreground">
        <p>No pipelines yet. Start a conversation to generate a plan.</p>
      </div>
    );
  }

  const handleSelectStep = useCallback((name: string | null) => {
    setSelectedStep(name);
  }, []);

  return (
    <div className="flex h-full flex-col overflow-auto p-4">
      {/* ── Pipeline header ─────────────────────────────────────────── */}
      <div className="mb-4">
        <div className="flex items-center justify-between">
          <div>
            <h3 className="text-lg font-semibold text-navy">
              {activePipeline.name}
            </h3>
            {activePipeline.description && (
              <p className="text-sm text-muted-foreground">
                {activePipeline.description}
              </p>
            )}
          </div>
          <div className="flex items-center gap-3">
            {/* ── View toggle ─────────────────────────────────────────── */}
            <div className="mac-segmented">
              <button
                onClick={() => setViewMode("graph")}
                className={cn(
                  "mac-segmented-item",
                  viewMode === "graph" && "active"
                )}
              >
                <GitGraph className="h-3.5 w-3.5" />
                Graph
              </button>
              <button
                onClick={() => setViewMode("list")}
                className={cn(
                  "mac-segmented-item",
                  viewMode === "list" && "active"
                )}
              >
                <List className="h-3.5 w-3.5" />
                List
              </button>
            </div>
            <span
              className={cn(
                "rounded-full px-3 py-1 text-xs font-medium",
                statusColorClass(activePipeline.status)
              )}
            >
              {activePipeline.status}
            </span>
          </div>
        </div>
      </div>

      {/* ── DAG graph view ──────────────────────────────────────────── */}
      {viewMode === "graph" && (
        <div className="mb-6">
          <h4 className="mb-2 text-sm font-medium text-navy">Pipeline DAG</h4>
          <DagGraph
            steps={steps}
            selectedStep={selectedStep}
            onSelectStep={handleSelectStep}
          />
        </div>
      )}

      {/* ── Step list (Gantt) ───────────────────────────────────────── */}
      {viewMode === "list" && (
        <div className="mb-6 space-y-2">
          <h4 className="text-sm font-medium text-navy">Pipeline Steps</h4>
          {steps.map((step) => (
            <StepRow
              key={step.name}
              step={step}
              isExpanded={selectedStep === step.name}
              onToggle={() =>
                setSelectedStep(selectedStep === step.name ? null : step.name)
              }
            />
          ))}
        </div>
      )}

      {/* ── Parameter editor (when step is selected) ──────────────── */}
      {selectedStep && (
        <ParameterEditor
          step={steps.find((s) => s.name === selectedStep)!}
          pipelineId={activePipeline.id}
        />
      )}
    </div>
  );
}

// ── Step row ────────────────────────────────────────────────────────────

function StepRow({
  step,
  isExpanded,
  onToggle,
}: {
  step: StepInfo;
  isExpanded: boolean;
  onToggle: () => void;
}) {
  const statusIcons: Record<string, React.ReactNode> = {
    completed: <CheckCircle2 className="h-4 w-4 text-green-500" />,
    running: <Loader2 className="h-4 w-4 animate-spin text-blue-500" />,
    failed: <XCircle className="h-4 w-4 text-red-500" />,
    pending: <Clock className="h-4 w-4 text-yellow-500" />,
    submitted: <Play className="h-4 w-4 text-purple-500" />,
  };

  const progressMap: Record<string, number> = {
    completed: 100,
    running: step.progress ?? 50,
    failed: step.progress ?? 0,
    pending: 0,
    submitted: 10,
  };

  const progressColorMap: Record<string, string> = {
    completed: "bg-green-500",
    running: "bg-blue-500",
    failed: "bg-red-500",
    pending: "bg-yellow-400",
    submitted: "bg-purple-500",
  };

  const progress = progressMap[step.status] ?? 0;
  const progressColor = progressColorMap[step.status] ?? "bg-gray-400";

  return (
    <div>
      <button
        onClick={onToggle}
        className="flex w-full items-center gap-3 mac-card px-3 py-2 text-left hover:shadow-md transition-all"
      >
        {isExpanded ? (
          <ChevronDown className="h-4 w-4 shrink-0 text-muted-foreground" />
        ) : (
          <ChevronRight className="h-4 w-4 shrink-0 text-muted-foreground" />
        )}
        <span className="shrink-0">
          {statusIcons[step.status] ?? <Clock className="h-4 w-4 text-gray-400" />}
        </span>
        <span className="flex-1 text-sm font-medium text-navy">
          {step.name}
        </span>
        <div className="w-32">
          <div className="h-2 overflow-hidden rounded-full bg-cream-300">
            <div
              className={cn("h-full rounded-full transition-all", progressColor)}
              style={{ width: `${progress}%` }}
            />
          </div>
        </div>
        <span className="text-xs text-muted-foreground">{progress}%</span>
      </button>
      {isExpanded && (
        <div className="ml-8 mt-1 space-y-1 mac-card p-3 text-xs">
          <div>
            <span className="font-medium text-navy">Image: </span>
            <span className="font-mono text-muted-foreground">
              {step.container_image}
            </span>
          </div>
          {step.command_args.length > 0 && (
            <div>
              <span className="font-medium text-navy">Args: </span>
              <code className="font-mono text-muted-foreground">
                {step.command_args.join(" ")}
              </code>
            </div>
          )}
          {step.depends_on.length > 0 && (
            <div>
              <span className="font-medium text-navy">Depends on: </span>
              <span className="text-muted-foreground">
                {step.depends_on.join(", ")}
              </span>
            </div>
          )}
          {step.started_at && (
            <div>
              <span className="font-medium text-navy">Started: </span>
              <span className="text-muted-foreground">
                {formatRelativeDate(step.started_at)}
              </span>
            </div>
          )}
          {step.status === "failed" && (
            <div className="flex items-center gap-1 text-red-600">
              <AlertTriangle className="h-3 w-3" />
              <span>Step failed — check logs for details</span>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

// ── Helper: Derive steps from pipeline + runs ──────────────────────────

function deriveSteps(
  pipeline: PipelineRead | null,
  runs: RunRead[]
): StepInfo[] {
  if (!pipeline) return [];

  const dag = pipeline.dag_json;
  // Support two DAG formats: { steps: [...] } or { step_name: {...}, ... }
  let stepsData: Array<Record<string, unknown>> = [];

  if (Array.isArray(dag.steps)) {
    stepsData = dag.steps as Array<Record<string, unknown>>;
  } else if (typeof dag === "object" && dag !== null) {
    // Could be keyed by step name
    const dagObj = dag as Record<string, unknown>;
    if (dagObj.steps && Array.isArray(dagObj.steps)) {
      stepsData = dagObj.steps as Array<Record<string, unknown>>;
    } else {
      // Assume keys are step names
      for (const [name, val] of Object.entries(dag)) {
        if (typeof val === "object" && val !== null) {
          stepsData.push({ name: name, ...(val as Record<string, unknown>) });
        }
      }
    }
  }

  // Build a runs lookup by step_name
  const runsByStep = new Map<string, RunRead>();
  for (const run of runs) {
    runsByStep.set(run.step_name, run);
  }

  return stepsData.map((step) => {
    const stepName = (step.name as string) ?? (step.step_name as string) ?? "unknown";
    const run = runsByStep.get(stepName);

    // Use real progress from the run if available, else infer from status
    const realProgress = run?.progress ?? null;
    const inferredProgress =
      run?.status === "completed"
        ? 100
        : run?.status === "running"
          ? 50
          : run?.status === "failed"
            ? 0
            : 0;

    return {
      name: stepName,
      status: run?.status ?? (step.status as string) ?? "pending",
      container_image:
        (step.container_image as string) ??
        (step.image as string) ??
        "unknown",
      command_args: (step.command_args as string[]) ?? (step.args as string[]) ?? [],
      depends_on: (step.depends_on as string[]) ?? [],
      started_at: run?.started_at ?? null,
      completed_at: run?.completed_at ?? null,
      progress: realProgress ?? inferredProgress,
    };
  });
}