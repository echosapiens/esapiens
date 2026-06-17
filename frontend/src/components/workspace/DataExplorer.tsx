"use client";

import { useState, useCallback } from "react";
import { cn } from "@/lib/utils";
import { FolderOpen, File, ChevronRight, ChevronDown, Download, Upload, Folder } from "lucide-react";

interface FileNode {
  name: string;
  type: "file" | "directory";
  size?: number;
  lastModified?: string;
  children?: FileNode[];
}

interface DataExplorerProps { sessionId: string; }

export function DataExplorer({ sessionId }: DataExplorerProps) {
  const [expandedPaths, setExpandedPaths] = useState<Set<string>>(new Set());
  const [selectedFile, setSelectedFile] = useState<string | null>(null);

  const toggleExpand = useCallback((path: string) => {
    setExpandedPaths((prev) => { const next = new Set(prev); next.has(path) ? next.delete(path) : next.add(path); return next; });
  }, []);

  return (
    <div className="flex h-full flex-col">
      <div className="mb-3 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <FolderOpen className="h-4 w-4" style={{ color: "var(--accent-gold)" }} />
          <h3 className="text-sm font-semibold" style={{ color: "var(--text-primary)" }}>Data Explorer</h3>
        </div>
        <span className="text-xs" style={{ color: "var(--text-muted)" }}>Session: {sessionId.slice(0, 8)}&hellip;</span>
      </div>

      <div className="flex-1 overflow-auto card">
        <div className="flex h-full flex-col items-center justify-center gap-3 p-6 text-center">
          <div className="rounded-full p-3" style={{ background: "var(--brand-gold-dim)" }}>
            <Folder className="h-8 w-8" style={{ color: "var(--accent-gold)" }} />
          </div>
          <div>
            <h4 className="text-sm font-medium" style={{ color: "var(--text-primary)" }}>No files yet</h4>
            <p className="mt-1 text-xs" style={{ color: "var(--text-muted)" }}>Upload data or run a pipeline to generate output files.</p>
          </div>
          <button disabled className="btn btn-ghost mt-2 text-xs opacity-50" title="Upload coming soon">
            <Upload className="h-3.5 w-3.5" />
            Upload files
          </button>
        </div>
      </div>

      {selectedFile && <FileDetails path={selectedFile} />}
    </div>
  );
}

function FileTreeNode({ node, path, depth, expandedPaths, selectedFile, onToggle, onSelect }: {
  node: FileNode; path: string; depth: number; expandedPaths: Set<string>; selectedFile: string | null;
  onToggle: (path: string) => void; onSelect: (path: string) => void;
}) {
  const isExpanded = expandedPaths.has(path);
  const isSelected = selectedFile === path;

  if (node.type === "directory") {
    return (
      <div>
        <button onClick={() => onToggle(path)} className={cn("flex w-full items-center gap-1.5 rounded px-2 py-1 text-sm hover:bg-hover", isSelected && "bg-gold/10")}
          style={{ paddingLeft: `${depth * 16 + 8}px`, background: isSelected ? "var(--brand-gold-dim)" : undefined }}>
          {isExpanded ? <ChevronDown className="h-3.5 w-3.5 shrink-0" style={{ color: "var(--text-muted)" }} /> : <ChevronRight className="h-3.5 w-3.5 shrink-0" style={{ color: "var(--text-muted)" }} />}
          <FolderOpen className="h-4 w-4 shrink-0" style={{ color: "var(--accent-gold)" }} />
          <span className="truncate" style={{ color: "var(--text-primary)" }}>{node.name}</span>
        </button>
        {isExpanded && node.children && <div>{node.children.map((child) => <FileTreeNode key={child.name} node={child} path={`${path}/${child.name}`} depth={depth + 1} expandedPaths={expandedPaths} selectedFile={selectedFile} onToggle={onToggle} onSelect={onSelect} />)}</div>}
      </div>
    );
  }

  return (
    <button onClick={() => onSelect(path)} className={cn("flex w-full items-center gap-1.5 rounded px-2 py-1 text-sm hover:bg-hover", isSelected && "bg-gold/10")}
      style={{ paddingLeft: `${depth * 16 + 8}px`, background: isSelected ? "var(--brand-gold-dim)" : undefined }}>
      <File className="h-4 w-4 shrink-0" style={{ color: "var(--text-muted)" }} />
      <span className="flex-1 truncate" style={{ color: "var(--text-primary)" }}>{node.name}</span>
      {node.size != null && <span className="text-xs" style={{ color: "var(--text-muted)" }}>{formatFileSize(node.size)}</span>}
    </button>
  );
}

function FileDetails({ path }: { path: string }) {
  const fileName = path.split("/").pop() || path;
  return (
    <div className="mt-3 card p-3">
      <div className="mb-2 flex items-center justify-between">
        <h4 className="text-sm font-medium" style={{ color: "var(--text-primary)" }}>{fileName}</h4>
        <button disabled className="btn btn-ghost text-xs opacity-50" title="Download coming soon">
          <Download className="h-3.5 w-3.5" />
          Download
        </button>
      </div>
      <p className="text-xs" style={{ color: "var(--text-muted)" }}>File details will be available once the backend S3 integration is enabled.</p>
    </div>
  );
}

function formatFileSize(bytes: number): string {
  if (bytes >= 1_000_000_000) return `${(bytes / 1_000_000_000).toFixed(1)} GB`;
  if (bytes >= 1_000_000) return `${(bytes / 1_000_000).toFixed(1)} MB`;
  if (bytes >= 1_000) return `${(bytes / 1_000).toFixed(1)} KB`;
  return `${bytes} B`;
}