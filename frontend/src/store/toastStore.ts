"use client";

import { create } from "zustand";

// ── Toast types ──────────────────────────────────────────────────────────

export type ToastVariant = "success" | "error" | "info" | "warning";

export interface Toast {
  id: string;
  variant: ToastVariant;
  title: string;
  message?: string;
  duration: number; // ms, 0 = sticky
}

type ToastInput = Omit<Toast, "id" | "duration"> & {
  id?: string;
  duration?: number;
};

interface ToastStore {
  toasts: Toast[];
  add: (toast: ToastInput) => string;
  dismiss: (id: string) => void;
  clear: () => void;
}

// ── Store ────────────────────────────────────────────────────────────────

export const useToastStore = create<ToastStore>((set) => ({
  toasts: [],
  add: (toast) => {
    const id = toast.id ?? `toast-${Date.now()}-${Math.random().toString(36).slice(2, 7)}`;
    const full: Toast = {
      id,
      variant: toast.variant,
      title: toast.title,
      message: toast.message,
      duration: toast.duration ?? 5000,
    };
    set((s) => ({ toasts: [...s.toasts, full] }));
    // Auto-dismiss unless sticky
    if (full.duration > 0) {
      setTimeout(() => {
        set((s) => ({ toasts: s.toasts.filter((t) => t.id !== id) }));
      }, full.duration);
    }
    return id;
  },
  dismiss: (id) => set((s) => ({ toasts: s.toasts.filter((t) => t.id !== id) })),
  clear: () => set({ toasts: [] }),
}));

// ── Convenience helpers (callable from anywhere) ────────────────────────

export const toast = {
  success: (title: string, message?: string, duration = 5000) =>
    useToastStore.getState().add({ variant: "success", title, message, duration }),
  error: (title: string, message?: string, duration = 8000) =>
    useToastStore.getState().add({ variant: "error", title, message, duration }),
  info: (title: string, message?: string, duration = 5000) =>
    useToastStore.getState().add({ variant: "info", title, message, duration }),
  warning: (title: string, message?: string, duration = 6000) =>
    useToastStore.getState().add({ variant: "warning", title, message, duration }),
};