"use client";

import { useEffect, useRef, useCallback, useState } from "react";
import { useSessionStore } from "@/store/sessionStore";
import { getAuthToken } from "@/lib/api";
import type { EventEnvelope, ConnectionStatus } from "@/types/events";

// ── WebSocket hook with auto-reconnect and state reconciliation ──────────

interface UseWebSocketOptions {
  sessionId: string | null;
  /** WebSocket URL override (default: ws://localhost:8000/ws/events) */
  url?: string;
  /** Whether to auto-connect on mount (default: true) */
  autoConnect?: boolean;
}

interface UseWebSocketReturn {
  connected: boolean;
  lastEvent: EventEnvelope | null;
  connectionStatus: ConnectionStatus;
  reconnect: () => void;
  disconnect: () => void;
}

const WS_BASE_URL =
  typeof window !== "undefined"
    ? `${window.location.protocol === "https:" ? "wss:" : "ws:"}//${window.location.hostname}:8000`
    : "ws://localhost:8000";

const MAX_BACKOFF_MS = 30_000;
const INITIAL_BACKOFF_MS = 1_000;

export function useWebSocket({
  sessionId,
  url,
  autoConnect = true,
}: UseWebSocketOptions): UseWebSocketReturn {
  const [lastEvent, setLastEvent] = useState<EventEnvelope | null>(null);
  const wsRef = useRef<WebSocket | null>(null);
  const backoffRef = useRef(INITIAL_BACKOFF_MS);
  const reconnectTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const mountedRef = useRef(true);

  const setConnectionStatus = useSessionStore((s) => s.setConnectionStatus);
  const applyEvent = useSessionStore((s) => s.applyEvent);
  const setLastSeqId = useSessionStore((s) => s.setLastSeqId);
  const lastSeqId = useSessionStore((s) => s.lastSeqId);

  const connectionStatus = useSessionStore((s) => s.connectionStatus);

  const clearReconnectTimeout = useCallback(() => {
    if (reconnectTimeoutRef.current !== null) {
      clearTimeout(reconnectTimeoutRef.current);
      reconnectTimeoutRef.current = null;
    }
  }, []);

  const connect = useCallback(() => {
    if (!sessionId || !mountedRef.current) return;

    // Close existing connection
    if (wsRef.current) {
      wsRef.current.close(1000, "Reconnecting");
      wsRef.current = null;
    }

    const token = getAuthToken();
    if (!token) {
      // No token yet — wait for dev-login to complete, then retry
      console.debug("[WebSocket] No auth token yet, deferring connection");
      const retry = setTimeout(() => {
        if (mountedRef.current) connect();
      }, 500);
      return;
    }

    const wsUrl = url ?? `${WS_BASE_URL}/ws/${sessionId}?token=${encodeURIComponent(token)}`;
    setConnectionStatus("connecting");

    const ws = new WebSocket(wsUrl);
    wsRef.current = ws;

    ws.onopen = () => {
      if (!mountedRef.current) return;
      setConnectionStatus("connected");
      backoffRef.current = INITIAL_BACKOFF_MS;

      // Send after_seq_id for state reconciliation
      if (lastSeqId > 0) {
        ws.send(JSON.stringify({ type: "RECONCILE", after_seq_id: lastSeqId }));
      }
    };

    ws.onmessage = (event) => {
      if (!mountedRef.current) return;
      try {
        const data = JSON.parse(event.data);

        // Handle EventEnvelope format from backend
        if (data.event_type && data.payload) {
          // Backend sends flat format: { event_type, payload, seq_id, ... }
          const envelope: EventEnvelope = {
            id: data.seq_id ?? data.id ?? 0,
            session_id: data.session_id ?? sessionId,
            event: data.payload.event_type
              ? data.payload
              : { event_type: data.event_type, ...data.payload },
            created_at: data.created_at ?? new Date().toISOString(),
          };
          applyEvent(envelope);
          setLastSeqId(envelope.id);
          setLastEvent(envelope);
        } else if (data.event) {
          // Already in EventEnvelope format
          const envelope: EventEnvelope = data;
          applyEvent(envelope);
          setLastSeqId(envelope.id);
          setLastEvent(envelope);
        } else if (data.echo) {
          // WS stub echo response — ignore
        }
      } catch (err) {
        console.error("[WebSocket] Failed to parse message:", err);
      }
    };

    ws.onclose = (event) => {
      if (!mountedRef.current) return;

      // 1000 = normal close, 1001 = going away
      if (event.code === 1000 || event.code === 1001) {
        setConnectionStatus("disconnected");
        return;
      }

      // Auto-reconnect with exponential backoff
      setConnectionStatus("reconnecting");
      const delay = backoffRef.current;
      backoffRef.current = Math.min(backoffRef.current * 2, MAX_BACKOFF_MS);

      reconnectTimeoutRef.current = setTimeout(() => {
        if (mountedRef.current) {
          connect();
        }
      }, delay);
    };

    ws.onerror = () => {
      if (!mountedRef.current) return;
      console.error("[WebSocket] Connection error");
    };
  }, [sessionId, url, applyEvent, setConnectionStatus, setLastSeqId, lastSeqId]);

  const disconnect = useCallback(() => {
    clearReconnectTimeout();
    if (wsRef.current) {
      wsRef.current.close(1000, "Manual disconnect");
      wsRef.current = null;
    }
    setConnectionStatus("disconnected");
  }, [clearReconnectTimeout, setConnectionStatus]);

  const reconnect = useCallback(() => {
    disconnect();
    backoffRef.current = INITIAL_BACKOFF_MS;
    connect();
  }, [disconnect, connect]);

  // Auto-connect / reconnect on sessionId change
  useEffect(() => {
    mountedRef.current = true;
    if (autoConnect && sessionId) {
      connect();
    }
    return () => {
      mountedRef.current = false;
      disconnect();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sessionId, autoConnect]);

  return {
    connected: connectionStatus === "connected",
    lastEvent,
    connectionStatus,
    reconnect,
    disconnect,
  };
}