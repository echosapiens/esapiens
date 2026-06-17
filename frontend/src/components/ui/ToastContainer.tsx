"use client";

import { useState } from "react";
import { useToastStore, type ToastVariant } from "@/store/toastStore";
import { cn } from "@/lib/utils";
import { CheckCircle2, XCircle, Info, AlertTriangle, X } from "lucide-react";

const VARIANT_CONFIG: Record<ToastVariant, { icon: React.ComponentType<{ className?: string }>; variant: string }> = {
  success: { icon: CheckCircle2, variant: "success" },
  error: { icon: XCircle, variant: "error" },
  info: { icon: Info, variant: "info" },
  warning: { icon: AlertTriangle, variant: "warning" },
};

const TOAST_COLORS: Record<string, { border: string; icon: string }> = {
  success: { border: "border-accent-green/30", icon: "text-accent-green" },
  error: { border: "border-accent-red/30", icon: "text-accent-red" },
  info: { border: "border-accent-blue/30", icon: "text-accent-blue" },
  warning: { border: "border-accent-orange/30", icon: "text-accent-orange" },
};

export function ToastContainer() {
  const { toasts, dismiss } = useToastStore();
  return (
    <div className="pointer-events-none fixed bottom-4 right-4 z-[100] flex flex-col gap-2">
      {toasts.map((t) => {
        const cfg = VARIANT_CONFIG[t.variant];
        const Icon = cfg.icon;
        const colors = TOAST_COLORS[cfg.variant] ?? TOAST_COLORS.info;
        return <ToastCard key={t.id} toast={t} icon={Icon} borderClass={colors.border} iconColor={colors.icon} onDismiss={() => dismiss(t.id)} />;
      })}
    </div>
  );
}

function ToastCard({ toast, icon: Icon, borderClass, iconColor, onDismiss }: {
  toast: { id: string; title: string; message?: string; variant: string };
  icon: React.ComponentType<{ className?: string }>;
  borderClass: string; iconColor: string; onDismiss: () => void;
}) {
  const [exiting, setExiting] = useState(false);
  const handleDismiss = () => { setExiting(true); setTimeout(onDismiss, 180); };
  return (
    <div className={cn("pointer-events-auto flex max-w-sm items-start gap-3 rounded-xl px-4 py-3 shadow-lg border", "bg-surface-raised backdrop-blur-2xl", borderClass, exiting ? "toast-exit" : "toast-enter")}
      style={{ background: "var(--bg-raised)" }}>
      <Icon className={cn("mt-0.5 h-5 w-5 shrink-0", iconColor)} />
      <div className="flex-1 min-w-0">
        <p className="text-sm font-semibold" style={{ color: "var(--text-primary)" }}>{toast.title}</p>
        {toast.message && <p className="mt-0.5 text-xs" style={{ color: "var(--text-muted)" }}>{toast.message}</p>}
      </div>
      <button onClick={handleDismiss} className="shrink-0 transition-colors" style={{ color: "var(--text-muted)" }} aria-label="Dismiss">
        <X className="h-4 w-4" />
      </button>
    </div>
  );
}