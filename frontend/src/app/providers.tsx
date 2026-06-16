"use client";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { api, getAuthToken } from "@/lib/api";

export default function Providers({ children }: { children: React.ReactNode }) {
  const [queryClient] = useState(
    () =>
      new QueryClient({
        defaultOptions: {
          queries: {
            staleTime: 30 * 1000, // 30 seconds
            retry: 2,
            refetchOnWindowFocus: true,
          },
        },
      })
  );
  const [authed, setAuthed] = useState(false);

  // ── Auto dev-login: ensure a JWT token exists on mount ──────────────
  useEffect(() => {
    if (getAuthToken()) {
      setAuthed(true);
      return;
    }
    api.devLogin()
      .then(() => setAuthed(true))
      .catch((err) => {
        console.error("[Auth] Dev login failed:", err);
        setAuthed(true); // Still render — API calls will fail gracefully
      });
  }, []);

  if (!authed) {
    return null; // Don't render until auth resolves
  }

  return (
    <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
  );
}