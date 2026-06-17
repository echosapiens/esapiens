"use client";

import { useMemo, useState } from "react";
import { cn } from "@/lib/utils";
import { CheckCircle2, XCircle, Loader2, Clock, Play } from "lucide-react";

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

const STATUS_COLORS: Record<string, { fill: string; stroke: string; text: string }> = {
  completed: { fill: "rgba(34,197,94,0.12)", stroke: "#22c55e", text: "#22c55e" },
  running: { fill: "rgba(59,130,246,0.12)", stroke: "#3b82f6", text: "#3b82f6" },
  failed: { fill: "rgba(239,68,68,0.12)", stroke: "#ef4444", text: "#ef4444" },
  pending: { fill: "rgba(245,158,11,0.12)", stroke: "#f59e0b", text: "#f59e0b" },
  submitted: { fill: "rgba(168,85,247,0.12)", stroke: "#a855f7", text: "#a855f7" },
  draft: { fill: "rgba(107,114,128,0.12)", stroke: "#6b7280", text: "#6b7280" },
};

const STATUS_ICONS: Record<string, React.ComponentType<{ className?: string; style?: React.CSSProperties }>> = {
  completed: CheckCircle2, running: Loader2, failed: XCircle, pending: Clock, submitted: Play, draft: Clock,
};

interface PositionedNode extends DagNode { x: number; y: number; col: number; }

function layoutDag(steps: DagNode[], width: number, height: number): { nodes: PositionedNode[]; edges: { from: string; to: string }[]; cols: number } {
  const NODE_W = 180, NODE_H = 56, COL_GAP = 80, ROW_GAP = 28;
  const nodeMap = new Map(steps.map((s) => [s.name, s]));
  const deps = new Map<string, string[]>();
  for (const s of steps) deps.set(s.name, s.depends_on.filter((d) => nodeMap.has(d)));
  const dependents = new Map<string, string[]>();
  steps.forEach((s) => dependents.set(s.name, []));
  deps.forEach((dlist, name) => dlist.forEach((d) => dependents.get(d)?.push(name)));
  const colMap = new Map<string, number>();
  const queue = steps.filter((s) => (deps.get(s.name) ?? []).length === 0).map((s) => s.name);
  queue.forEach((n) => colMap.set(n, 0));
  const sorted: string[] = [];
  const inDegree = new Map(steps.map((s) => [s.name, (deps.get(s.name) ?? []).length]));
  while (queue.length > 0) {
    const n = queue.shift()!;
    sorted.push(n);
    for (const dep of dependents.get(n) ?? []) {
      const newDeg = (inDegree.get(dep) ?? 1) - 1;
      inDegree.set(dep, newDeg);
      if (newDeg === 0) queue.push(dep);
    }
  }
  for (const s of steps) if (!sorted.includes(s.name)) sorted.push(s.name);
  for (const name of sorted) {
    const dlist = deps.get(name) ?? [];
    colMap.set(name, dlist.length === 0 ? 0 : Math.max(...dlist.map((d) => colMap.get(d) ?? 0)) + 1);
  }
  const cols = Math.max(...Array.from(colMap.values()), 0) + 1;
  const colGroups = new Map<number, string[]>();
  for (const [name, col] of colMap) { if (!colGroups.has(col)) colGroups.set(col, []); colGroups.get(col)!.push(name); }
  const positioned: PositionedNode[] = [];
  for (let col = 0; col < cols; col++) {
    (colGroups.get(col) ?? []).forEach((name, idx) => {
      const step = nodeMap.get(name)!;
      positioned.push({ ...step, col, x: col * (NODE_W + COL_GAP) + 24, y: idx * (NODE_H + ROW_GAP) + 24 });
    });
  }
  const edges: { from: string; to: string }[] = [];
  for (const step of steps) for (const dep of step.depends_on) if (nodeMap.has(dep)) edges.push({ from: dep, to: step.name });
  return { nodes: positioned, edges, cols };
}

export function DagGraph({ steps, selectedStep, onSelectStep }: DagGraphProps) {
  const [hoveredStep, setHoveredStep] = useState<string | null>(null);
  const { nodes, edges, cols } = useMemo(() => layoutDag(steps, 0, 0), [steps]);
  const NODE_W = 180, NODE_H = 56, COL_GAP = 80, ROW_GAP = 28, PAD = 24;
  const maxColHeight = useMemo(() => {
    const colHeights = new Map<number, number>();
    nodes.forEach((n) => colHeights.set(n.col, (colHeights.get(n.col) ?? 0) + 1));
    return Math.max(...Array.from(colHeights.values()), 0);
  }, [nodes]);
  const svgWidth = cols * (NODE_W + COL_GAP) + PAD * 2 - COL_GAP;
  const svgHeight = maxColHeight * (NODE_H + ROW_GAP) + PAD * 2 - ROW_GAP;
  const nodeByName = useMemo(() => new Map(nodes.map((n) => [n.name, n])), [nodes]);

  function edgePath(from: PositionedNode, to: PositionedNode): string {
    const x1 = from.x + NODE_W, y1 = from.y + NODE_H / 2, x2 = to.x, y2 = to.y + NODE_H / 2, midX = (x1 + x2) / 2;
    return `M ${x1} ${y1} C ${midX} ${y1}, ${midX} ${y2}, ${x2} ${y2}`;
  }

  if (steps.length === 0) return null;

  return (
    <div className="w-full overflow-auto card p-2">
      <svg width={Math.max(svgWidth, 200)} height={Math.max(svgHeight, 100)} className="min-w-full">
        {edges.map((edge, i) => {
          const from = nodeByName.get(edge.from), to = nodeByName.get(edge.to);
          if (!from || !to) return null;
          const isFlowing = from.status === "completed" && (to.status === "running" || to.status === "pending");
          return <path key={`${edge.from}-${edge.to}-${i}`} d={edgePath(from, to)} fill="none" stroke={isFlowing ? "#3b82f6" : "#4b5563"} strokeWidth={1.5} className={cn(isFlowing && "dag-edge-flow")} opacity={0.5} />;
        })}
        {nodes.map((node) => {
          const colors = STATUS_COLORS[node.status] ?? STATUS_COLORS.draft;
          const Icon = STATUS_ICONS[node.status] ?? Clock;
          const isSelected = selectedStep === node.name;
          const isHovered = hoveredStep === node.name;
          const isRunning = node.status === "running";
          return (
            <g key={node.name} transform={`translate(${node.x}, ${node.y})`} onClick={() => onSelectStep(isSelected ? null : node.name)}
              onMouseEnter={() => setHoveredStep(node.name)} onMouseLeave={() => setHoveredStep(null)} className="cursor-pointer">
              <rect width={NODE_W} height={NODE_H} rx={8} fill={colors.fill} stroke={isSelected ? "#c9a84c" : colors.stroke} strokeWidth={isSelected ? 2 : 1}
                className={cn(isRunning && "dag-node-running")}
                style={{ filter: isHovered || isSelected ? "drop-shadow(0 2px 8px rgba(0,0,0,0.3))" : "drop-shadow(0 1px 2px rgba(0,0,0,0.2))", transition: "filter 0.15s ease" }} />
              <g transform="translate(10, (NODE_H - 16) / 2)">
                <foreignObject width={16} height={16}>
                  <Icon className={cn("h-4 w-4", isRunning && "animate-spin")} style={{ color: colors.stroke }} />
                </foreignObject>
              </g>
              <text x={34} y={20} className="font-sans text-xs font-semibold" fill={colors.text}>
                {node.name.length > 22 ? node.name.slice(0, 22) + "\u2026" : node.name}
              </text>
              {node.status === "running" && <rect x={34} y={NODE_H - 14} width={NODE_W - 44} height={4} rx={2} fill="rgba(255,255,255,0.08)" />}
              {node.status === "running" && (
                <rect x={34} y={NODE_H - 14} width={(NODE_W - 44) * ((node.progress ?? 50) / 100)} height={4} rx={2} fill={colors.stroke}>
                  <animate attributeName="opacity" values="0.7;1;0.7" dur="1.5s" repeatCount="indefinite" />
                </rect>
              )}
              <text x={34} y={NODE_H - (node.status === "running" ? 20 : 14)} className="font-mono text-[8px]" fill={colors.text} opacity={0.5}>
                {(node.container_image.split("/").pop() ?? node.container_image).slice(0, 24)}
              </text>
              {node.depends_on.length > 0 && (
                <g transform={`translate(${NODE_W - 22}, 8)`}>
                  <circle r={7} fill="rgba(0,0,0,0.3)" />
                  <text x={0} y={3} textAnchor="middle" className="font-sans text-[8px] font-medium" fill={colors.text} opacity={0.7}>{node.depends_on.length}</text>
                </g>
              )}
            </g>
          );
        })}
      </svg>
    </div>
  );
}