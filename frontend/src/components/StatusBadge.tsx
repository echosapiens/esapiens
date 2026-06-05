import type { JobStatus } from "@/types";

const statusStyles: Record<JobStatus, { bg: string; text: string; pulse?: boolean }> = {
  pending: { bg: "bg-gray-500/20", text: "text-gray-400" },
  researching: { bg: "bg-blue-500/20", text: "text-blue-400" },
  contracting: { bg: "bg-yellow-500/20", text: "text-yellow-400" },
  queued: { bg: "bg-orange-500/20", text: "text-orange-400" },
  running: { bg: "bg-green-500/20", text: "text-green-400", pulse: true },
  streaming: { bg: "bg-cyan-500/20", text: "text-cyan-400" },
  completed: { bg: "bg-green-500/20", text: "text-green-300" },
  failed: { bg: "bg-red-500/20", text: "text-red-400" },
};

export default function StatusBadge({ status }: { status: JobStatus }) {
  const style = statusStyles[status] ?? statusStyles.pending;

  return (
    <span
      className={`inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-medium ${style.bg} ${style.text} ${
        style.pulse ? "animate-pulse" : ""
      }`}
    >
      <span
        className={`w-1.5 h-1.5 rounded-full ${
          style.pulse ? "bg-green-400" : "bg-current"
        }`}
      />
      {status.charAt(0).toUpperCase() + status.slice(1)}
    </span>
  );
}