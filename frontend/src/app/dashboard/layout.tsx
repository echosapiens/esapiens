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
  Settings,
  Activity,
} from "lucide-react";

// ── Dashboard layout with macOS sidebar ─────────────────────────────────

export default function DashboardLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const pathname = usePathname();

  const isDashboard = pathname === "/dashboard";
  const isJobs = pathname === "/dashboard/jobs";

  const { data: sessions = [] } = useQuery({
    queryKey: ["sessions"],
    queryFn: () => api.listSessions(),
  });

  const { data: grants = [] } = useQuery({
    queryKey: ["grants"],
    queryFn: () => api.listGrants(),
  });

  const { data: jobsData } = useQuery({
    queryKey: ["jobs", "sidebar"],
    queryFn: () => api.listJobs(false),
    refetchInterval: 5000,
  });
  const activeRuns = jobsData?.total_active ?? 0;
  const completedRecent = jobsData?.recent?.filter((j) => j.status === "completed").length ?? 0;
  const failedRecent = jobsData?.recent?.filter((j) => j.status === "failed").length ?? 0;
  const runningPipelines = activeRuns;

  return (
    <div className="flex h-screen" style={{ background: "var(--mac-window-bg)" }}>
      {/* ── macOS Sidebar ──────────────────────────────────────────── */}
      <aside
        className={cn(
          "mac-sidebar flex flex-col transition-all duration-200",
          sidebarCollapsed ? "w-14" : "w-56"
        )}
      >
        {/* ── Sidebar header with traffic lights ──────────────────── */}
        <div className="mac-sidebar-header">
          <div className="mac-traffic-lights">
            <div className="mac-traffic-light mac-traffic-close" title="Close" />
            <div className="mac-traffic-light mac-traffic-minimize" title="Minimize" />
            <div className="mac-traffic-light mac-traffic-zoom" title="Zoom" />
          </div>
          {!sidebarCollapsed && (
            <div className="flex items-center gap-1.5 ml-1">
              <FlaskConical className="h-4 w-4 text-gold" />
              <span className="text-sm font-semibold text-white/90">E.sapiens</span>
            </div>
          )}
        </div>

        {/* ── Navigation ──────────────────────────────────────────── */}
        <nav className="flex-1 overflow-y-auto mac-sidebar-section">
          <div>
            <button
              onClick={() => {}}
              className={cn(
                "mac-sidebar-item",
                isDashboard && "active"
              )}
            >
              <LayoutDashboard className="h-4 w-4 shrink-0" />
              {!sidebarCollapsed && "Dashboard"}
            </button>
          </div>
          <div>
            <button
              onClick={() => {}}
              className={cn(
                "mac-sidebar-item",
                isJobs && "active"
              )}
            >
              <Activity className="h-4 w-4 shrink-0" />
              {!sidebarCollapsed && "Job Monitor"}
            </button>
          </div>

          {/* ── Sessions list ─────────────────────────────────────── */}
          <div className="mt-4">
            <div className="mac-sidebar-section-header">
              {!sidebarCollapsed && <span>Sessions</span>}
              <Link href="/dashboard" className="text-white/40 hover:text-gold transition-colors">
                <Plus className="h-3.5 w-3.5" />
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

          {/* ── Pipeline status ────────────────────────────────────── */}
          {!sidebarCollapsed && (
            <div className="mt-4">
              <div className="mac-sidebar-section-header">
                <span>Pipeline Status</span>
              </div>
              <div className="space-y-0.5">
                <PipelineStatusItem label="Running" count={runningPipelines} color="bg-system-blue" />
                <PipelineStatusItem label="Completed" count={completedRecent} color="bg-system-green" />
                <PipelineStatusItem label="Failed" count={failedRecent} color="bg-system-red" />
              </div>
            </div>
          )}

          {/* ── Grants overview ────────────────────────────────────── */}
          {!sidebarCollapsed && grants.length > 0 && (
            <div className="mt-4">
              <div className="mac-sidebar-section-header">
                <span>Grants</span>
              </div>
              <div className="space-y-0.5">
                {grants.slice(0, 3).map((grant) => (
                  <div
                    key={grant.id}
                    className="mac-sidebar-item flex items-center justify-between"
                    style={{ cursor: "default" }}
                  >
                    <div className="flex items-center gap-2 min-w-0">
                      <Wallet className="h-3.5 w-3.5 shrink-0 text-gold" />
                      <span className="truncate text-xs text-white/60">{grant.name}</span>
                    </div>
                    <span
                      className={cn(
                        "text-[10px] font-medium",
                        grant.status === "active" ? "text-system-green" : "text-system-red"
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

        {/* ── Sidebar footer ───────────────────────────────────────── */}
        <div className="mac-sidebar-footer">
          <button className="mac-sidebar-item">
            <Settings className="h-4 w-4 shrink-0" />
            {!sidebarCollapsed && "Settings"}
          </button>
        </div>

        {/* ── Collapse toggle ─────────────────────────────────────── */}
        <button
          onClick={() => setSidebarCollapsed(!sidebarCollapsed)}
          className="flex h-7 items-center justify-center border-t border-white/10 text-white/40 hover:text-white/80 transition-colors"
        >
          {sidebarCollapsed ? (
            <ChevronRight className="h-3.5 w-3.5" />
          ) : (
            <ChevronLeft className="h-3.5 w-3.5" />
          )}
        </button>
      </aside>

      {/* ── Main content ──────────────────────────────────────────────── */}
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
      className={cn("mac-sidebar-item", isActive && "active")}
      title={session.title}
    >
      <GitBranch className="h-3.5 w-3.5 shrink-0" />
      {!collapsed && (
        <span className="truncate text-xs">
          {session.title.length > 22
            ? session.title.slice(0, 22) + "\u2026"
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
    <div className="flex items-center justify-between px-3 py-1 text-xs">
      <div className="flex items-center gap-2">
        <span className={cn("h-1.5 w-1.5 rounded-full", color)} />
        <span className="text-white/50">{label}</span>
      </div>
      <span className="font-medium text-white/80">{count}</span>
    </div>
  );
}