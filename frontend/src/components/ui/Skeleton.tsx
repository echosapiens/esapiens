"use client";

import { cn } from "@/lib/utils";

function SkeletonBlock({ className }: { className?: string }) {
  return <div className={cn("skeleton", className)} />;
}

export function Skeleton({ className }: { className?: string }) {
  return <div className={cn("skeleton", className)} />;
}

export function DashboardSkeleton() {
  return (
    <div className="flex h-full flex-col overflow-auto">
      <div className="topbar">
        <div className="flex items-center h-full px-3 gap-3">
          <SkeletonBlock className="h-3 w-24" />
          <SkeletonBlock className="h-3 w-16" />
        </div>
      </div>
      <div className="grid grid-cols-3 gap-3 px-4 py-3">
        {[0, 1, 2].map((i) => (
          <div key={i} className="card flex items-center gap-3 px-4 py-3">
            <SkeletonBlock className="h-9 w-9 rounded-lg" />
            <div className="flex-1"><SkeletonBlock className="h-4 w-12" /><SkeletonBlock className="mt-1 h-2 w-16" /></div>
          </div>
        ))}
      </div>
      <div className="flex-1 px-4">
        <SkeletonBlock className="mb-3 h-3 w-24" />
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {[0, 1, 2, 3, 4, 5].map((i) => (
            <div key={i} className="card p-4">
              <div className="mb-2 flex justify-between"><SkeletonBlock className="h-3 w-28" /><SkeletonBlock className="h-3 w-12" /></div>
              <SkeletonBlock className="h-2 w-20" />
              <div className="mt-3 flex justify-between"><SkeletonBlock className="h-6 w-14 rounded-md" /><SkeletonBlock className="h-3 w-3" /></div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

export function SessionSkeleton() {
  return (
    <div className="flex h-full flex-col">
      <div className="topbar">
        <SkeletonBlock className="h-3 w-32" />
        <SkeletonBlock className="h-3 w-20 ml-auto" />
      </div>
      <div className="flex flex-1 overflow-hidden">
        <div className="w-2/5 min-w-[320px] p-3 space-y-3" style={{ borderRight: "1px solid var(--border-default)" }}>
          <SkeletonBlock className="h-3 w-20" />
          {[0, 1, 2].map((i) => (
            <div key={i} className="space-y-1.5"><SkeletonBlock className="h-2 w-full" /><SkeletonBlock className="h-2 w-4/5" /><SkeletonBlock className="h-2 w-3/5" /></div>
          ))}
          <SkeletonBlock className="h-8 w-full rounded-md" />
        </div>
        <div className="flex-1 p-3 space-y-2">
          <SkeletonBlock className="h-3 w-32" />
          {[0, 1, 2, 3].map((i) => <SkeletonBlock key={i} className="h-10 w-full rounded-lg" />)}
        </div>
      </div>
    </div>
  );
}