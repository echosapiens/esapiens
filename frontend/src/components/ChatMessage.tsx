"use client";

import React from "react";
import StreamingText from "./StreamingText";

type ChatMessageRole = "user" | "system" | "thought" | "log" | "error" | "chat";

interface ChatMessageProps {
  role: ChatMessageRole;
  content: string;
  phase?: "research" | "contract" | "execute" | null;
  streaming?: boolean;
}

export default function ChatMessage({
  role,
  content,
  phase,
  streaming = false,
}: ChatMessageProps) {
  const isUser = role === "user";

  const bubbleStyles: Record<ChatMessageRole, string> = {
    user: "bg-cyan-700/80 text-slate-100 rounded-2xl rounded-br-sm",
    system: "bg-slate-700/80 text-slate-200 rounded-2xl rounded-bl-sm",
    thought:
      "bg-slate-600/50 text-slate-200 italic rounded-2xl rounded-bl-sm border-l-2 border-amber-400/50",
    log: "bg-slate-800/90 text-green-300 rounded-lg font-mono text-xs leading-relaxed border border-slate-700/50",
    error:
      "bg-red-800/70 text-red-100 rounded-2xl rounded-bl-sm border border-red-600/30",
    chat:
      "bg-slate-600/60 text-slate-200 rounded-2xl rounded-bl-sm",
  };

  const iconMap: Record<string, React.ReactNode> = {
    thought: (
      <svg className="w-4 h-4 inline-block" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
        <path strokeLinecap="round" strokeLinejoin="round" d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z" />
      </svg>
    ),
    error: (
      <svg className="w-4 h-4 inline-block" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
        <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
      </svg>
    ),
    log: ">",
  };

  return (
    <div
      className={`flex ${isUser ? "justify-end" : "justify-start"} mb-3 px-4`}
    >
      <div
        className={`max-w-[85%] md:max-w-[75%] ${
          role === "log" ? "w-full max-w-full md:max-w-full" : ""
        }`}
      >
        {/* Phase label for thought messages */}
        {phase && role === "thought" && (
          <div className="text-[10px] uppercase tracking-wider text-amber-400/70 mb-1 ml-1 font-semibold">
            {phase}
          </div>
        )}

        <div className={`p-3 ${bubbleStyles[role]}`}>
          {/* Icon for thought/error */}
          {(role === "thought" || role === "error") && (
            <span className="mr-2 text-sm inline-flex items-center">{iconMap[role]}</span>
          )}

          {/* Log prefix */}
          {role === "log" && (
            <span className="text-green-500/70 mr-2 select-none">{">"}</span>
          )}

          {/* Content */}
          {role === "thought" && streaming ? (
            <StreamingText text={content} speed={20} />
          ) : role === "log" ? (
            <pre className="whitespace-pre-wrap break-words font-mono">
              {content}
            </pre>
          ) : (
            <span className="whitespace-pre-wrap break-words">{content}</span>
          )}
        </div>
      </div>
    </div>
  );
}
