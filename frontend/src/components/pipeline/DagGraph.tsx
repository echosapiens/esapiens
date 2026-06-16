"use client";

import { useMemo, useState } from "react";
import { cn } from "@/lib/utils";
import {
  CheckCircle2,
  XCircle,
  Loader2,
  Clock,
  Play,
  AlertTriangle,
} from "lucide-react";

// ── Types ────────────────────────────────────────────────────────────────

interface DagNode {
  name: string;
  status: string;
  container_image: string;
  command_args: string[];
  depends_on: string[];
  started_at?: string | null;
  completed_at?: string | null;
  progress?: number;
}

interface DagGraphProps {
  steps: DagNode[];
  selectedStep: string | null;
  onSelectStep: (name: string | null) => void;
}

// ── Status colors ────────────────────────────────────────────────────────

const STATUS_COLORS: Record<string, { fill: string; stroke: string; text: string }> = {
  completed: { fill: "#dcfce7", stroke: "#22c55e", text: "#166534" },
  running: { fill: "#dbeafe", stroke: "#3b82f6", text: "#1e40af" },
  failed: { fill: "#fee2e2", stroke: "#ef4444", text: "#991b1b" },
  pending: { fill: "#fef9c3", stroke: "#eab308", text: "#854d0e" },
  submitted: { fill: "#f3e8ff", stroke: "#a855f7", text: "#6b21a8" },
  draft: { fill: "#f3f4f6", stroke: "#9ca3af", text: "#4b5563" },
};

const STATUS_ICONS: Record<string, React.ComponentType<{ className?: string; style?: React.CSSProperties }>> = {
  completed: CheckCircle2,
  running: Loader2,
  failed: XCircle,
  pending: Clock,
  submitted: Play,
  draft: Clock,
};

// ── Layout: topological sort + column assignment ────────────────────────

interface PositionedNode extends DagNode {
  x: number;
  y: number;
  col: number;
}

function layoutDag(steps: DagNode[], width: number, height: number): {
  nodes: PositionedNode[];
  edges: { from: string; to: string }[];
  cols: number;
} {
  const NODE_W = 180;
  const NODE_H = 56;
  const COL_GAP = 80;
  const ROW_GAP = 28;

  // Build dependency graph
  const nodeMap = new Map(steps.map((s) => [s.name, s]));
  const deps = new Map<string, string[]>();
  for (const s of steps) {
    deps.set(s.name, s.depends_on.filter((d) => nodeMap.has(d)));
  }

  // Topological sort (Kahn's algorithm)
  const inDegree = new Map<string, number>();
  steps.forEach((s) => inDegree.set(s.name, 0));
  deps.forEach((dlist, name) => {
    // in-degree = number of deps that point TO this node
    inDegree.set(name, dlist.length);
  });

  // Also build reverse map: which nodes depend on this one
  const dependents = new Map<string, string[]>();
  steps.forEach((s) => dependents.set(s.name, []));
  deps.forEach((dlist, name) => {
    dlist.forEach((d) => {
      dependents.get(d)?.push(name);
    });
  });

  // Assign columns: root nodes (no deps) = col 0, each child = max(parent col) + 1
  const colMap = new Map<string, number>();
  const queue = steps.filter((s) => (deps.get(s.name) ?? []).length === 0).map((s) => s.name);
  queue.forEach((n) => colMap.set(n, 0));

  const sorted: string[] = [];
  const tempInDegree = new Map(inDegree);
  while (queue.length > 0) {
    const n = queue.shift()!;
    sorted.push(n);
    for (const dep of dependents.get(n) ?? []) {
      const newDeg = (tempInDegree.get(dep) ?? 1) - 1;
      tempInDegree.set(dep, newDeg);
      if (newDeg === 0) queue.push(dep);
    }
  }

  // Handle cycles: any unsorted nodes go to the end
  for (const s of steps) {
    if (!sorted.includes(s.name)) sorted.push(s.name);
  }

  // Compute columns via longest path from roots
  for (const name of sorted) {
    const dlist = deps.get(name) ?? [];
    if (dlist.length === 0) {
      colMap.set(name, 0);
    } else {
      const maxParentCol = Math.max(...dlist.map((d) => colMap.get(d) ?? 0));
      colMap.set(name, maxParentCol + 1);
    }
  }

  const cols = Math.max(...Array.from(colMap.values()), 0) + 1;

  // Group by column and assign Y positions
  const colGroups = new Map<number, string[]>();
  for (const [name, col] of colMap) {
    if (!colGroups.has(col)) colGroups.set(col, []);
    colGroups.get(col)!.push(name);
  }

  const positioned: PositionedNode[] = [];
  for (let col = 0; col < cols; col++) {
    const names = colGroups.get(col) ?? [];
    names.forEach((name, idx) => {
      const step = nodeMap.get(name)!;
      positioned.push({
        ...step,
        col,
        x: col * (NODE_W + COL_GAP) + 24,
        y: idx * (NODE_H + ROW_GAP) + 24,
      });
    });
  }

  // Build edges
  const edges: { from: string; to: string }[] = [];
  for (const step of steps) {
    for (const dep of step.depends_on) {
      if (nodeMap.has(dep)) {
        edges.push({ from: dep, to: step.name });
      }
    }
  }

  return { nodes: positioned, edges, cols };
}

// ── DAG graph component ──────────────────────────────────────────────────

export function DagGraph({ steps, selectedStep, onSelectStep }: DagGraphProps) {
  const [hoveredStep, setHoveredStep] = useState<string | null>(null);

  const { nodes, edges, cols } = useMemo(() => layoutDag(steps, 0, 0), [steps]);

  const NODE_W = 180;
  const NODE_H = 56;
  const COL_GAP = 80;
  const ROW_GAP = 28;
  const PAD = 24;

  // Compute SVG dimensions
  const maxColHeight = useMemo(() => {
    const colHeights = new Map<number, number>();
    nodes.forEach((n) => {
      colHeights.set(n.col, (colHeights.get(n.col) ?? 0) + 1);
    });
    let maxH = 0;
    colHeights.forEach((c) => { maxH = Math.max(maxH, c); });
    return maxH;
  }, [nodes]);

  const svgWidth = cols * (NODE_W + COL_GAP) + PAD * 2 - COL_GAP;
  const svgHeight = maxColHeight * (NODE_H + ROW_GAP) + PAD * 2 - ROW_GAP;

  const nodeByName = useMemo(() => new Map(nodes.map((n) => [n.name, n])), [nodes]);

  // ── Edge path: orthogonal from right edge of source to left edge of target
  function edgePath(from: PositionedNode, to: PositionedNode): string {
    const x1 = from.x + NODE_W;
    const y1 = from.y + NODE_H / 2;
    const x2 = to.x;
    const y2 = to.y + NODE_H / 2;
    const midX = (x1 + x2) / 2;
    return `M ${x1} ${y1} C ${midX} ${y1}, ${midX} ${y2}, ${x2} ${y2}`;
  }

  if (steps.length === 0) {
    return null;
  }

  return (
    <div className="w-full overflow-auto rounded-xl glass p-2">
      <svg
        width={Math.max(svgWidth, 200)}
        height={Math.max(svgHeight, 100)}
        className="min-w-full"
      >
        {/* ── Edges ─────────────────────────────────────────────────── */}
        {edges.map((edge, i) => {
          const from = nodeByName.get(edge.from);
          const to = nodeByName.get(edge.to);
          if (!from || !to) return null;
          const isFlowing =
            from.status === "completed" && (to.status === "running" || to.status === "pending");
          return (
            <path
              key={`${edge.from}-${edge.to}-${i}`}
              d={edgePath(from, to)}
              fill="none"
              stroke={isFlowing ? "#3b82f6" : "#9dabbe"}
              strokeWidth={1.5}
              className={cn(isFlowing && "dag-edge-flow")}
              opacity={0.5}
            />
          );
        })}

        {/* ── Nodes ─────────────────────────────────────────────────── */}
        {nodes.map((node) => {
          const colors = STATUS_COLORS[node.status] ?? STATUS_COLORS.draft;
          const Icon = STATUS_ICONS[node.status] ?? Clock;
          const isSelected = selectedStep === node.name;
          const isHovered = hoveredStep === node.name;
          const isRunning = node.status === "running";

          return (
            <g
              key={node.name}
              transform={`translate(${node.x}, ${node.y})`}
              onClick={() => onSelectStep(isSelected ? null : node.name)}
              onMouseEnter={() => setHoveredStep(node.name)}
              onMouseLeave={() => setHoveredStep(null)}
              className="cursor-pointer"
            >
              {/* Node background */}
              <rect
                width={NODE_W}
                height={NODE_H}
                rx={10}
                fill={colors.fill}
                stroke={isSelected ? "#c9a84c" : colors.stroke}
                strokeWidth={isSelected ? 2 : 1}
                className={cn(isRunning && "dag-node-running")}
                style={{
                  filter: isHovered || isSelected
                    ? "drop-shadow(0 2px 8px rgba(15, 27, 45, 0.12))"
                    : "drop-shadow(0 1px 3px rgba(15, 27, 45, 0.06))",
                  transition: "filter 0.2s ease",
                }}
              />
              {/* Status icon */}
              <g transform="translate(10, (NODE_H - 16) / 2)">
                <foreignObject width={16} height={16}>
                  <Icon
                    className={cn("h-4 w-4", isRunning && "animate-spin")}
                    style={{ color: colors.stroke }}
                  />
                </foreignObject>
              </g>
              {/* Step name */}
              <text
                x={34}
                y={20}
                className="font-sans text-xs font-semibold"
                fill={colors.text}
              >
                {node.name.length > 22 ? node.name.slice(0, 22) + "\u2026" : node.name}
              </text>
              {/* Progress bar */}
              {node.status === "running" && (
                <rect
                  x={34}
                  y={NODE_H - 14}
                  width={NODE_W - 44}
                  height={4}
                  rx={2}
                  fill="rgba(255,255,255,0.6)"
                >
                </rect>
              )}
              {node.status === "running" && (
                <rect
                  x={34}
                  y={NODE_H - 14}
                  width={(NODE_W - 44) * ((node.progress ?? 50) / 100)}
                  height={4}
                  rx={2}
                  fill={colors.stroke}
                >
                  <animate
                    attributeName="opacity"
                    values="0.7;1;0.7"
                    dur="1.5s"
                    repeatCount="indefinite"
                  />
                </rect>
              )}
              {/* Container image (truncated) */}
              <text
                x={34}
                y={NODE_H - (node.status === "running" ? 20 : 14)}
                className="font-mono text-[8px]"
                fill={colors.text}
                opacity={0.6}
              >
                {(node.container_image.split("/").pop() ?? node.container_image).slice(0, 24)}
              </text>
              {/* Depends count badge */}
              {node.depends_on.length > 0 && (
                <g transform={`translate(${NODE_W - 22}, 8)`}>
                  <circle r={7} fill="rgba(15,27,45,0.08)" />
                  <text
                    x={0}
                    y={3}
                    textAnchor="middle"
                    className="font-sans text-[8px] font-medium"
                    fill={colors.text}
                    opacity={0.7}
                  >
                    {node.depends_on.length}
                  </text>
                </g>
              )}
            </g>
          );
        })}
      </svg>
    </div>
  );
}