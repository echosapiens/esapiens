import { useState, useCallback, useRef, useEffect } from "react";
import { MantineProvider } from "@mantine/core";
import { showNotification } from "@mantine/notifications";
import { produce } from "immer";
import { theme } from "./theme";
import {
  AuthProvider,
  useAuth,
} from "./lib/auth";
import {
  type Message,
  type Session,
  streamChat,
  listSessions,
  getSession,
  deleteSession as apiDeleteSession,
  addUserMessage,
  addAssistantMessage,
  updateLastAssistantContent,
  setLastAssistantContent,
  setAssistantSkills,
  addToolCallToAssistant,
  addThoughtToAssistant,
  updateToolCallResult,
  finalizeAssistant,
} from './lib/api';
import { Header } from "./components/Layout/Header";
import { SessionSidebar } from "./components/Layout/SessionSidebar";
import { Chat } from "./components/Chat/Chat";
import { SystemStatusBar } from "./components/Telemetry/SystemStatusBar";
import { CommandPalette } from "./components/Dashboard/CommandPalette";
import { KeyboardShortcuts } from "./components/Dashboard/KeyboardShortcuts";
import { LoginPage } from "./components/Auth/LoginPage";

/* ─── Auth Guard ─── */

function AuthGuard({ children }: { children: React.ReactNode }) {
  const { authenticated, loading } = useAuth();
  const [, forceUpdate] = useState(0);

  useEffect(() => {
    const handler = () => forceUpdate((n) => n + 1);
    window.addEventListener('auth:unauthorized', handler);
    return () => window.removeEventListener('auth:unauthorized', handler);
  }, []);

  if (loading) {
    return (
      <div style={{
        width: '100vw',
        height: '100dvh',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        backgroundColor: 'var(--e-bg-default)',
      }}>
        <div style={{
          fontFamily: 'var(--e-font-sans)',
          fontSize: 'var(--e-type-sm)',
          color: 'var(--e-text-muted)',
        }}>
          Loading...
        </div>
      </div>
    );
  }

  if (!authenticated) {
    return <LoginPage />;
  }

  return <>{children}</>;
}

/* ─── Main App (authenticated) ─── */

function MainApp() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [sessionId, setSessionId] = useState<string>(`session_${Date.now()}`);
  const [sessions, setSessions] = useState<Session[]>([]);
  const [activeBackgroundJobs, setActiveBackgroundJobs] = useState<any[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [isSessionLoading, setIsSessionLoading] = useState(false);
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const [uiVisible, setUiVisible] = useState(true);
  
  const abortRef = useRef<AbortController | null>(null);
  const inactivityTimerRef = useRef<number | null>(null);

  /* ─── Command palette & shortcuts state ─── */
  const [cmdPaletteOpen, setCmdPaletteOpen] = useState(false);
  const [shortcutsOpen, setShortcutsOpen] = useState(false);

  const resetInactivityTimer = useCallback(() => {
    setUiVisible(true);
    if (inactivityTimerRef.current) window.clearTimeout(inactivityTimerRef.current);
    inactivityTimerRef.current = window.setTimeout(() => {
      setUiVisible(false);
    }, 7000);
  }, []);

  useEffect(() => {
    const handleEvents = (e: MouseEvent | KeyboardEvent) => {
      if (e instanceof MouseEvent) {
        // Tapping edge detection: top (y < 20) or left (x < 20)
        if (e.clientY < 20 || e.clientX < 20) {
          setUiVisible(true);
          resetInactivityTimer();
          return;
        }
      }
      resetInactivityTimer();
    };

    window.addEventListener('mousemove', handleEvents as any);
    window.addEventListener('keydown', handleEvents as any);
    window.addEventListener('mousedown', handleEvents as any);
    resetInactivityTimer();

    return () => {
      window.removeEventListener('mousemove', handleEvents as any);
      window.removeEventListener('keydown', handleEvents as any);
      window.removeEventListener('mousedown', handleEvents as any);
      if (inactivityTimerRef.current) window.clearTimeout(inactivityTimerRef.current);
    };
  }, [resetInactivityTimer]);

  const toggleSidebar = useCallback(() => {
    setSidebarCollapsed((c) => !c);
    resetInactivityTimer();
  }, [resetInactivityTimer]);

  /* ─── Global keyboard shortcuts ─── */
  useEffect(() => {
    function handleKeyDown(e: KeyboardEvent) {
      if ((e.metaKey || e.ctrlKey) && e.key === 'k') {
        e.preventDefault();
        setCmdPaletteOpen((prev) => !prev);
        return;
      }
      if ((e.metaKey || e.ctrlKey) && e.key === 'n') {
        e.preventDefault();
        handleNewChat();
        return;
      }
      if ((e.metaKey || e.ctrlKey) && e.key === 'b') {
        e.preventDefault();
        toggleSidebar();
        return;
      }
      if (e.key === '?' && !(e.target instanceof HTMLInputElement || e.target instanceof HTMLTextAreaElement)) {
        e.preventDefault();
        setShortcutsOpen(true);
        return;
      }
      if (e.key === 'Escape') {
        if (cmdPaletteOpen) setCmdPaletteOpen(false);
        if (shortcutsOpen) setShortcutsOpen(false);
      }
    }

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [cmdPaletteOpen, shortcutsOpen, toggleSidebar]);

  useEffect(() => {
    listSessions()
      .then(setSessions)
      .catch(() => {});
  }, []);

  const refreshSessions = useCallback(() => {
    listSessions().then(setSessions).catch(() => {});
  }, []);

  const handleNewChat = useCallback(() => {
    abortRef.current?.abort();
    abortRef.current = null;
    setMessages([]);
    setSessionId(`session_${Date.now()}`);
    setIsLoading(false);
    setActiveBackgroundJobs([]);
  }, []);

  const handleSendMessage = useCallback(
    async (query: string, fileContext?: string | null) => {
      if (!query.trim() || isLoading) return;

      setMessages((prev) =>
        produce(prev, (draft) => {
          addUserMessage(draft, query);
          addAssistantMessage(draft);
        }),
      );
      setIsLoading(true);

      const controller = new AbortController();
      abortRef.current = controller;

      try {
        let finalSessionId = sessionId;

        await streamChat(
          query,
          sessionId,
          {
            onSkillsLoaded: (skills) => {
              setMessages((prev) => produce(prev, (draft) => { setAssistantSkills(draft, skills); }));
            },
            onToolCall: (toolCall) => {
              setMessages((prev) => produce(prev, (draft) => { addToolCallToAssistant(draft, toolCall); }));
            },
            onThought: (thought) => {
              setMessages((prev) => produce(prev, (draft) => { addThoughtToAssistant(draft, thought); }));
            },
            onToolResult: (toolCallId, result, status) => {
              setMessages((prev) => produce(prev, (draft) => { updateToolCallResult(draft, toolCallId, result, status); }));
            },
            onChunk: (chunk, replace) => {
              setMessages((prev) => produce(prev, (draft) => { updateLastAssistantContent(draft, chunk, replace); }));
            },
            onVisualization: (visData) => {
              setMessages((prev) => produce(prev, (draft) => {
                for (let i = draft.length - 1; i >= 0; i--) {
                  if (draft[i].role === 'assistant') {
                    draft[i].visualization = visData;
                    break;
                  }
                }
              }));
            },
            onComputationActive: (jobs) => {
              setActiveBackgroundJobs(jobs);
            },
            onDone: (sid, response) => {
              if (sid) finalSessionId = sid;
              setMessages((prev) => produce(prev, (draft) => {
                finalizeAssistant(draft);
                if (response) setLastAssistantContent(draft, response);
              }));
              setSessionId(finalSessionId);
              setIsLoading(false);
              refreshSessions();
            },
            onError: (error) => {
              showNotification({ title: "Error", message: error, color: "red" });
              setMessages((prev) => produce(prev, (draft) => { finalizeAssistant(draft); }));
              setIsLoading(false);
            },
          },
          controller.signal,
          fileContext,
        );
      } catch (err: unknown) {
        if (err instanceof Error && err.name === "AbortError") {
          setMessages((prev) => produce(prev, (draft) => { finalizeAssistant(draft); }));
        } else {
          showNotification({ title: "Error", message: (err as any).message || "Request failed", color: "red" });
          setMessages((prev) => produce(prev, (draft) => { finalizeAssistant(draft); }));
        }
      } finally {
        setIsLoading(false);
      }
    },
    [sessionId, isLoading, refreshSessions],
  );

  const handleStop = useCallback(() => {
    abortRef.current?.abort();
    abortRef.current = null;
    setIsLoading(false);
  }, []);

  const handleSelectSession = useCallback(
    async (id: string) => {
      if (isLoading || isSessionLoading) return;
      abortRef.current?.abort();
      setIsSessionLoading(true);
      try {
        const data = await getSession(id);
        setSessionId(id);
        setMessages(data.messages);
        setActiveBackgroundJobs([]); // Reset jobs, will be re-populated by backend on next query or fetch logic
      } catch {
        showNotification({ title: "Error", message: "Failed to load session", color: "red" });
      } finally {
        setIsSessionLoading(false);
      }
    },
    [isLoading, isSessionLoading],
  );

  const handleDeleteSession = useCallback(
    async (id: string) => {
      try {
        await apiDeleteSession(id);
        if (sessionId === id) handleNewChat();
        refreshSessions();
      } catch {
        showNotification({ title: "Error", message: "Failed to delete session", color: "red" });
      }
    },
    [sessionId, handleNewChat, refreshSessions],
  );

  const sidebarWidth = sidebarCollapsed ? 0 : 264;
  const actualUiVisible = uiVisible || cmdPaletteOpen || shortcutsOpen || isSessionLoading || isLoading;

  return (
    <>
      <CommandPalette opened={cmdPaletteOpen} onClose={() => setCmdPaletteOpen(false)} onNewChat={handleNewChat} onToggleSidebar={toggleSidebar} onOpenShortcuts={() => setShortcutsOpen(true)} />
      <KeyboardShortcuts opened={shortcutsOpen} onClose={() => setShortcutsOpen(false)} />

      <div style={{
        width: '100vw',
        height: '100dvh',
        backgroundColor: 'var(--e-bg-default)',
        display: 'flex',
        flexDirection: 'column',
        overflow: 'hidden',
      }}>
        {/* Header */}
        <div style={{
          padding: actualUiVisible ? '10px 12px 0 12px' : '0',
          marginTop: actualUiVisible ? 0 : -62,
          flexShrink: 0,
          transition: 'all 0.4s cubic-bezier(0.4, 0, 0.2, 1)',
          opacity: actualUiVisible ? 1 : 0,
        }}>
          <div style={{
            backgroundColor: 'var(--e-bg-surface)',
            borderRadius: 'var(--e-radius-2xl)',
            boxShadow: 'var(--e-shadow-md)',
            overflow: 'hidden',
            height: 52,
            display: 'flex',
            alignItems: 'center',
            padding: '0 16px',
          }}>
            <Header
              navbarOpened={!sidebarCollapsed}
              onToggleNavbar={toggleSidebar}
              onNewChat={handleNewChat}
              messageCount={messages.length}
              sessionCount={sessions.length}
            />
          </div>
        </div>

        {/* Workspace Body */}
        <div style={{
          display: 'flex',
          flex: 1,
          minHeight: 0,
          padding: actualUiVisible ? '10px 12px 12px 12px' : '0',
          gap: actualUiVisible ? 10 : 0,
          transition: 'all 0.4s cubic-bezier(0.4, 0, 0.2, 1)',
        }}>
          {/* Sidebar */}
          <div style={{
            width: actualUiVisible ? sidebarWidth : 0,
            marginLeft: actualUiVisible ? 0 : -(sidebarWidth + 24),
            flexShrink: 0,
            backgroundColor: 'var(--e-bg-surface)',
            borderRadius: 'var(--e-radius-2xl)',
            boxShadow: 'var(--e-shadow-md)',
            overflow: 'hidden',
            transition: 'all 0.4s cubic-bezier(0.4, 0, 0.2, 1)',
            opacity: actualUiVisible ? 1 : 0,
            display: 'flex',
            flexDirection: 'column',
          }}>
            <SessionSidebar
              sessions={sessions}
              activeSessionId={sessionId}
              onSelectSession={handleSelectSession}
              onNewChat={handleNewChat}
              onDeleteSession={handleDeleteSession}
              collapsed={sidebarCollapsed}
              onToggleCollapse={toggleSidebar}
            />
          </div>

          {/* Chat Expansion */}
          <div style={{ flex: 1, minWidth: 0, display: 'flex', flexDirection: 'column', gap: 10 }}>
            <Chat
              messages={messages}
              onSend={handleSendMessage}
              onStop={handleStop}
              isLoading={isLoading || activeBackgroundJobs.length > 0}
              sessionCount={sessions.length}
              onNewChat={handleNewChat}
              sessionId={sessionId}
            />
          </div>
        </div>
      </div>
      <SystemStatusBar />
    </>
  );
}

export default function App() {
  return (
    <MantineProvider theme={theme} defaultColorScheme="light">
      <AuthProvider>
        <AuthGuard>
          <MainApp />
        </AuthGuard>
      </AuthProvider>
    </MantineProvider>
  );
}
