import type { CostEstimate } from "@/types";

export default function CostPreview({ cost }: { cost?: CostEstimate | null }) {
  if (!cost) return null;

  const markupPct =
    cost.platform_markup_usd > 0 && cost.raw_compute_cost_usd > 0
      ? Math.round(
          (cost.platform_markup_usd / cost.raw_compute_cost_usd) * 100
        )
      : 0;

  return (
    <div className="bg-slate-800 rounded-lg border border-slate-700 p-4 space-y-2">
      <h3 className="text-sm font-semibold text-slate-300 uppercase tracking-wider">
        Cost Estimate
      </h3>
      <div className="space-y-1 text-sm">
        <div className="flex justify-between text-slate-400">
          <span>Raw compute cost</span>
          <span className="font-mono text-slate-200">
            ${cost.raw_compute_cost_usd.toFixed(4)}
          </span>
        </div>
        <div className="flex justify-between text-slate-400">
          <span>Platform markup ({markupPct}%)</span>
          <span className="font-mono text-slate-200">
            +${cost.platform_markup_usd.toFixed(4)}
          </span>
        </div>
        <div className="border-t border-slate-700 pt-1 flex justify-between font-semibold">
          <span className="text-slate-200">Total cost</span>
          <span className="font-mono text-cyan-400">
            ${cost.total_cost_usd.toFixed(4)}
          </span>
        </div>
        <div className="flex justify-between text-slate-400">
          <span>Estimated runtime</span>
          <span className="font-mono text-slate-200">
            ~{cost.estimated_minutes} min
          </span>
        </div>
      </div>
    </div>
  );
}