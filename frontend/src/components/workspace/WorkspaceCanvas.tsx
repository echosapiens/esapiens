"use client";

import { useState } from "react";
import { cn } from "@/lib/utils";
import { GitBranch, FolderOpen, Search } from "lucide-react";
import { PipelineGantt } from "@/components/pipeline/PipelineGantt";
import { DataExplorer } from "@/components/workspace/DataExplorer";
import { ExportMethods } from "@/components/workspace/ExportMethods";

type Tab = "pipeline" | "files" | "inspector";

const tabs: { id: Tab; label: string; icon: React.ElementType }[] = [
  { id: "pipeline", label: "Pipeline", icon: GitBranch },
  { id: "files", label: "Files", icon: FolderOpen },
  { id: "inspector", label: "Inspector", icon: Search },
];

// ── WorkspaceCanvas ─────────────────────────────────────────────────────

export function WorkspaceCanvas({ sessionId }: { sessionId: string }) {
  const [activeTab, setActiveTab] = useState<Tab>("pipeline");

  return (
    <div className="flex h-full flex-col glass">
      {/* ── Tab bar ─────────────────────────────────────────────────── */}
      <div className="flex items-center gap-1 border-b border-border glass-heavy px-4 py-2">
        {tabs.map((tab) => {
          const Icon = tab.icon;
          return (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={cn(
                "inline-flex items-center gap-1.5 rounded-md px-3 py-1.5 text-sm font-medium transition-colors",
                activeTab === tab.id
                  ? "glass-navy text-white"
                  : "text-muted-foreground hover:bg-cream-300 hover:text-navy"
              )}
            >
              <Icon className="h-4 w-4" />
              {tab.label}
            </button>
          );
        })}
      </div>

      {/* ── Tab content ─────────────────────────────────────────────── */}
      <div className="flex-1 overflow-hidden">
        {activeTab === "pipeline" && <PipelineTab sessionId={sessionId} />}
        {activeTab === "files" && <FilesTab sessionId={sessionId} />}
        {activeTab === "inspector" && <InspectorTab sessionId={sessionId} />}
      </div>
    </div>
  );
}

// ── Tab panels ──────────────────────────────────────────────────────────

function PipelineTab({ sessionId }: { sessionId: string }) {
  return (
    <div className="flex h-full flex-col">
      <PipelineGantt sessionId={sessionId} />
    </div>
  );
}

function FilesTab({ sessionId }: { sessionId: string }) {
  return (
    <div className="h-full overflow-auto p-4">
      <DataExplorer sessionId={sessionId} />
    </div>
  );
}

function InspectorTab({ sessionId }: { sessionId: string }) {
  return (
    <div className="flex h-full flex-col gap-4 overflow-auto p-4">
      <ExportMethods sessionId={sessionId} />
    </div>
  );
}