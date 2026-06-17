"use client";

import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import rehypeHighlight from "rehype-highlight";
import { cn } from "@/lib/utils";

interface MarkdownRendererProps { content: string; className?: string; }

export function MarkdownRenderer({ content, className }: MarkdownRendererProps) {
  return (
    <div className={cn("prose-chat", className)}>
      <ReactMarkdown remarkPlugins={[remarkGfm]} rehypePlugins={[[rehypeHighlight, { detect: true, ignoreMissing: true }]]}
        components={{
          pre({ children, ...props }) { return <pre className="my-2 overflow-x-auto rounded-lg p-3 text-xs leading-relaxed" style={{ background: "var(--bg-surface)" }} {...props}>{children}</pre>; },
          code({ className: codeClassName, children, ...props }) {
            const isBlock = /language-/.test(codeClassName ?? "");
            if (isBlock) return <code className={codeClassName} {...props}>{children}</code>;
            return <code className="rounded px-1.5 py-0.5 font-mono text-[0.85em]" style={{ background: "rgba(255,255,255,0.06)", color: "var(--accent-gold)" }} {...props}>{children}</code>;
          },
          a({ children, ...props }) { return <a className="underline underline-offset-2" style={{ color: "var(--accent-gold)" }} target="_blank" rel="noopener noreferrer" {...props}>{children}</a>; },
          table({ children }) { return <div className="my-2 overflow-x-auto"><table className="w-full border-collapse text-xs">{children}</table></div>; },
          th({ children }) { return <th className="border px-2 py-1 text-left font-semibold" style={{ borderColor: "var(--border-default)", color: "var(--text-primary)" }}>{children}</th>; },
          td({ children }) { return <td className="border px-2 py-1" style={{ borderColor: "var(--border-default)", color: "var(--text-secondary)" }}>{children}</td>; },
          ul({ children }) { return <ul className="my-1 list-disc pl-4 space-y-0.5">{children}</ul>; },
          ol({ children }) { return <ol className="my-1 list-decimal pl-4 space-y-0.5">{children}</ol>; },
          blockquote({ children }) { return <blockquote className="my-2 border-l-2 pl-3 italic" style={{ borderColor: "var(--accent-gold)", color: "var(--text-muted)" }}>{children}</blockquote>; },
          p({ children }) { return <p className="my-1 leading-relaxed">{children}</p>; },
          h1({ children }) { return <h1 className="mb-1 mt-2 text-base font-bold" style={{ color: "var(--text-primary)" }}>{children}</h1>; },
          h2({ children }) { return <h2 className="mb-1 mt-2 text-sm font-bold" style={{ color: "var(--text-primary)" }}>{children}</h2>; },
          h3({ children }) { return <h3 className="mb-1 mt-1.5 text-sm font-semibold" style={{ color: "var(--text-primary)" }}>{children}</h3>; },
          h4({ children }) { return <h4 className="mb-0.5 mt-1 text-xs font-semibold" style={{ color: "var(--text-primary)" }}>{children}</h4>; },
          hr() { return <hr className="my-2" style={{ borderColor: "var(--border-default)" }} />; },
          strong({ children }) { return <strong className="font-semibold" style={{ color: "var(--text-primary)" }}>{children}</strong>; },
        }}
      >
        {content}
      </ReactMarkdown>
    </div>
  );
}