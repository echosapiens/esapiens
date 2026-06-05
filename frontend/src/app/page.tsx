"use client";

import { useState, useRef, useEffect, useCallback } from "react";
import Link from "next/link";
import ChatMessage from "@/components/ChatMessage";
import ChatInput from "@/components/ChatInput";
import PhaseIndicator from "@/components/PhaseIndicator";
import { streamPipeline, listSessions, createSession, getSession, deleteSession } from "@/lib/api";
import type { Session, SessionMessage } from "@/types";

type PhaseStatus = "pending" | "active" | "completed";

interface Phase {
  id: number;
  name: string;
  status: PhaseStatus;
}

interface Message {
  id: string;
  role: "user" | "system" | "thought" | "log" | "error" | "chat";
  content: string;
  phase?: "research" | "contract" | "execute" | null;
  streaming?: boolean;
  chatId?: string;
}

const INITIAL_PHASES: Phase[] = [
  { id: 1, name: "Research", status: "pending" },
  { id: 2, name: "Contract", status: "pending" },
  { id: 3, name: "Execute", status: "pending" },
];

const WELCOME_MESSAGE: Message = {
  id: "welcome",
  role: "system",
  content:
    "Describe your bioinformatics analysis in natural language. I'll handle the rest.",
};

export default function HomePage() {
  const [messages, setMessages] = useState<Message[]>([WELCOME_MESSAGE]);
  const [phases, setPhases] = useState<Phase[]>(INITIAL_PHASES);
  const [isRunning, setIsRunning] = useState(false);
  const [currentThoughtId, setCurrentThoughtId] = useState<string | null>(null);
  const currentChatIdRef = useRef<string | null>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const abortRef = useRef<AbortController | null>(null);

  // Session sidebar state
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [sessions, setSessions] = useState<Session[]>([]);
  const [activeSessionId, setActiveSessionId] = useState<string | null>(null);
  const [loadingSessions, setLoadingSessions] = useState(false);

  const scrollToBottom = useCallback(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, []);

  // Auto-scroll when messages change
  useEffect(() => {
    scrollToBottom();
  }, [messages, scrollToBottom]);

  // Fetch sessions when sidebar opens
  useEffect(() => {
    if (sidebarOpen && !loadingSessions) {
      fetchSessions();
    }
  }, [sidebarOpen]);

  const fetchSessions = async () => {
    setLoadingSessions(true);
    try {
      const data = await listSessions();
      // Sort by most recent updated_at
      data.sort(
        (a, b) =>
          new Date(b.updated_at).getTime() - new Date(a.updated_at).getTime()
      );
      setSessions(data);
    } catch {
      // Silently fail - sessions may not be available
    } finally {
      setLoadingSessions(false);
    }
  };

  const handleNewChat = async () => {
    try {
      const session = await createSession();
      setActiveSessionId(session.id);
      setMessages([WELCOME_MESSAGE]);
      setPhases(INITIAL_PHASES);
      await fetchSessions();
    } catch {
      // Silently fail
    }
  };

  const handleSelectSession = async (sessionId: string) => {
    try {
      const sessionData = await getSession(sessionId);
      setActiveSessionId(sessionData.id);
      // Convert session messages to our Message format
      const loadedMessages: Message[] = sessionData.messages.map(
        (m: SessionMessage) => ({
          id: m.id,
          role: m.role as Message["role"],
          content: m.content,
        })
      );
      setMessages(
        loadedMessages.length > 0 ? loadedMessages : [WELCOME_MESSAGE]
      );
      setPhases(INITIAL_PHASES);
      setSidebarOpen(false);
    } catch {
      // Silently fail
    }
  };

  const handleDeleteSession = async (
    e: React.MouseEvent,
    sessionId: string
  ) => {
    e.stopPropagation();
    try {
      await deleteSession(sessionId);
      if (activeSessionId === sessionId) {
        setActiveSessionId(null);
        setMessages([WELCOME_MESSAGE]);
      }
      await fetchSessions();
    } catch {
      // Silently fail
    }
  };

  const handleSend = useCallback(
    (prompt: string) => {
      if (isRunning) return;

      setIsRunning(true);
      setPhases(INITIAL_PHASES);

      // Add user message
      const userMsg: Message = {
        id: `user-${Date.now()}`,
        role: "user",
        content: prompt,
      };
      setMessages((prev) => [...prev, userMsg]);

      // Connect to SSE stream
      const controller = streamPipeline(
        prompt,
        (event) => {
          const { type, data } = event;

          switch (type) {
            case "phase": {
              const phaseName = data.phase as string;
              setPhases((prev) =>
                prev.map((p) => {
                  const lower = p.name.toLowerCase();
                  if (lower === phaseName) {
                    return { ...p, status: "active" as PhaseStatus };
                  }
                  // Mark previous phases as completed
                  const phaseOrder = ["research", "contract", "execute"];
                  const currentIdx = phaseOrder.indexOf(phaseName);
                  const thisIdx = phaseOrder.indexOf(lower);
                  if (thisIdx < currentIdx) {
                    return { ...p, status: "completed" as PhaseStatus };
                  }
                  return p;
                })
              );
              break;
            }

            case "thought": {
              const thoughtId = `thought-${Date.now()}`;
              setCurrentThoughtId(thoughtId);
              setMessages((prev) => [
                ...prev,
                {
                  id: thoughtId,
                  role: "thought",
                  content: data.content || data.text || data.message || "",
                  phase: data.phase || null,
                  streaming: true,
                },
              ]);
              break;
            }

            case "token": {
              const token = data.token || "";
              if (!currentChatIdRef.current) {
                const chatId = `chat-${Date.now()}`;
                currentChatIdRef.current = chatId;
                setMessages((prev) => [
                  ...prev,
                  {
                    id: chatId,
                    role: "chat",
                    content: token,
                    streaming: true,
                    chatId,
                  },
                ]);
              } else {
                setMessages((prev) =>
                  prev.map((m) =>
                    m.chatId === currentChatIdRef.current
                      ? { ...m, content: m.content + token }
                      : m
                  )
                );
              }
              break;
            }

            case "log": {
              setMessages((prev) => [
                ...prev,
                {
                  id: `log-${Date.now()}-${Math.random().toString(36).slice(2, 6)}`,
                  role: "log",
                  content: data.content || data.text || data,
                },
              ]);
              break;
            }

            case "result": {
              setMessages((prev) => [
                ...prev,
                {
                  id: `result-${Date.now()}`,
                  role: "system",
                  content:
                    data.content ||
                    data.summary ||
                    data.text ||
                    JSON.stringify(data, null, 2),
                },
              ]);
              break;
            }

            case "error": {
              setMessages((prev) => [
                ...prev,
                {
                  id: `error-${Date.now()}`,
                  role: "error",
                  content: data.content || data.message || data.text || "An error occurred",
                },
              ]);
              break;
            }

            case "complete": {
              // Mark all phases completed
              setPhases((prev) =>
                prev.map((p) => ({ ...p, status: "completed" as PhaseStatus }))
              );
              break;
            }
          }
        },
        (error) => {
          setMessages((prev) => [
            ...prev,
            {
              id: `error-${Date.now()}`,
              role: "error",
              content: error,
            },
          ]);
        },
        () => {
          // On complete: stop streaming on thought and chat messages
          setCurrentThoughtId(null);
          currentChatIdRef.current = null;
          setMessages((prev) =>
            prev.map((m) =>
              m.streaming ? { ...m, streaming: false } : m
            )
          );
          setIsRunning(false);
        }
      );

      abortRef.current = controller;
    },
    [isRunning]
  );

  return (
    <div className="flex h-full relative">
      {/* Session Sidebar */}
      <div
        className={`fixed left-0 top-0 h-full z-30 bg-slate-900 border-r border-slate-800 transition-all duration-300 flex flex-col ${
          sidebarOpen ? "w-64" : "w-0 overflow-hidden"
        }`}
      >
        {/* Sidebar Header */}
        <div className="flex items-center justify-between p-3 border-b border-slate-800 flex-shrink-0">
          <span className="text-sm font-semibold text-slate-300 uppercase tracking-wider">
            Sessions
          </span>
          <button
            onClick={() => setSidebarOpen(false)}
            className="text-slate-500 hover:text-slate-300 transition-colors p-1"
            aria-label="Close sidebar"
          >
            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>

        {/* New Chat Button */}
        <div className="p-3">
          <button
            onClick={handleNewChat}
            className="w-full flex items-center justify-center gap-2 px-3 py-2 text-sm font-medium text-slate-200 bg-slate-800 hover:bg-slate-700 border border-slate-700 rounded-lg transition-colors"
          >
            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
              <path strokeLinecap="round" strokeLinejoin="round" d="M12 4v16m8-8H4" />
            </svg>
            New Chat
          </button>
        </div>

        {/* Session List */}
        <div className="flex-1 overflow-y-auto px-3 pb-3 space-y-1">
          {loadingSessions ? (
            <div className="flex items-center justify-center py-8">
              <div className="w-5 h-5 border-2 border-slate-600 border-t-cyan-400 rounded-full animate-spin" />
            </div>
          ) : sessions.length === 0 ? (
            <p className="text-xs text-slate-500 text-center py-8">
              No sessions yet
            </p>
          ) : (
            sessions.map((session) => (
              <div
                key={session.id}
                onClick={() => handleSelectSession(session.id)}
                className={`group flex items-center justify-between px-3 py-2 rounded-lg cursor-pointer transition-colors text-sm ${
                  activeSessionId === session.id
                    ? "bg-slate-800 text-slate-200"
                    : "text-slate-400 hover:bg-slate-800/60 hover:text-slate-300"
                }`}
              >
                <span className="truncate flex-1">{session.title}</span>
                <button
                  onClick={(e) => handleDeleteSession(e, session.id)}
                  className="opacity-0 group-hover:opacity-100 text-slate-600 hover:text-red-400 transition-all p-1"
                  aria-label="Delete session"
                >
                  <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                    <path strokeLinecap="round" strokeLinejoin="round" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                  </svg>
                </button>
              </div>
            ))
          )}
        </div>
      </div>

      {/* Overlay when sidebar is open on mobile */}
      {sidebarOpen && (
        <div
          className="fixed inset-0 bg-black/50 z-20 md:hidden"
          onClick={() => setSidebarOpen(false)}
        />
      )}

      {/* Main chat area */}
      <div className="flex flex-col h-full flex-1 min-w-0">
        {/* Header */}
        <header className="border-b border-slate-800 bg-slate-900/80 backdrop-blur-sm flex-shrink-0">
          <div className="max-w-5xl mx-auto px-4 h-14 flex items-center justify-between">
            <div className="flex items-center gap-3">
              {/* Sidebar toggle */}
              <button
                onClick={() => setSidebarOpen(!sidebarOpen)}
                className="text-slate-400 hover:text-slate-200 transition-colors p-1"
                aria-label="Toggle sidebar"
              >
                <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M3.75 6.75h16.5M3.75 12h16.5m-16.5 5.25h16.5" />
                </svg>
              </button>
              <Link
                href="/"
                className="text-lg font-bold text-slate-100 tracking-tight"
              >
                <span className="text-cyan-400">E.</span>sapiens
              </Link>
            </div>
            <div className="flex items-center gap-4 text-sm">
              <Link
                href="/dashboard"
                className="text-slate-400 hover:text-slate-200 transition-colors"
              >
                Dashboard
              </Link>
            </div>
          </div>
        </header>

        {/* Phase indicator */}
        <div className="border-b border-slate-800/50 bg-slate-900/40 flex-shrink-0">
          <PhaseIndicator phases={phases} />
        </div>

        {/* Messages area */}
        <div className="flex-1 overflow-y-auto py-4 space-y-1">
          {messages.map((msg) => (
            <ChatMessage
              key={msg.id}
              role={msg.role}
              content={msg.content}
              phase={msg.phase}
              streaming={msg.streaming}
            />
          ))}
          <div ref={messagesEndRef} />
        </div>

        {/* Input bar */}
        <div className="flex-shrink-0">
          <ChatInput onSend={handleSend} disabled={isRunning} />
        </div>
      </div>
    </div>
  );
}
