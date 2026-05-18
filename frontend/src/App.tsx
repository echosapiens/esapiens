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

  // Listen for auth:unauthorized events from api.ts (401 responses)
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
  const [isLoading, setIsLoading] = useState(false);
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const abortRef = useRef<AbortController | null>(null);

  /* ─── Command palette & shortcuts state ─── */
  const [cmdPaletteOpen, setCmdPaletteOpen] = useState(false);
  const [shortcutsOpen, setShortcutsOpen] = useState(false);

  const toggleSidebar = useCallback(() => setSidebarCollapsed((c) => !c), []);

  /* ─── Global keyboard shortcuts ─── */
  useEffect(() => {
    function handleKeyDown(e: KeyboardEvent) {
      // Cmd+K — command palette
      if ((e.metaKey || e.ctrlKey) && e.key === 'k') {
        e.preventDefault();
        setCmdPaletteOpen((prev) => !prev);
        return;
      }
      // Cmd+N — new chat
      if ((e.metaKey || e.ctrlKey) && e.key === 'n') {
        e.preventDefault();
        handleNewChat();
        return;
      }
      // Cmd+B — toggle sidebar
      if ((e.metaKey || e.ctrlKey) && e.key === 'b') {
        e.preventDefault();
        toggleSidebar();
        return;
      }
      // ? — shortcuts (only when not typing in an input)
      if (e.key === '?' && !(e.target instanceof HTMLInputElement || e.target instanceof HTMLTextAreaElement)) {
        e.preventDefault();
        setShortcutsOpen(true);
        return;
      }
      // Escape — close modals
      if (e.key === 'Escape') {
        if (cmdPaletteOpen) setCmdPaletteOpen(false);
        if (shortcutsOpen) setShortcutsOpen(false);
      }
    }

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [cmdPaletteOpen, shortcutsOpen, toggleSidebar]);

  /* ─── Listen for custom event from WelcomeDashboard ─── */
  useEffect(() => {
    function handler() { setShortcutsOpen(true); }
    window.addEventListener('open-shortcuts', handler);
    return () => window.removeEventListener('open-shortcuts', handler);
  }, []);

  // Load sessions on mount
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
  }, []);

  const handleSendMessage = useCallback(
    async (query: string, fileContext?: string | null) => {
      if (!query.trim() || isLoading) return;

      // Add user message to state
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
              setMessages((prev) =>
                produce(prev, (draft) => {
                  setAssistantSkills(draft, skills);
                }),
              );
            },
            onToolCall: (toolCall) => {
              setMessages((prev) =>
                produce(prev, (draft) => {
                  addToolCallToAssistant(draft, toolCall);
                }),
              );
            },
            onToolResult: (toolCallId, result, status) => {
              setMessages((prev) =>
                produce(prev, (draft) => {
                  updateToolCallResult(draft, toolCallId, result, status);
                }),
              );
            },
            onChunk: (chunk, replace) => {
              setMessages((prev) =>
                produce(prev, (draft) => {
                  updateLastAssistantContent(draft, chunk, replace);
                }),
              );
            },
            onVisualization: (visData) => {
              setMessages((prev) =>
                produce(prev, (draft) => {
                  for (let i = draft.length - 1; i >= 0; i--) {
                    if (draft[i].role === 'assistant') {
                      draft[i].visualization = visData;
                      break;
                    }
                  }
                }),
              );
            },
            onDone: (sid, response) => {
              if (sid) finalSessionId = sid;
              setMessages((prev) =>
                produce(prev, (draft) => {
                  finalizeAssistant(draft);
                  // Fallback: if chunks didn't deliver content, set it from the done event
                  if (response) {
                    setLastAssistantContent(draft, response);
                  }
                }),
              );
              setSessionId(finalSessionId);
              setIsLoading(false);
              refreshSessions();
            },
            onError: (error) => {
              showNotification({
                title: "Error",
                message: error,
                color: "red",
              });
              setMessages((prev) =>
                produce(prev, (draft) => {
                  finalizeAssistant(draft);
                }),
              );
              setIsLoading(false);
            },
          },
          controller.signal,
          fileContext,
        );
      } catch (err: unknown) {
        if (err instanceof Error && err.name === "AbortError") {
          setMessages((prev) =>
            produce(prev, (draft) => {
              finalizeAssistant(draft);
            }),
          );
        } else {
          const msg = err instanceof Error ? err.message : "Request failed";
          showNotification({
            title: "Error",
            message: msg,
            color: "red",
          });
          setMessages((prev) =>
            produce(prev, (draft) => {
              finalizeAssistant(draft);
            }),
          );
        }
      } finally {
        // Safety net: always clear loading state, even if stream ends without done/error
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
      if (isLoading) return;
      abortRef.current?.abort();
      setIsLoading(true);
      try {
        const data = await getSession(id);
        setSessionId(id);
        setMessages(data.messages);
      } catch {
        showNotification({
          title: "Error",
          message: "Failed to load session",
          color: "red",
        });
      } finally {
        setIsLoading(false);
      }
    },
    [isLoading],
  );

  const handleDeleteSession = useCallback(
    async (id: string) => {
      try {
        await apiDeleteSession(id);
        if (sessionId === id) {
          handleNewChat();
        }
        refreshSessions();
      } catch {
        showNotification({
          title: "Error",
          message: "Failed to delete session",
          color: "red",
        });
      }
    },
    [sessionId, handleNewChat, refreshSessions],
  );

  const sidebarWidth = sidebarCollapsed ? 56 : 264;

  return (
    <>
      <CommandPalette
        opened={cmdPaletteOpen}
        onClose={() => setCmdPaletteOpen(false)}
        onNewChat={handleNewChat}
        onToggleSidebar={toggleSidebar}
        onOpenShortcuts={() => setShortcutsOpen(true)}
      />
      <KeyboardShortcuts
        opened={shortcutsOpen}
        onClose={() => setShortcutsOpen(false)}
      />

      {/* Full-viewport canvas */}
      <div style={{
        width: '100vw',
        height: '100dvh',
        backgroundColor: 'var(--e-bg-default)',
        display: 'flex',
        flexDirection: 'column',
        overflow: 'hidden',
      }}>
        {/* Row 1: Floating header bar */}
        <div style={{
          padding: '10px 12px 0 12px',
          flexShrink: 0,
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

        {/* Row 2: Sidebar + Main content */}
        <div style={{
          display: 'flex',
          flex: 1,
          minHeight: 0,
          padding: '10px 12px 12px 12px',
          gap: 10,
        }}>
          {/* Floating sidebar card */}
          <div style={{
            width: sidebarWidth,
            flexShrink: 0,
            backgroundColor: 'var(--e-bg-surface)',
            borderRadius: 'var(--e-radius-2xl)',
            boxShadow: 'var(--e-shadow-md)',
            overflow: 'hidden',
            transition: 'width 0.2s ease',
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

          {/* Main chat area */}
          <div style={{
            flex: 1,
            minWidth: 0,
            display: 'flex',
            flexDirection: 'column',
            gap: 10,
          }}>
            <Chat
              messages={messages}
              onSend={handleSendMessage}
              onStop={handleStop}
              isLoading={isLoading}
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

/* ─── App Root ─── */

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