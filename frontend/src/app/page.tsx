"use client";

import { useState, useRef, useEffect, useCallback } from "react";
import Link from "next/link";
import ChatMessage from "@/components/ChatMessage";
import ChatInput from "@/components/ChatInput";
import PhaseIndicator from "@/components/PhaseIndicator";
import { streamPipeline } from "@/lib/api";

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

  const scrollToBottom = useCallback(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, []);

  // Auto-scroll when messages change
  useEffect(() => {
    scrollToBottom();
  }, [messages, scrollToBottom]);

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
    <div className="flex flex-col h-full">
      {/* Header */}
      <header className="border-b border-slate-800 bg-slate-900/80 backdrop-blur-sm flex-shrink-0">
        <div className="max-w-5xl mx-auto px-4 h-14 flex items-center justify-between">
          <Link
            href="/"
            className="text-lg font-bold text-slate-100 tracking-tight"
          >
            <span className="text-cyan-400">E.</span>sapiens
          </Link>
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
  );
}
