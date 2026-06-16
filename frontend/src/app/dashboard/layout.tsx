"use client";

import { useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { api, type SessionRead, type GrantRead } from "@/lib/api";
import { cn, formatRelativeDate, statusColorClass, formatCurrency } from "@/lib/utils";
import {
  FlaskConical,
  Plus,
  GitBranch,
  Wallet,
  ChevronLeft,
  ChevronRight,
  LayoutDashboard,
  LogOut,
  Settings,
  Activity,
} from "lucide-react";

// ── Dashboard layout with sidebar ───────────────────────────────────────

export default function DashboardLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const pathname = usePathname();

  // ── Active route helpers ───────────────────────────────────────────
  const isDashboard = pathname === "/dashboard";
  const isJobs = pathname === "/dashboard/jobs";
  const isSessionPage = pathname.startsWith("/dashboard/session/");

  // ── Fetch sessions for sidebar ───────────────────────────────────
  const { data: sessions = [] } = useQuery({
    queryKey: ["sessions"],
    queryFn: () => api.listSessions(),
  });

  // ── Fetch grants for sidebar ─────────────────────────────────────
  const { data: grants = [] } = useQuery({
    queryKey: ["grants"],
    queryFn: () => api.listGrants(),
  });

  // ── Fetch live pipeline + run counts for the status overview ──────
  // Uses the cross-session /jobs endpoint to count active/recent runs.
  const { data: jobsData } = useQuery({
    queryKey: ["jobs", "sidebar"],
    queryFn: () => api.listJobs(false),
    refetchInterval: 5000,
  });
  const activeRuns = jobsData?.total_active ?? 0;
  const completedRecent = jobsData?.recent?.filter((j) => j.status === "completed").length ?? 0;
  const failedRecent = jobsData?.recent?.filter((j) => j.status === "failed").length ?? 0;
  // Count unique draft pipelines across all sessions
  const draftPipelines = (jobsData?.recent?.length ?? 0) === 0 && activeRuns === 0 ? 0 : 0;
  const runningPipelines = activeRuns;

  return (
    <div className="flex h-screen bg-cream">
      {/* ── Sidebar ─────────────────────────────────────────────────── */}
      <aside
        className={cn(
          "flex flex-col bg-navy text-white transition-all duration-200",
          sidebarCollapsed ? "w-16" : "w-64"
        )}
      >
        {/* ── Logo ──────────────────────────────────────────────── */}
        <div className="flex h-16 items-center gap-2 border-b border-navy-700 px-4">
          <FlaskConical className="h-6 w-6 shrink-0 text-gold" />
          {!sidebarCollapsed && (
            <span className="text-lg font-bold">E.sapiens</span>
          )}
        </div>

        {/* ── Navigation ────────────────────────────────────────── */}
        <nav className="flex-1 overflow-y-auto py-4">
          <div className="px-3 mb-2">
            <Link
              href="/dashboard"
              className={cn(
                "flex items-center gap-2 rounded-md px-3 py-2 text-sm font-medium transition-colors",
                isDashboard
                  ? "bg-navy-700 text-white"
                  : "hover:bg-navy-700 text-navy-200 hover:text-white"
              )}
            >
              <LayoutDashboard className="h-4 w-4 shrink-0" />
              {!sidebarCollapsed && "Dashboard"}
            </Link>
          </div>

          <div className="px-3 mb-2">
            <Link
              href="/dashboard/jobs"
              className={cn(
                "flex items-center gap-2 rounded-md px-3 py-2 text-sm font-medium transition-colors",
                isJobs
                  ? "bg-navy-700 text-white"
                  : "hover:bg-navy-700 text-navy-200 hover:text-white"
              )}
            >
              <Activity className="h-4 w-4 shrink-0" />
              {!sidebarCollapsed && "Job Monitor"}
            </Link>
          </div>

          {/* ── Sessions list ───────────────────────────────────── */}
          <div className="px-3 mt-4">
            <div className="flex items-center justify-between mb-1">
              {!sidebarCollapsed && (
                <span className="text-xs font-medium uppercase tracking-wider text-navy-400">
                  Sessions
                </span>
              )}
              <Link
                href="/dashboard"
                className="text-navy-400 hover:text-gold"
                title="New session"
              >
                <Plus className="h-4 w-4" />
              </Link>
            </div>
            <div className="space-y-0.5">
              {sessions.slice(0, 8).map((session) => (
                <SessionNavItem
                  key={session.id}
                  session={session}
                  collapsed={sidebarCollapsed}
                />
              ))}
            </div>
          </div>

          {/* ── Active pipelines ────────────────────────────────── */}
          {!sidebarCollapsed && (
            <div className="px-3 mt-6">
              <span className="text-xs font-medium uppercase tracking-wider text-navy-400">
                Pipeline Status
              </span>
              <div className="mt-2 space-y-1">
                <PipelineStatusItem
                  label="Running"
                  count={runningPipelines}
                  color="bg-blue-500"
                />
                <PipelineStatusItem
                  label="Completed"
                  count={completedRecent}
                  color="bg-green-500"
                />
                <PipelineStatusItem
                  label="Failed"
                  count={failedRecent}
                  color="bg-red-500"
                />
              </div>
            </div>
          )}

          {/* ── Grants overview ──────────────────────────────────── */}
          {!sidebarCollapsed && grants.length > 0 && (
            <div className="px-3 mt-6">
              <span className="text-xs font-medium uppercase tracking-wider text-navy-400">
                Grants
              </span>
              <div className="mt-2 space-y-1">
                {grants.slice(0, 3).map((grant) => (
                  <div
                    key={grant.id}
                    className="flex items-center justify-between rounded-md px-2 py-1.5 text-xs hover:bg-navy-700"
                  >
                    <div className="flex items-center gap-2 min-w-0">
                      <Wallet className="h-3.5 w-3.5 shrink-0 text-gold" />
                      <span className="truncate text-navy-200">{grant.name}</span>
                    </div>
                    <span
                      className={cn(
                        "text-xs font-medium",
                        grant.status === "active"
                          ? "text-green-400"
                          : "text-red-400"
                      )}
                    >
                      {formatCurrency(grant.spent_budget)} / {formatCurrency(grant.total_budget)}
                    </span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </nav>

        {/* ── Footer ─────────────────────────────────────────────── */}
        <div className="border-t border-navy-700 px-3 py-3">
          <button className="flex w-full items-center gap-2 rounded-md px-3 py-2 text-sm text-navy-300 hover:bg-navy-700 hover:text-white">
            <Settings className="h-4 w-4 shrink-0" />
            {!sidebarCollapsed && "Settings"}
          </button>
        </div>

        {/* ── Collapse toggle ────────────────────────────────────── */}
        <button
          onClick={() => setSidebarCollapsed(!sidebarCollapsed)}
          className="flex h-10 items-center justify-center border-t border-navy-700 text-navy-400 hover:bg-navy-700 hover:text-white"
        >
          {sidebarCollapsed ? (
            <ChevronRight className="h-4 w-4" />
          ) : (
            <ChevronLeft className="h-4 w-4" />
          )}
        </button>
      </aside>

      {/* ── Main content ────────────────────────────────────────────── */}
      <main className="flex-1 overflow-hidden">{children}</main>
    </div>
  );
}

// ── Session nav item ─────────────────────────────────────────────────────

function SessionNavItem({
  session,
  collapsed,
}: {
  session: SessionRead;
  collapsed: boolean;
}) {
  const pathname = usePathname();
  const isActive = pathname === `/dashboard/session/${session.id}`;
  return (
    <Link
      href={`/dashboard/session/${session.id}`}
      className={cn(
        "flex items-center gap-2 rounded-md px-2 py-1.5 text-sm transition-colors",
        isActive
          ? "bg-navy-700 text-white"
          : "text-navy-300 hover:bg-navy-700 hover:text-white"
      )}
      title={session.title}
    >
      <GitBranch className="h-3.5 w-3.5 shrink-0" />
      {!collapsed && (
        <span className="truncate">
          {session.title.length > 20
            ? session.title.slice(0, 20) + "…"
            : session.title}
        </span>
      )}
    </Link>
  );
}

// ── Pipeline status item ─────────────────────────────────────────────────

function PipelineStatusItem({
  label,
  count,
  color,
}: {
  label: string;
  count: number;
  color: string;
}) {
  return (
    <div className="flex items-center justify-between rounded-md px-2 py-1.5 text-xs">
      <div className="flex items-center gap-2">
        <span className={cn("h-2 w-2 rounded-full", color)} />
        <span className="text-navy-300">{label}</span>
      </div>
      <span className="font-medium text-white">{count}</span>
    </div>
  );
}