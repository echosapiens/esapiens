"use client";

import { useState, useCallback } from "react";
import { useQuery } from "@tanstack/react-query";
import { api, type PipelineRead, type RunRead } from "@/lib/api";
import { cn, formatTimestamp } from "@/lib/utils";
import { Copy, Download, FileText, Check } from "lucide-react";

// ── Export Methods panel ────────────────────────────────────────────────
// Generates publication-ready method section text from pipeline execution metadata

interface ExportMethodsProps {
  sessionId: string;
}

export function ExportMethods({ sessionId }: ExportMethodsProps) {
  const [copied, setCopied] = useState(false);
  const [includeTimestamps, setIncludeTimestamps] = useState(true);
  const [includeDigests, setIncludeDigests] = useState(true);

  // ── Fetch pipelines ──────────────────────────────────────────────
  const { data: pipelines } = useQuery({
    queryKey: ["pipelines", sessionId],
    queryFn: () => api.listPipelines(sessionId),
  });

  const activePipeline = pipelines?.[0] ?? null;

  // ── Fetch runs ───────────────────────────────────────────────────
  const { data: runs } = useQuery({
    queryKey: ["runs", activePipeline?.id],
    queryFn: () => api.listRuns(activePipeline!.id),
    enabled: !!activePipeline,
  });

  // ── Generate methods text ────────────────────────────────────────
  const methodsText = generateMethodsText(
    activePipeline,
    runs ?? [],
    { includeTimestamps, includeDigests }
  );

  const handleCopy = useCallback(async () => {
    await navigator.clipboard.writeText(methodsText);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  }, [methodsText]);

  const handleDownload = useCallback(() => {
    const blob = new Blob([methodsText], { type: "text/plain" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `methods_${activePipeline?.name ?? "pipeline"}.txt`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  }, [methodsText, activePipeline?.name]);

  return (
    <div className="glass rounded-xl p-4">
      <div className="mb-4 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <FileText className="h-5 w-5 text-gold" />
          <h3 className="text-lg font-semibold text-navy">Export Methods</h3>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={handleCopy}
            className="btn-ghost inline-flex items-center gap-1.5 text-sm"
          >
            {copied ? (
              <>
                <Check className="h-4 w-4 text-green-500" />
                Copied!
              </>
            ) : (
              <>
                <Copy className="h-4 w-4" />
                Copy
              </>
            )}
          </button>
          <button
            onClick={handleDownload}
            className="btn-primary inline-flex items-center gap-1.5 text-sm"
          >
            <Download className="h-4 w-4" />
            Download .txt
          </button>
        </div>
      </div>

      {/* ── Options ────────────────────────────────────────────────── */}
      <div className="mb-4 flex items-center gap-4">
        <label className="flex items-center gap-2 text-sm">
          <input
            type="checkbox"
            checked={includeTimestamps}
            onChange={(e) => setIncludeTimestamps(e.target.checked)}
            className="rounded border-border text-navy focus:ring-gold"
          />
          Include timestamps
        </label>
        <label className="flex items-center gap-2 text-sm">
          <input
            type="checkbox"
            checked={includeDigests}
            onChange={(e) => setIncludeDigests(e.target.checked)}
            className="rounded border-border text-navy focus:ring-gold"
          />
          Include container digests
        </label>
      </div>

      {/* ── Methods preview ─────────────────────────────────────────── */}
      <div className="max-h-96 overflow-auto rounded-lg bg-navy-900 p-4">
        <pre className="whitespace-pre-wrap font-mono text-xs leading-relaxed text-cream-100">
          {methodsText || "No pipeline data available yet."}
        </pre>
      </div>
    </div>
  );
}

// ── Generate publication-ready methods text ──────────────────────────────

function generateMethodsText(
  pipeline: PipelineRead | null,
  runs: RunRead[],
  options: { includeTimestamps: boolean; includeDigests: boolean }
): string {
  if (!pipeline) return "";

  const dag = pipeline.dag_json;
  const lines: string[] = [];

  lines.push("Computational Methods");
  lines.push("=====================");
  lines.push("");
  lines.push(
    `Bioinformatics analyses were performed using the E.sapiens platform (v0.1.0). ` +
    `The pipeline "${pipeline.name}" was executed with the following containerized tools.`
  );
  lines.push("");

  // ── Extract steps from DAG ─────────────────────────────────────────
  let steps: Array<Record<string, unknown>> = [];
  if (Array.isArray((dag as Record<string, unknown>)?.steps)) {
    steps = ((dag as Record<string, unknown>).steps) as Array<Record<string, unknown>>;
  } else if (typeof dag === "object" && dag !== null) {
    for (const [name, val] of Object.entries(dag)) {
      if (typeof val === "object" && val !== null) {
        steps.push({ name, ...(val as Record<string, unknown>) });
      }
    }
  }

  // ── Describe each tool ─────────────────────────────────────────────
  for (const step of steps) {
    const stepName = (step.name as string) ?? (step.step_name as string) ?? "Unnamed step";
    const containerImage = (step.container_image as string) ?? (step.image as string) ?? "";
    const commandArgs = (step.command_args as string[]) ?? [];
    const run = runs.find((r) => r.step_name === stepName);

    lines.push(`### ${stepName}`);
    lines.push("");

    // Parse container image for tool name and version
    if (containerImage) {
      const imageParts = containerImage.split("/");
      const imageName = imageParts[imageParts.length - 1] ?? containerImage;
      const parts = imageName.split(":");
      const toolName = parts[0] ?? imageName;
      const version = parts.length > 1 ? parts[1].split("@")[0] : "latest";

      lines.push(`${toolName} (v${version}) was used`);

      if (options.includeDigests && containerImage.includes("@")) {
        const digest = containerImage.split("@")[1];
        if (digest) {
          lines.push(`  Container image digest: ${digest}`);
        }
      }
    }

    if (commandArgs.length > 0) {
      lines.push(`  Command-line arguments: ${commandArgs.join(" ")}`);
    }

    if (run && options.includeTimestamps) {
      if (run.started_at) {
        lines.push(
          `  Execution started: ${formatTimestamp(run.started_at)}`
        );
      }
      if (run.completed_at) {
        lines.push(
          `  Execution completed: ${formatTimestamp(run.completed_at)}`
        );
      }
      if (run.exit_code !== null && run.exit_code !== undefined) {
        lines.push(`  Exit code: ${run.exit_code}`);
      }
    }

    lines.push("");
  }

  // ── Summary ────────────────────────────────────────────────────────
  const completedRuns = runs.filter((r) => r.status === "completed").length;
  const failedRuns = runs.filter((r) => r.status === "failed").length;
  const totalRuns = runs.length;

  lines.push("### Summary");
  lines.push("");
  lines.push(
    `A total of ${totalRuns} bioinformatics step${totalRuns !== 1 ? "s were" : " was"} executed: ` +
    `${completedRuns} completed successfully` +
    (failedRuns > 0 ? `, ${failedRuns} failed` : "") +
    "."
  );
  lines.push("");
  lines.push(
    "All analyses were performed using containerized tools with pinned SHA256 digests " +
    "to ensure reproducibility. Container images were sourced from the Biocontainers " +
    "project (https://biocontainers.pro/)."
  );

  return lines.join("\n");
}