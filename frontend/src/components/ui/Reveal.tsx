"use client";

import { useScrollReveal } from "@/hooks/useScrollReveal";
import { cn } from "@/lib/utils";
import type { ReactNode } from "react";

// ── Reveal ──────────────────────────────────────────────────────────────
// Wraps children in a scroll-triggered fade-up animation.
// Use `delay` (ms) to stagger items.

interface RevealProps {
  children: ReactNode;
  className?: string;
  delay?: number;
  as?: "div" | "section" | "article" | "li";
}

export function Reveal({ children, className, delay = 0, as = "div" }: RevealProps) {
  const { ref } = useScrollReveal<HTMLElement>();

  const Tag = as as React.ElementType;

  return (
    <Tag
      ref={ref as React.RefObject<HTMLElement>}
      className={cn("reveal", className)}
      style={{ transitionDelay: `${delay}ms` }}
    >
      {children}
    </Tag>
  );
}