"use client";

import { useEffect, useState, useCallback } from "react";
import { useWebSocket } from "./useWebSocket";
import { useSessionStore } from "@/store/sessionStore";
import { api } from "@/lib/api";
import type { SessionState } from "@/types/events";

// ── State synchronization hook ───────────────────────────────────────────
// Fetches initial state from REST, subscribes to WebSocket for real-time
// updates, and reconciles missed events on reconnect.

interface UseStateSyncReturn {
  state: SessionState | null;
  isLoading: boolean;
  error: string | null;
  refetch: () => Promise<void>;
}

export function useStateSync(sessionId: string | null): UseStateSyncReturn {
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const store = useSessionStore();
  const { connectionStatus, reconnect } = useWebSocket({ sessionId });

  // ── Fetch initial state on mount or session change ──────────────
  const fetchState = useCallback(async () => {
    if (!sessionId) return;
    setIsLoading(true);
    setError(null);
    try {
      // Fetch session metadata
      await store.fetchSession(sessionId);

      // Fetch projected state (pipelines, runs, metrics, agent_state)
      await store.fetchProjectState(sessionId);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to fetch state");
    } finally {
      setIsLoading(false);
    }
  }, [sessionId]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    fetchState();
  }, [fetchState]);

  // ── On reconnect, reconcile missed events ──────────────────────
  useEffect(() => {
    if (connectionStatus === "connected" && sessionId) {
      const lastSeqId = store.lastSeqId;
      if (lastSeqId > 0) {
        // Reconciliation: fetch missed events
        api
          .getEventsAfter(sessionId, lastSeqId)
          .then((events) => {
            for (const event of events) {
              if (event.seq_id > lastSeqId) {
                // Reconstruct EventEnvelope from backend EventResponse
                const payload = event.payload ?? {};
                const envelope: import("@/types/events").EventEnvelope = {
                  id: event.seq_id ?? event.id,
                  session_id: event.session_id,
                  event: {
                    event_type: event.event_type as import("@/types/events").ServerEventType,
                    ...payload,
                  } as import("@/types/events").ServerEvent,
                  created_at: event.created_at,
                };
                store.applyEvent(envelope);
              }
            }
          })
          .catch((err) => {
            console.error("[useStateSync] Reconciliation failed:", err);
          });
      }
    }
  }, [connectionStatus, sessionId]); // eslint-disable-line react-hooks/exhaustive-deps

  // ── Compose projected state from store ──────────────────────────
  const state: SessionState | null = sessionId
    ? {
        session_id: sessionId,
        pipelines: store.pipelines,
        runs: store.runs,
        metrics: store.metrics,
        agent_state: store.agentState,
        events_count: store.logs.length,
        projected_at: new Date().toISOString(),
      }
    : null;

  return {
    state,
    isLoading: isLoading || store.isLoading,
    error: error ?? store.error,
    refetch: fetchState,
  };
}