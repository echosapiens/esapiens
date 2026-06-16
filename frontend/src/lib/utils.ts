// ── Utility: cn ──────────────────────────────────────────────────────────
// Merges Tailwind classes with conflict resolution (tailwind-merge + clsx)

import { type ClassValue, clsx } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

// ── Utility: formatDate ──────────────────────────────────────────────────

import { formatDistanceToNow, format, isToday, isYesterday } from "date-fns";

export function formatRelativeDate(date: string | Date): string {
  const d = typeof date === "string" ? new Date(date) : date;
  if (isToday(d)) return formatDistanceToNow(d, { addSuffix: true });
  if (isYesterday(d)) return "Yesterday";
  return format(d, "MMM d, yyyy");
}

export function formatTimestamp(date: string | Date): string {
  const d = typeof date === "string" ? new Date(date) : date;
  return format(d, "yyyy-MM-dd HH:mm:ss");
}

// ── Utility: formatCurrency ──────────────────────────────────────────────

export function formatCurrency(
  amount: number | string,
  currency: string = "USD"
): string {
  const num = typeof amount === "string" ? parseFloat(amount) : amount;
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency,
    minimumFractionDigits: 2,
  }).format(num);
}

// ── Utility: statusColorClass ───────────────────────────────────────────

export function statusColorClass(status: string): string {
  const map: Record<string, string> = {
    draft: "status-draft",
    submitted: "status-submitted",
    pending: "status-pending",
    running: "status-running",
    completed: "status-completed",
    failed: "status-failed",
    active: "bg-green-50 text-green-700",
    archived: "bg-gray-50 text-gray-600",
    exhausted: "bg-red-50 text-red-700",
    expired: "bg-orange-50 text-orange-700",
  };
  return map[status] ?? "bg-gray-50 text-gray-600";
}

// ── Utility: truncate ───────────────────────────────────────────────────

export function truncate(str: string, length: number): string {
  if (str.length <= length) return str;
  return str.slice(0, length) + "…";
}

// ── Utility: generateId ─────────────────────────────────────────────────

export function generateId(): string {
  return Math.random().toString(36).substring(2, 11);
}