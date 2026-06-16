"use client";

import { useState, useCallback } from "react";
import { cn } from "@/lib/utils";
import {
  FolderOpen,
  File,
  ChevronRight,
  ChevronDown,
  Download,
  HardDrive,
  RefreshCw,
} from "lucide-react";

// ── Data explorer (S3/Volume file browser) ──────────────────────────────
// Note: The backend doesn't have a dedicated files API yet, so this
// component provides the UI structure with mock data. When the backend
// adds a /sessions/{id}/files endpoint, wire it up with useQuery.

interface FileNode {
  name: string;
  type: "file" | "directory";
  size?: number;
  lastModified?: string;
  children?: FileNode[];
}

const MOCK_FILE_TREE: FileNode[] = [
  {
    name: "data",
    type: "directory",
    children: [
      {
        name: "raw",
        type: "directory",
        children: [
          { name: "sample_R1.fastq.gz", type: "file", size: 2_450_000_000, lastModified: "2025-01-15T10:30:00Z" },
          { name: "sample_R2.fastq.gz", type: "file", size: 2_310_000_000, lastModified: "2025-01-15T10:31:00Z" },
        ],
      },
      {
        name: "reference",
        type: "directory",
        children: [
          { name: "hg38.fa", type: "file", size: 3_100_000_000, lastModified: "2024-12-01T08:00:00Z" },
          { name: "hg38.fa.fai", type: "file", size: 150_000, lastModified: "2024-12-01T08:00:00Z" },
        ],
      },
    ],
  },
  {
    name: "results",
    type: "directory",
    children: [
      { name: "aligned.bam", type: "file", size: 5_200_000_000, lastModified: "2025-01-16T14:20:00Z" },
      { name: "aligned.bam.bai", type: "file", size: 4_500_000, lastModified: "2025-01-16T14:21:00Z" },
      { name: "variants.vcf.gz", type: "file", size: 890_000_000, lastModified: "2025-01-16T16:45:00Z" },
      { name: "qc_report.html", type: "file", size: 2_400_000, lastModified: "2025-01-16T13:10:00Z" },
    ],
  },
  {
    name: "logs",
    type: "directory",
    children: [
      { name: "pipeline.log", type: "file", size: 1_200_000, lastModified: "2025-01-16T17:00:00Z" },
      { name: "alignment.stderr", type: "file", size: 45_000, lastModified: "2025-01-16T14:15:00Z" },
    ],
  },
];

interface DataExplorerProps {
  sessionId: string;
}

export function DataExplorer({ sessionId }: DataExplorerProps) {
  const [expandedPaths, setExpandedPaths] = useState<Set<string>>(
    new Set(["data", "results"])
  );
  const [selectedFile, setSelectedFile] = useState<string | null>(null);

  const toggleExpand = useCallback((path: string) => {
    setExpandedPaths((prev) => {
      const next = new Set(prev);
      if (next.has(path)) {
        next.delete(path);
      } else {
        next.add(path);
      }
      return next;
    });
  }, []);

  return (
    <div className="flex h-full flex-col">
      {/* ── Header ─────────────────────────────────────────────────── */}
      <div className="mb-3 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <FolderOpen className="h-5 w-5 text-gold" />
          <h3 className="text-sm font-semibold text-navy">Data Explorer</h3>
        </div>
        <span className="text-xs text-muted-foreground">
          Session: {sessionId.slice(0, 8)}…
        </span>
      </div>

      {/* ── Tree view ──────────────────────────────────────────────── */}
      <div className="flex-1 overflow-auto rounded-md border border-border bg-white">
        <div className="p-2">
          {MOCK_FILE_TREE.map((node) => (
            <FileTreeNode
              key={node.name}
              node={node}
              path={node.name}
              depth={0}
              expandedPaths={expandedPaths}
              selectedFile={selectedFile}
              onToggle={toggleExpand}
              onSelect={setSelectedFile}
            />
          ))}
        </div>
      </div>

      {/* ── Selected file details ──────────────────────────────────── */}
      {selectedFile && (
        <FileDetails path={selectedFile} />
      )}
    </div>
  );
}

// ── File tree node ──────────────────────────────────────────────────────

interface FileTreeNodeProps {
  node: FileNode;
  path: string;
  depth: number;
  expandedPaths: Set<string>;
  selectedFile: string | null;
  onToggle: (path: string) => void;
  onSelect: (path: string) => void;
}

function FileTreeNode({
  node,
  path,
  depth,
  expandedPaths,
  selectedFile,
  onToggle,
  onSelect,
}: FileTreeNodeProps) {
  const isExpanded = expandedPaths.has(path);
  const isSelected = selectedFile === path;

  if (node.type === "directory") {
    return (
      <div>
        <button
          onClick={() => onToggle(path)}
          className={cn(
            "flex w-full items-center gap-1.5 rounded px-2 py-1 text-sm hover:bg-cream-200",
            isSelected && "bg-gold/10"
          )}
          style={{ paddingLeft: `${depth * 16 + 8}px` }}
        >
          {isExpanded ? (
            <ChevronDown className="h-3.5 w-3.5 shrink-0 text-muted-foreground" />
          ) : (
            <ChevronRight className="h-3.5 w-3.5 shrink-0 text-muted-foreground" />
          )}
          <FolderOpen className="h-4 w-4 shrink-0 text-gold" />
          <span className="truncate text-navy">{node.name}</span>
        </button>
        {isExpanded && node.children && (
          <div>
            {node.children.map((child) => (
              <FileTreeNode
                key={child.name}
                node={child}
                path={`${path}/${child.name}`}
                depth={depth + 1}
                expandedPaths={expandedPaths}
                selectedFile={selectedFile}
                onToggle={onToggle}
                onSelect={onSelect}
              />
            ))}
          </div>
        )}
      </div>
    );
  }

  return (
    <button
      onClick={() => onSelect(path)}
      className={cn(
        "flex w-full items-center gap-1.5 rounded px-2 py-1 text-sm hover:bg-cream-200",
        isSelected && "bg-gold/10"
      )}
      style={{ paddingLeft: `${depth * 16 + 8}px` }}
    >
      <File className="h-4 w-4 shrink-0 text-muted-foreground" />
      <span className="flex-1 truncate text-navy">{node.name}</span>
      {node.size != null && (
        <span className="text-xs text-muted-foreground">
          {formatFileSize(node.size)}
        </span>
      )}
    </button>
  );
}

// ── File details panel ──────────────────────────────────────────────────

function FileDetails({ path }: { path: string }) {
  // Find the file node from the mock tree
  const parts = path.split("/");
  let node: FileNode | undefined;
  let current: FileNode[] = MOCK_FILE_TREE;
  for (const part of parts) {
    node = current.find((n) => n.name === part);
    if (node?.children) {
      current = node.children;
    }
  }

  if (!node || node.type !== "file") {
    return null;
  }

  return (
    <div className="mt-3 rounded-md border border-border bg-white p-3">
      <div className="mb-2 flex items-center justify-between">
        <h4 className="text-sm font-medium text-navy">{node.name}</h4>
        <button className="btn-ghost inline-flex items-center gap-1 text-xs">
          <Download className="h-3.5 w-3.5" />
          Download
        </button>
      </div>
      <div className="grid grid-cols-2 gap-2 text-xs">
        {node.size != null && (
          <div>
            <span className="text-muted-foreground">Size: </span>
            <span className="text-navy">{formatFileSize(node.size)}</span>
          </div>
        )}
        {node.lastModified && (
          <div>
            <span className="text-muted-foreground">Modified: </span>
            <span className="text-navy">{node.lastModified}</span>
          </div>
        )}
      </div>
      <p className="mt-2 text-xs text-muted-foreground">
        Pre-signed download URLs will be available when the backend S3 integration is enabled.
      </p>
    </div>
  );
}

// ── Format file size ───────────────────────────────────────────────────

function formatFileSize(bytes: number): string {
  if (bytes >= 1_000_000_000) {
    return `${(bytes / 1_000_000_000).toFixed(1)} GB`;
  }
  if (bytes >= 1_000_000) {
    return `${(bytes / 1_000_000).toFixed(1)} MB`;
  }
  if (bytes >= 1_000) {
    return `${(bytes / 1_000).toFixed(1)} KB`;
  }
  return `${bytes} B`;
}