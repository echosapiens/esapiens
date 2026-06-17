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

  const { data: pipelines, isLoading: pipelinesLoading } = useQuery({
    queryKey: ["pipelines", sessionId],
    queryFn: () => api.listPipelines(sessionId),
  });

  const storePipelines = useSessionStore((s) => s.pipelines);
  const activePipeline = pipelines?.[0] ?? null;

  const { data: runs } = useQuery({
    queryKey: ["runs", activePipeline?.id],
    queryFn: () => api.listRuns(activePipeline!.id),
    enabled: !!activePipeline,
    refetchInterval: (query) => {
      const data = query.state.data as RunRead[] | undefined;
      if (!data) return false;
      return data.some((r) => r.status === "pending" || r.status === "running") ? 2000 : false;
    },
  });

  const steps = deriveSteps(activePipeline, runs ?? []);

  if (pipelinesLoading) {
    return <div className="flex h-full items-center justify-center"><Loader2 className="h-5 w-5 animate-spin" style={{ color: "var(--text-muted)" }} /></div>;
  }

  if (!activePipeline) {
    return <div className="flex h-full items-center justify-center text-xs" style={{ color: "var(--text-muted)" }}><p>No pipelines yet. Start a conversation to generate a plan.</p></div>;
  }

  const handleSelectStep = useCallback((name: string | null) => setSelectedStep(name), []);

  return (
    <div className="flex h-full flex-col overflow-auto p-4">
      <div className="mb-4">
        <div className="flex items-center justify-between">
          <div className="min-w-0">
            <h3 className="text-sm font-semibold" style={{ color: "var(--text-primary)" }}>{activePipeline.name}</h3>
            {activePipeline.description && <p className="text-xs" style={{ color: "var(--text-muted)" }}>{activePipeline.description}</p>}
          </div>
          <div className="flex items-center gap-3">
            <div className="segmented">
              <button onClick={() => setViewMode("graph")} className={cn("segmented-item", viewMode === "graph" && "active")}>
                <GitGraph className="h-3.5 w-3.5" /> Graph
              </button>
              <button onClick={() => setViewMode("list")} className={cn("segmented-item", viewMode === "list" && "active")}>
                <List className="h-3.5 w-3.5" /> List
              </button>
            </div>
            <span className={cn("badge", statusColorClass(activePipeline.status).replace("status-", "badge-"))}>{activePipeline.status}</span>
          </div>
        </div>
      </div>

      {viewMode === "graph" && (
        <div className="mb-6">
          <h4 className="mb-2 text-xs font-medium" style={{ color: "var(--text-secondary)" }}>Pipeline DAG</h4>
          <DagGraph steps={steps} selectedStep={selectedStep} onSelectStep={handleSelectStep} />
        </div>
      )}

      {viewMode === "list" && (
        <div className="mb-6 space-y-2">
          <h4 className="text-xs font-medium" style={{ color: "var(--text-secondary)" }}>Pipeline Steps</h4>
          {steps.map((step) => (
            <StepRow key={step.name} step={step} isExpanded={selectedStep === step.name} onToggle={() => setSelectedStep(selectedStep === step.name ? null : step.name)} />
          ))}
        </div>
      )}

      {selectedStep && <ParameterEditor step={steps.find((s) => s.name === selectedStep)!} pipelineId={activePipeline.id} />}
    </div>
  );
}

function StepRow({ step, isExpanded, onToggle }: { step: StepInfo; isExpanded: boolean; onToggle: () => void }) {
  const statusIcons: Record<string, React.ReactNode> = {
    completed: <CheckCircle2 className="h-4 w-4" style={{ color: "var(--accent-green)" }} />,
    running: <Loader2 className="h-4 w-4 animate-spin" style={{ color: "var(--accent-blue)" }} />,
    failed: <XCircle className="h-4 w-4" style={{ color: "var(--accent-red)" }} />,
    pending: <Clock className="h-4 w-4" style={{ color: "var(--accent-orange)" }} />,
    submitted: <Play className="h-4 w-4" style={{ color: "var(--accent-purple)" }} />,
  };
  const progressMap: Record<string, number> = { completed: 100, running: step.progress ?? 50, failed: step.progress ?? 0, pending: 0, submitted: 10 };
  const progressColorMap: Record<string, string> = { completed: "progress-fill-green", running: "progress-fill-blue", failed: "progress-fill-red", pending: "progress-fill-gold", submitted: "progress-fill-gold" };
  const progress = progressMap[step.status] ?? 0;
  const progressColor = progressColorMap[step.status] ?? "bg-gray-500";

  return (
    <div>
      <button onClick={onToggle} className="flex w-full items-center gap-3 card card-hover px-3 py-2 text-left transition-all">
        {isExpanded ? <ChevronDown className="h-4 w-4 shrink-0" style={{ color: "var(--text-muted)" }} /> : <ChevronRight className="h-4 w-4 shrink-0" style={{ color: "var(--text-muted)" }} />}
        <span className="shrink-0">{statusIcons[step.status] ?? <Clock className="h-4 w-4 text-gray-500" />}</span>
        <span className="flex-1 text-sm font-medium" style={{ color: "var(--text-primary)" }}>{step.name}</span>
        <div className="w-32">
          <div className="progress">
            <div className={cn("progress-fill", progressColor)} style={{ width: `${progress}%` }} />
          </div>
        </div>
        <span className="text-xs" style={{ color: "var(--text-muted)" }}>{progress}%</span>
      </button>
      {isExpanded && (
        <div className="ml-8 mt-1 space-y-1 card p-3 text-xs">
          <div><span className="font-medium" style={{ color: "var(--text-primary)" }}>Image: </span><span className="font-mono" style={{ color: "var(--text-secondary)" }}>{step.container_image}</span></div>
          {step.command_args.length > 0 && <div><span className="font-medium" style={{ color: "var(--text-primary)" }}>Args: </span><code className="font-mono" style={{ color: "var(--text-secondary)" }}>{step.command_args.join(" ")}</code></div>}
          {step.depends_on.length > 0 && <div><span className="font-medium" style={{ color: "var(--text-primary)" }}>Depends on: </span><span style={{ color: "var(--text-secondary)" }}>{step.depends_on.join(", ")}</span></div>}
          {step.started_at && <div><span className="font-medium" style={{ color: "var(--text-primary)" }}>Started: </span><span style={{ color: "var(--text-secondary)" }}>{formatRelativeDate(step.started_at)}</span></div>}
          {step.status === "failed" && <div className="flex items-center gap-1" style={{ color: "var(--accent-red)" }}><AlertTriangle className="h-3 w-3" /><span>Step failed &mdash; check logs for details</span></div>}
        </div>
      )}
    </div>
  );
}

function deriveSteps(pipeline: PipelineRead | null, runs: RunRead[]): StepInfo[] {
  if (!pipeline) return [];
  const dag = pipeline.dag_json;
  let stepsData: Array<Record<string, unknown>> = [];
  if (Array.isArray(dag.steps)) {
    stepsData = dag.steps as Array<Record<string, unknown>>;
  } else if (typeof dag === "object" && dag !== null) {
    const dagObj = dag as Record<string, unknown>;
    if (dagObj.steps && Array.isArray(dagObj.steps)) {
      stepsData = dagObj.steps as Array<Record<string, unknown>>;
    } else {
      for (const [name, val] of Object.entries(dag)) {
        if (typeof val === "object" && val !== null) stepsData.push({ name, ...(val as Record<string, unknown>) });
      }
    }
  }
  const runsByStep = new Map<string, RunRead>();
  for (const run of runs) runsByStep.set(run.step_name, run);
  return stepsData.map((step) => {
    const stepName = (step.name as string) ?? (step.step_name as string) ?? "unknown";
    const run = runsByStep.get(stepName);
    const realProgress = run?.progress ?? null;
    const inferredProgress = run?.status === "completed" ? 100 : run?.status === "running" ? 50 : 0;
    return {
      name: stepName,
      status: run?.status ?? (step.status as string) ?? "pending",
      container_image: (step.container_image as string) ?? (step.image as string) ?? "unknown",
      command_args: (step.command_args as string[]) ?? (step.args as string[]) ?? [],
      depends_on: (step.depends_on as string[]) ?? [],
      started_at: run?.started_at ?? null,
      completed_at: run?.completed_at ?? null,
      progress: realProgress ?? inferredProgress,
    };
  });
}