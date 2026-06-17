"use client";

// ── macOS skeleton primitives ──────────────────────────────────────────

function MacSkeleton({ className }: { className?: string }) {
  return <div className={cn("mac-skeleton", className)} />;
}

import { cn } from "@/lib/utils";

export function Skeleton({ className }: { className?: string }) {
  return <div className={cn("mac-skeleton", className)} />;
}

// ── Dashboard skeleton ──────────────────────────────────────────────────

export function DashboardSkeleton() {
  return (
    <div className="flex h-full flex-col overflow-auto">
      {/* Toolbar */}
      <div className="h-9" style={{ background: "var(--mac-toolbar-bg)", borderBottom: "1px solid var(--mac-toolbar-separator)" }}>
        <div className="flex items-center h-full px-3 gap-3">
          <MacSkeleton className="h-3 w-24" />
          <MacSkeleton className="h-3 w-16" />
        </div>
      </div>
      {/* Stats */}
      <div className="grid grid-cols-3 gap-3 px-4 py-3">
        {[0, 1, 2].map((i) => (
          <div key={i} className="mac-card flex items-center gap-3 px-4 py-3">
            <MacSkeleton className="h-9 w-9 rounded-lg" />
            <div className="flex-1">
              <MacSkeleton className="h-4 w-12" />
              <MacSkeleton className="mt-1 h-2 w-16" />
            </div>
          </div>
        ))}
      </div>
      {/* Cards grid */}
      <div className="flex-1 px-4">
        <MacSkeleton className="mb-3 h-3 w-24" />
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {[0, 1, 2, 3, 4, 5].map((i) => (
            <div key={i} className="mac-card p-4">
              <div className="mb-2 flex justify-between">
                <MacSkeleton className="h-3 w-28" />
                <MacSkeleton className="h-3 w-12" />
              </div>
              <MacSkeleton className="h-2 w-20" />
              <div className="mt-3 flex justify-between">
                <MacSkeleton className="h-6 w-14 rounded-md" />
                <MacSkeleton className="h-3 w-3" />
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

// ── Session skeleton ────────────────────────────────────────────────────

export function SessionSkeleton() {
  return (
    <div className="flex h-full flex-col">
      {/* Titlebar */}
      <div className="flex items-center h-[38px] px-3" style={{ background: "var(--mac-toolbar-bg)", borderBottom: "1px solid var(--mac-toolbar-separator)" }}>
        <div className="flex gap-[7px]">
          <MacSkeleton className="h-3 w-3 rounded-full" />
          <MacSkeleton className="h-3 w-3 rounded-full" />
          <MacSkeleton className="h-3 w-3 rounded-full" />
        </div>
        <MacSkeleton className="h-3 w-32 mx-auto" />
        <MacSkeleton className="h-3 w-20" />
      </div>
      {/* Split pane */}
      <div className="flex flex-1 overflow-hidden">
        <div className="w-2/5 min-w-[320px] p-3 space-y-3" style={{ borderRight: "1px solid var(--mac-separator)" }}>
          <MacSkeleton className="h-3 w-20" />
          {[0, 1, 2].map((i) => (
            <div key={i} className="space-y-1.5">
              <MacSkeleton className="h-2 w-full" />
              <MacSkeleton className="h-2 w-4/5" />
              <MacSkeleton className="h-2 w-3/5" />
            </div>
          ))}
          <MacSkeleton className="h-8 w-full rounded-md" />
        </div>
        <div className="flex-1 p-3 space-y-2">
          <MacSkeleton className="h-3 w-32" />
          {[0, 1, 2, 3].map((i) => (
            <MacSkeleton key={i} className="h-10 w-full rounded-lg" />
          ))}
        </div>
      </div>
    </div>
  );
}