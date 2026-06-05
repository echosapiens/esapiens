"use client";

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

  const iconMap: Record<string, string> = {
    thought: "💡",
    error: "❌",
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
            <span className="mr-2 text-sm">{iconMap[role]}</span>
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
