"use client";

import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import rehypeHighlight from "rehype-highlight";
import { cn } from "@/lib/utils";

// ── MarkdownRenderer ─────────────────────────────────────────────────────
// GitHub-flavored markdown with syntax highlighting for chat messages.
// Uses react-markdown + remark-gfm + rehype-highlight (highlight.js).

interface MarkdownRendererProps {
  content: string;
  className?: string;
}

export function MarkdownRenderer({ content, className }: MarkdownRendererProps) {
  return (
    <div
      className={cn(
        "mac-prose",
        className
      )}
    >
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        rehypePlugins={[[rehypeHighlight, { detect: true, ignoreMissing: true }]]}
        components={{
          // ── Code blocks (pre > code) ──────────────────────────────
          pre({ children, ...props }) {
            return (
              <pre
                className="my-2 overflow-x-auto rounded-lg bg-navy-900 p-3 text-xs leading-relaxed"
                {...props}
              >
                {children}
              </pre>
            );
          },
          // ── Inline code ─────────────────────────────────────────────
          code({ className: codeClassName, children, ...props }) {
            // If it has a language class (from rehype-highlight), it's a block
            const isBlock = /language-/.test(codeClassName ?? "");
            if (isBlock) {
              return (
                <code className={codeClassName} {...props}>
                  {children}
                </code>
              );
            }
            return (
              <code
                className="rounded bg-navy-900/8 px-1.5 py-0.5 font-mono text-[0.85em] text-navy"
                {...props}
              >
                {children}
              </code>
            );
          },
          // ── Links ────────────────────────────────────────────────────
          a({ children, ...props }) {
            return (
              <a
                className="text-gold-700 underline decoration-gold/40 underline-offset-2 hover:decoration-gold"
                target="_blank"
                rel="noopener noreferrer"
                {...props}
              >
                {children}
              </a>
            );
          },
          // ── Tables ──────────────────────────────────────────────────
          table({ children }) {
            return (
              <div className="my-2 overflow-x-auto">
                <table className="w-full border-collapse text-xs">
                  {children}
                </table>
              </div>
            );
          },
          th({ children }) {
            return (
              <th className="border border-border bg-cream-200 px-2 py-1 text-left font-semibold text-navy">
                {children}
              </th>
            );
          },
          td({ children }) {
            return (
              <td className="border border-border px-2 py-1 text-navy">
                {children}
              </td>
            );
          },
          // ── Lists ────────────────────────────────────────────────────
          ul({ children }) {
            return <ul className="my-1 list-disc pl-4 space-y-0.5">{children}</ul>;
          },
          ol({ children }) {
            return <ol className="my-1 list-decimal pl-4 space-y-0.5">{children}</ol>;
          },
          // ── Blockquotes ──────────────────────────────────────────────
          blockquote({ children }) {
            return (
              <blockquote className="my-2 border-l-2 border-gold/40 pl-3 text-muted-foreground italic">
                {children}
              </blockquote>
            );
          },
          // ── Paragraphs ───────────────────────────────────────────────
          p({ children }) {
            return <p className="my-1 leading-relaxed">{children}</p>;
          },
          // ── Headings ─────────────────────────────────────────────────
          h1({ children }) {
            return <h1 className="mb-1 mt-2 text-base font-bold text-navy">{children}</h1>;
          },
          h2({ children }) {
            return <h2 className="mb-1 mt-2 text-sm font-bold text-navy">{children}</h2>;
          },
          h3({ children }) {
            return <h3 className="mb-1 mt-1.5 text-sm font-semibold text-navy">{children}</h3>;
          },
          h4({ children }) {
            return <h4 className="mb-0.5 mt-1 text-xs font-semibold text-navy">{children}</h4>;
          },
          // ── Horizontal rule ─────────────────────────────────────────
          hr() {
            return <hr className="my-2 border-border" />;
          },
          // ── Strong / Em ──────────────────────────────────────────────
          strong({ children }) {
            return <strong className="font-semibold text-navy">{children}</strong>;
          },
        }}
      >
        {content}
      </ReactMarkdown>
    </div>
  );
}