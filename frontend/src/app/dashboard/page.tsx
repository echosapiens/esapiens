import Link from "next/link";
import JobDashboard from "@/components/JobDashboard";

export default function DashboardPage() {
  return (
    <div className="max-w-3xl mx-auto px-4 py-8">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold text-slate-100">Dashboard</h1>
          <p className="text-sm text-slate-400 mt-1">
            Monitor and manage your pipeline jobs
          </p>
        </div>
        <Link
          href="/"
          className="px-4 py-2 bg-cyan-600 hover:bg-cyan-500 text-white rounded-lg text-sm font-medium transition-colors focus:outline-none focus:ring-2 focus:ring-cyan-500 focus:ring-offset-2 focus:ring-offset-slate-900"
        >
          New Pipeline
        </Link>
      </div>

      <JobDashboard />
    </div>
  );
}