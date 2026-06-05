"use client";

type PhaseStatus = "pending" | "active" | "completed";

interface Phase {
  id: number;
  name: string;
  status: PhaseStatus;
}

interface PhaseIndicatorProps {
  phases: Phase[];
}

export default function PhaseIndicator({ phases }: PhaseIndicatorProps) {
  return (
    <div className="flex items-center justify-center gap-0 px-4 py-3">
      {phases.map((phase, index) => {
        const isActive = phase.status === "active";
        const isCompleted = phase.status === "completed";
        const isPending = phase.status === "pending";

        return (
          <div key={phase.id} className="flex items-center">
            {/* Phase circle + label */}
            <div className="flex flex-col items-center gap-1">
              <div
                className={`w-8 h-8 rounded-full flex items-center justify-center text-xs font-bold transition-all duration-500 ${
                  isCompleted
                    ? "bg-cyan-500 text-white shadow-lg shadow-cyan-500/30"
                    : isActive
                    ? "bg-cyan-600 text-white animate-pulse shadow-md shadow-cyan-500/20 ring-2 ring-cyan-400/50"
                    : "bg-slate-700/60 text-slate-500"
                }`}
              >
                {isCompleted ? (
                  <svg
                    className="w-4 h-4"
                    fill="none"
                    viewBox="0 0 24 24"
                    stroke="currentColor"
                    strokeWidth={3}
                  >
                    <path
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      d="M5 13l4 4L19 7"
                    />
                  </svg>
                ) : (
                  phase.id
                )}
              </div>
              <span
                className={`text-[10px] uppercase tracking-wider font-semibold ${
                  isCompleted
                    ? "text-cyan-400"
                    : isActive
                    ? "text-cyan-300"
                    : "text-slate-600"
                }`}
              >
                {phase.name}
              </span>
            </div>

            {/* Connector line between phases */}
            {index < phases.length - 1 && (
              <div className="w-12 md:w-20 h-0.5 mx-2 relative">
                <div className="absolute inset-0 bg-slate-700 rounded-full" />
                <div
                  className={`absolute inset-y-0 left-0 rounded-full transition-all duration-700 ${
                    isCompleted
                      ? "bg-cyan-500 w-full"
                      : isActive
                      ? "bg-cyan-500/50 w-1/2"
                      : "bg-transparent w-0"
                  }`}
                />
              </div>
            )}
          </div>
        );
      })}
    </div>
  );
}
