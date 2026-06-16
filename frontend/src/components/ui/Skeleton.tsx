"use client";

import { cn } from "@/lib/utils";

// ── Skeleton primitives ──────────────────────────────────────────────────

export function Skeleton({ className }: { className?: string }) {
  return <div className={cn("skeleton rounded-md", className)} />;
}

// ── Dashboard skeleton (session cards) ──────────────────────────────────

export function DashboardSkeleton() {
  return (
    <div className="flex h-full flex-col overflow-auto">
      {/* Header */}
      <div className="glass-heavy border-b border-border px-6 py-4">
        <Skeleton className="h-6 w-32" />
        <Skeleton className="mt-2 h-3 w-56" />
      </div>
      {/* Stats */}
      <div className="grid grid-cols-3 gap-4 border-b border-border px-6 py-4">
        {[0, 1, 2].map((i) => (
          <div key={i} className="glass flex items-center gap-3 px-4 py-3 rounded-xl">
            <Skeleton className="h-10 w-10 rounded-lg" />
            <div className="flex-1">
              <Skeleton className="h-5 w-16" />
              <Skeleton className="mt-1 h-2.5 w-20" />
            </div>
          </div>
        ))}
      </div>
      {/* Cards grid */}
      <div className="flex-1 p-6">
        <Skeleton className="mb-4 h-5 w-36" />
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {[0, 1, 2, 3, 4, 5].map((i) => (
            <div key={i} className="glass p-5 rounded-xl">
              <div className="mb-2 flex justify-between">
                <Skeleton className="h-4 w-32" />
                <Skeleton className="h-4 w-16 rounded-full" />
              </div>
              <Skeleton className="h-3 w-24" />
              <div className="mt-4 flex justify-between">
                <Skeleton className="h-7 w-20 rounded-lg" />
                <Skeleton className="h-4 w-4" />
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

// ── Session page skeleton ────────────────────────────────────────────────

export function SessionSkeleton() {
  return (
    <div className="flex h-full flex-col">
      {/* Session header */}
      <div className="glass-heavy flex items-center justify-between border-b border-border px-4 py-2">
        <div className="flex items-center gap-3">
          <Skeleton className="h-4 w-32" />
          <Skeleton className="h-4 w-12 rounded-full" />
        </div>
        <Skeleton className="h-3 w-40" />
      </div>
      {/* Split pane */}
      <div className="flex flex-1 overflow-hidden">
        {/* Chat */}
        <div className="w-2/5 min-w-[320px] border-r border-border p-4 space-y-4">
          <div className="flex justify-between">
            <Skeleton className="h-5 w-24" />
            <Skeleton className="h-5 w-20" />
          </div>
          {[0, 1, 2].map((i) => (
            <div key={i} className="space-y-1.5">
              <Skeleton className="h-3 w-full" />
              <Skeleton className="h-3 w-4/5" />
              <Skeleton className="h-3 w-3/5" />
            </div>
          ))}
          <Skeleton className="h-10 w-full rounded-lg" />
        </div>
        {/* Workspace */}
        <div className="flex-1 p-4 space-y-4">
          <Skeleton className="h-5 w-48" />
          {[0, 1, 2, 3].map((i) => (
            <Skeleton key={i} className="h-12 w-full rounded-lg" />
          ))}
        </div>
      </div>
    </div>
  );
}

// ── Chat loading skeleton ────────────────────────────────────────────────

export function ChatLoadingBubble() {
  return (
    <div className="flex gap-3">
      <Skeleton className="h-8 w-8 rounded-full" />
      <div className="flex-1 space-y-1.5">
        <Skeleton className="h-3 w-3/4" />
        <Skeleton className="h-3 w-1/2" />
      </div>
    </div>
  );
}