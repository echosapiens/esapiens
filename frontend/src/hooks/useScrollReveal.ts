"use client";

import { useEffect, useRef, useState } from "react";

// ── useScrollReveal ──────────────────────────────────────────────────────
// IntersectionObserver-based hook that adds `is-visible` class when the
// element enters the viewport. Returns a ref to attach and a boolean.

export function useScrollReveal<T extends HTMLElement = HTMLDivElement>(
  options?: { threshold?: number; rootMargin?: string; once?: boolean }
): { ref: React.RefObject<T>; isVisible: boolean } {
  const ref = useRef<T>(null);
  const [isVisible, setIsVisible] = useState(false);

  useEffect(() => {
    const el = ref.current;
    if (!el) return;

    // Respect reduced motion
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) {
      setIsVisible(true);
      el.classList.add("is-visible");
      return;
    }

    const observer = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting) {
          setIsVisible(true);
          el.classList.add("is-visible");
          if (options?.once !== false) {
            observer.unobserve(el);
          }
        } else if (options?.once === false) {
          setIsVisible(false);
          el.classList.remove("is-visible");
        }
      },
      {
        threshold: options?.threshold ?? 0.15,
        rootMargin: options?.rootMargin ?? "0px 0px -60px 0px",
      }
    );

    observer.observe(el);
    return () => observer.disconnect();
  }, [options?.threshold, options?.rootMargin, options?.once]);

  return { ref, isVisible };
}