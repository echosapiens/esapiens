"use client";

import { useState, useCallback } from "react";
import { cn } from "@/lib/utils";
import {
  FolderOpen,
  File,
  ChevronRight,
  ChevronDown,
  Download,
  Upload,
  Folder,
} from "lucide-react";

// ── Data explorer (S3/Volume file browser) ──────────────────────────────
// Backend doesn't have a dedicated files API yet, so this component
// shows an empty state. When the backend adds a /sessions/{id}/files
// endpoint, wire it up with useQuery and populate the tree.

interface FileNode {
  name: string;
  type: "file" | "directory";
  size?: number;
  lastModified?: string;
  children?: FileNode[];
}

interface DataExplorerProps {
  sessionId: string;
}

export function DataExplorer({ sessionId }: DataExplorerProps) {
  const [expandedPaths, setExpandedPaths] = useState<Set<string>>(new Set());
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

      {/* ── Empty state ────────────────────────────────────────────── */}
      <div className="flex-1 overflow-auto mac-card">
        <div className="flex h-full flex-col items-center justify-center gap-3 p-6 text-center">
          <div className="rounded-full bg-gold/10 p-3">
            <Folder className="h-8 w-8 text-gold" />
          </div>
          <div>
            <h4 className="text-sm font-medium text-navy">No files yet</h4>
            <p className="mt-1 text-xs text-muted-foreground">
              Upload data or run a pipeline to generate output files.
            </p>
          </div>
          <button
            disabled
            className="mac-btn-ghost mt-2 inline-flex items-center gap-1.5 text-xs opacity-50"
            title="Upload coming soon"
          >
            <Upload className="h-3.5 w-3.5" />
            Upload files
          </button>
        </div>
      </div>

      {/* ── Selected file details ──────────────────────────────────── */}
      {selectedFile && <FileDetails path={selectedFile} />}
    </div>
  );
}

// ── File tree node (used when files exist) ──────────────────────────────

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
  // Placeholder — will be populated from real file metadata
  const fileName = path.split("/").pop() || path;

  return (
    <div className="mt-3 mac-card p-3">
      <div className="mb-2 flex items-center justify-between">
        <h4 className="text-sm font-medium text-navy">{fileName}</h4>
        <button
          disabled
          className="mac-btn-ghost inline-flex items-center gap-1 text-xs opacity-50"
          title="Download coming soon"
        >
          <Download className="h-3.5 w-3.5" />
          Download
        </button>
      </div>
      <p className="text-xs text-muted-foreground">
        File details will be available once the backend S3 integration is enabled.
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