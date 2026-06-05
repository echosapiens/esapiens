import type { JobExecution } from "@/types";

export default function ResultsViewer({ job }: { job: JobExecution }) {
  const { contract, stdout, stderr, error, status } = job;
  const isSuccess = status === "completed";

  return (
    <div className="space-y-4">
      {/* Error message -- only for actual failures */}
      {error && !isSuccess && (
        <div className="p-4 bg-red-500/10 border border-red-500/30 rounded-lg">
          <h4 className="text-sm font-semibold text-red-400 mb-1">Error</h4>
          <pre className="text-sm text-red-300 font-mono whitespace-pre-wrap">
            {error}
          </pre>
        </div>
      )}

      {/* Container Contract */}
      {contract && (
        <div className="bg-slate-800 rounded-lg border border-slate-700 p-4 space-y-4">
          <h3 className="text-sm font-semibold text-slate-300 uppercase tracking-wider">
            Container Contract
          </h3>

          <div>
            <label className="text-xs text-slate-500 uppercase tracking-wide">
              Image
            </label>
            <p className="text-sm font-mono text-sky-400 mt-0.5">
              {contract.image_string}
            </p>
          </div>

          <div>
            <label className="text-xs text-slate-500 uppercase tracking-wide">
              CLI Command
            </label>
            <pre className="mt-1 p-3 bg-slate-900 rounded-lg text-sm font-mono text-slate-200 overflow-x-auto">
              {contract.exact_cli_command}
            </pre>
          </div>

          {contract.inputs.length > 0 && (
            <div>
              <label className="text-xs text-slate-500 uppercase tracking-wide">
                Expected Inputs
              </label>
              <div className="mt-1 space-y-1">
                {contract.inputs.map((input, i) => (
                  <div
                    key={i}
                    className="flex items-center gap-2 text-sm text-slate-300"
                  >
                    <span className="text-cyan-400">
                      <span className="text-xs">[in]</span>
                    </span>
                    <span className="font-mono text-xs bg-slate-700 px-1.5 py-0.5 rounded">
                      {input.file_type}
                    </span>
                    <span className="text-slate-400">&rarr;</span>
                    <span className="font-mono text-xs">{input.mount_path}</span>
                    {input.description && (
                      <span className="text-slate-500 text-xs">
                        &mdash; {input.description}
                      </span>
                    )}
                  </div>
                ))}
              </div>
            </div>
          )}

          {contract.outputs.length > 0 && (
            <div>
              <label className="text-xs text-slate-500 uppercase tracking-wide">
                Generated Outputs
              </label>
              <div className="mt-1 space-y-1">
                {contract.outputs.map((output, i) => (
                  <div
                    key={i}
                    className="flex items-center gap-2 text-sm text-slate-300"
                  >
                    <span className="text-green-400">
                      <span className="text-xs">[out]</span>
                    </span>
                    <span className="font-mono text-xs bg-slate-700 px-1.5 py-0.5 rounded">
                      {output.file_type}
                    </span>
                    <span className="text-slate-400">&rarr;</span>
                    <span className="font-mono text-xs">{output.mount_path}</span>
                    {output.description && (
                      <span className="text-slate-500 text-xs">
                        &mdash; {output.description}
                      </span>
                    )}
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}

      {/* stdout */}
      {stdout && (
        <div className="bg-slate-800 rounded-lg border border-slate-700 p-4">
          <div className="flex items-center justify-between mb-2">
            <h4 className="text-sm font-semibold text-slate-300 uppercase tracking-wider">
              stdout
            </h4>
            <span className="text-xs text-slate-500 font-mono">
              {stdout.split("\n").length} lines
            </span>
          </div>
          <pre className="p-3 bg-slate-900 rounded-lg text-sm font-mono text-slate-300 overflow-auto max-h-64 whitespace-pre-wrap">
            {stdout}
          </pre>
        </div>
      )}

      {/* stderr -- styled as tool progress when successful, error when failed */}
      {stderr && (
        <div className={`bg-slate-800 rounded-lg border ${isSuccess ? "border-slate-700" : "border-red-500/30"} p-4`}>
          <div className="flex items-center justify-between mb-2">
            <h4 className={`text-sm font-semibold uppercase tracking-wider ${isSuccess ? "text-amber-400" : "text-red-400"}`}>
              {isSuccess ? "Tool Progress" : "stderr"}
            </h4>
            <span className="text-xs text-slate-500 font-mono">
              {stderr.split("\n").length} lines
            </span>
          </div>
          <pre className={`p-3 bg-slate-900 rounded-lg text-sm font-mono overflow-auto max-h-64 whitespace-pre-wrap ${isSuccess ? "text-amber-200/80" : "text-red-300"}`}>
            {stderr}
          </pre>
        </div>
      )}

      {/* No results state */}
      {!contract && !stdout && !stderr && !error && (
        <div className="text-center py-8 text-slate-500 text-sm">
          No results available yet. The pipeline is still processing.
        </div>
      )}
    </div>
  );
}