"use client";

import { useEffect, useState } from "react";
import { useToastStore, type ToastVariant } from "@/store/toastStore";
import { cn } from "@/lib/utils";
import {
  CheckCircle2,
  XCircle,
  Info,
  AlertTriangle,
  X,
} from "lucide-react";

// ── Toast container (renders fixed top-right, portal-free) ──────────────

const VARIANT_CONFIG: Record<
  ToastVariant,
  { icon: React.ComponentType<{ className?: string }>; border: string; iconColor: string }
> = {
  success: { icon: CheckCircle2, border: "border-green-400/50", iconColor: "text-green-500" },
  error: { icon: XCircle, border: "border-red-400/50", iconColor: "text-red-500" },
  info: { icon: Info, border: "border-blue-400/50", iconColor: "text-blue-500" },
  warning: { icon: AlertTriangle, border: "border-amber-400/50", iconColor: "text-amber-500" },
};

export function ToastContainer() {
  const { toasts, dismiss } = useToastStore();

  return (
    <div className="pointer-events-none fixed bottom-4 right-4 z-[100] flex flex-col gap-2">
      {toasts.map((t) => {
        const cfg = VARIANT_CONFIG[t.variant];
        const Icon = cfg.icon;
        return (
          <ToastCard
            key={t.id}
            toast={t}
            icon={Icon}
            iconColor={cfg.iconColor}
            borderClass={cfg.border}
            onDismiss={() => dismiss(t.id)}
          />
        );
      })}
    </div>
  );
}

// ── Toast card with enter/exit animation ─────────────────────────────────

function ToastCard({
  toast,
  icon: Icon,
  iconColor,
  borderClass,
  onDismiss,
}: {
  toast: { id: string; title: string; message?: string; variant: string };
  icon: React.ComponentType<{ className?: string }>;
  iconColor: string;
  borderClass: string;
  onDismiss: () => void;
}) {
  const [exiting, setExiting] = useState(false);

  const handleDismiss = () => {
    setExiting(true);
    setTimeout(onDismiss, 280);
  };

  return (
    <div
      className={cn(
        "pointer-events-auto flex max-w-sm items-start gap-3 rounded-xl border glass-heavy px-4 py-3 shadow-lg",
        borderClass,
        exiting ? "toast-exit" : "toast-enter"
      )}
    >
      <Icon className={cn("mt-0.5 h-5 w-5 shrink-0", iconColor)} />
      <div className="flex-1 min-w-0">
        <p className="text-sm font-semibold text-navy">{toast.title}</p>
        {toast.message && (
          <p className="mt-0.5 text-xs text-muted-foreground">{toast.message}</p>
        )}
      </div>
      <button
        onClick={handleDismiss}
        className="shrink-0 text-muted-foreground hover:text-navy transition-colors"
        aria-label="Dismiss"
      >
        <X className="h-4 w-4" />
      </button>
    </div>
  );
}