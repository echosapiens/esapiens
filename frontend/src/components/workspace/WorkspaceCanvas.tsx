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

// ── WorkspaceCanvas — macOS segmented tab bar ────────────────────────────

export function WorkspaceCanvas({ sessionId }: { sessionId: string }) {
  const [activeTab, setActiveTab] = useState<Tab>("pipeline");

  return (
    <div className="flex h-full flex-col" style={{ background: "var(--mac-window-bg)" }}>
      {/* ── macOS segmented tab bar ──────────────────────────────────── */}
      <div className="flex items-center justify-center py-2 border-b" style={{ borderColor: "var(--mac-toolbar-separator)", background: "var(--mac-toolbar-bg)" }}>
        <div className="mac-segmented">
          {tabs.map((tab) => {
            const Icon = tab.icon;
            return (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id)}
                className={cn(
                  "mac-segmented-item",
                  activeTab === tab.id && "active"
                )}
              >
                <Icon className="h-3.5 w-3.5" />
                {tab.label}
              </button>
            );
          })}
        </div>
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

function PipelineTab({ sessionId }: { sessionId: string }) {
  return (
    <div className="flex h-full flex-col" style={{ background: "var(--mac-window-bg)" }}>
      <PipelineGantt sessionId={sessionId} />
    </div>
  );
}

function FilesTab({ sessionId }: { sessionId: string }) {
  return (
    <div className="h-full overflow-auto p-4" style={{ background: "var(--mac-window-bg)" }}>
      <DataExplorer sessionId={sessionId} />
    </div>
  );
}

function InspectorTab({ sessionId }: { sessionId: string }) {
  return (
    <div className="flex h-full flex-col gap-4 overflow-auto p-4" style={{ background: "var(--mac-window-bg)" }}>
      <ExportMethods sessionId={sessionId} />
    </div>
  );
}