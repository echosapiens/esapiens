"use client";

import { useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { api, type SessionRead, type GrantRead } from "@/lib/api";
import { cn, formatCurrency } from "@/lib/utils";
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
    <div className="flex h-screen" style={{ background: "var(--bg-base)" }}>
      {/* ── Sidebar ──────────────────────────────────────────────────── */}
      <aside
        className="sidebar"
        style={{ width: sidebarCollapsed ? "var(--sidebar-collapsed-width)" : "var(--sidebar-width)" }}
      >
        {/* ── Header ──────────────────────────────────────────────── */}
        <div className="sidebar-header">
          <FlaskConical className="h-4 w-4 shrink-0" style={{ color: "var(--accent-gold)" }} />
          {!sidebarCollapsed && (
            <span className="text-sm font-semibold" style={{ color: "var(--text-primary)" }}>
              E.sapiens
            </span>
          )}
        </div>

        {/* ── Navigation ────────────────────────────────────────── */}
        <nav className="flex-1 overflow-y-auto sidebar-section">
          <div>
            <Link
              href="/dashboard"
              className={cn("sidebar-item", isDashboard && "active")}
            >
              <LayoutDashboard className="h-4 w-4 shrink-0" />
              {!sidebarCollapsed && "Dashboard"}
            </Link>
          </div>
          <div>
            <Link
              href="/dashboard/jobs"
              className={cn("sidebar-item", isJobs && "active")}
            >
              <Activity className="h-4 w-4 shrink-0" />
              {!sidebarCollapsed && "Job Monitor"}
            </Link>
          </div>

          {/* ── Sessions ─────────────────────────────────────────── */}
          <div className="mt-4">
            <div className="sidebar-section-title">
              {!sidebarCollapsed && <span>Sessions</span>}
              <Link href="/dashboard" className="hover:text-gold transition-colors" style={{ color: "var(--text-muted)" }}>
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

          {/* ── Pipeline status ──────────────────────────────────── */}
          {!sidebarCollapsed && (
            <div className="mt-4">
              <div className="sidebar-section-title">
                <span>Pipeline Status</span>
              </div>
              <div className="space-y-0.5">
                <PipelineStatusItem label="Running" count={runningPipelines} color="bg-accent-blue" />
                <PipelineStatusItem label="Completed" count={completedRecent} color="bg-accent-green" />
                <PipelineStatusItem label="Failed" count={failedRecent} color="bg-accent-red" />
              </div>
            </div>
          )}

          {/* ── Grants ───────────────────────────────────────────── */}
          {!sidebarCollapsed && grants.length > 0 && (
            <div className="mt-4">
              <div className="sidebar-section-title">
                <span>Grants</span>
              </div>
              <div className="space-y-0.5">
                {grants.slice(0, 3).map((grant) => (
                  <div
                    key={grant.id}
                    className="sidebar-item"
                    style={{ cursor: "default" }}
                  >
                    <div className="flex items-center gap-2 min-w-0 flex-1">
                      <Wallet className="h-3.5 w-3.5 shrink-0" style={{ color: "var(--accent-gold)" }} />
                      <span className="truncate text-xs" style={{ color: "var(--text-secondary)" }}>{grant.name}</span>
                    </div>
                    <span
                      className="text-[10px] font-medium shrink-0"
                      style={{ color: grant.status === "active" ? "var(--accent-green)" : "var(--accent-red)" }}
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
        <div className="sidebar-footer">
          <button className="sidebar-item">
            <Settings className="h-4 w-4 shrink-0" />
            {!sidebarCollapsed && "Settings"}
          </button>
        </div>

        {/* ── Collapse toggle ────────────────────────────────────── */}
        <button
          onClick={() => setSidebarCollapsed(!sidebarCollapsed)}
          className="flex h-7 items-center justify-center border-t"
          style={{ borderColor: "var(--border-default)", color: "var(--text-muted)" }}
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
      className={cn("sidebar-item", isActive && "active")}
      title={session.title}
    >
      <GitBranch className="h-3.5 w-3.5 shrink-0" />
      {!collapsed && (
        <span className="truncate text-xs">
          {session.title.length > 24
            ? session.title.slice(0, 24) + "\u2026"
            : session.title}
        </span>
      )}
    </Link>
  );
}

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
        <span style={{ color: "var(--text-muted)" }}>{label}</span>
      </div>
      <span className="font-medium" style={{ color: "var(--text-secondary)" }}>{count}</span>
    </div>
  );
}