import { memo, useState, useEffect } from 'react';
import { Group, Text, Badge, Tooltip, UnstyledButton, Accordion } from '@mantine/core';
import { IconChevronDown, IconChevronUp, IconTerminal2 } from '@tabler/icons-react';
import Markdown from 'react-markdown';
import remarkMath from 'remark-math';
import remarkGfm from 'remark-gfm';
import rehypeKatex from 'rehype-katex';
import rehypeRaw from 'rehype-raw';
import rehypeHighlight from 'rehype-highlight';
import type { Message } from '../../lib/api';
import { ToolCallDisplay } from './ToolCallDisplay';
import { VisualizationPanel } from '../Visualizations';
import { ProcessingPipeline } from './ProcessingPipeline';
import { useTypewriter } from '../../hooks/useTypewriter';

/* ─── Timestamp ─── */
function TimeLabel({ ts }: { ts: number }) {
  const d = new Date(ts);
  const hh = String(d.getHours()).padStart(2, '0');
  const mm = String(d.getMinutes()).padStart(2, '0');
  return (
    <Text
      style={{
        fontFamily: "var(--e-font-mono)",
        fontSize: '0.625rem',
        color: 'var(--e-text-muted)',
        letterSpacing: '0.04em',
        userSelect: 'none',
      }}
    >
      {hh}:{mm}
    </Text>
  );
}

/* ─── Content Length Badge ─── */
function CharCount({ text }: { text?: string | null }) {
  if (!text || text.length < 100) return null;
  return (
    <Tooltip label={`${text.length} characters`} withArrow>
      <Text
        component="span"
        style={{
          fontFamily: "var(--e-font-mono)",
          fontSize: '0.5625rem',
          color: 'var(--e-text-muted)',
          letterSpacing: '0.04em',
          marginLeft: 4,
          cursor: 'default',
        }}
      >
        {text.length}
      </Text>
    </Tooltip>
  );
}

/* ─── Role Label ─── */
function RoleLabel({ role, accent }: { role: 'user' | 'assistant'; accent: string }) {
  const label = role === 'user' ? 'INPUT' : 'E.SAPIENS';
  return (
    <Text
      style={{
        fontFamily: "var(--e-font-mono)",
        fontSize: '0.5625rem',
        fontWeight: 600,
        letterSpacing: '0.1em',
        textTransform: 'uppercase',
        color: accent,
      }}
    >
      {label}
    </Text>
  );
}

export const MessageBubble = memo(function MessageBubble({ message }: MessageBubbleProps) {
  const isUser = message.role === 'user';
  const isStreaming = message.isStreaming;
  const hasThoughts = message.thoughts && message.thoughts.length > 0;

  // Auto-show thoughts during streaming, auto-collapse when done
  const [showThoughts, setShowThoughts] = useState(false);
  const [thoughtsCollapsed, setThoughtsCollapsed] = useState(false);

  // While streaming: keep thoughts expanded
  useEffect(() => {
    if (isStreaming && hasThoughts) {
      setShowThoughts(true);
      setThoughtsCollapsed(false);
    }
  }, [isStreaming, hasThoughts]);

  // When streaming ends and we have thoughts: collapse them after a brief delay
  useEffect(() => {
    if (!isStreaming && hasThoughts && showThoughts) {
      const timer = setTimeout(() => {
        setThoughtsCollapsed(true);
        // Wait for collapse animation to finish, then fully hide
      }, 600);
      return () => clearTimeout(timer);
    }
  }, [isStreaming, hasThoughts, showThoughts]);

  /* ─── Typewriter effect for streaming assistant content ─── */
  const { displayText, isAnimating, skipToEnd } = useTypewriter(
    message.content,
    18,
    !!message.isStreaming && !!message.content,
  );

  useEffect(() => {
    if (!message.isStreaming && isAnimating) {
      skipToEnd();
    }
  }, [message.isStreaming, isAnimating, skipToEnd]);

  /* ─── User Message ─── */
  if (isUser) {
    return (
      <div
        style={{
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'flex-end',
          marginBottom: 16,
          animation: 'fade-in-up 0.2s ease-out',
        }}
      >
        <div
          style={{
            maxWidth: '80%',
            padding: '8px 16px',
            borderRight: '2px solid var(--e-accent-blue)',
            backgroundColor: 'rgba(37, 99, 235, 0.04)',
            borderRadius: 'var(--e-radius-md)',
          }}
        >
          {/* Header row */}
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 4 }}>
            <RoleLabel role="user" accent="var(--e-accent-blue)" />
            <TimeLabel ts={message.timestamp} />
            <CharCount text={message.content} />
          </div>
          {/* Content */}
          <div className="markdown-content" style={{ wordBreak: 'break-word' }}>
            <Markdown
              remarkPlugins={[remarkMath, remarkGfm]}
              rehypePlugins={[rehypeKatex, rehypeRaw, rehypeHighlight]}
            >
              {message.content}
            </Markdown>
          </div>
        </div>
      </div>
    );
  }

  /* ─── Assistant Message ─── */
  const hasToolCalls = message.tool_calls && message.tool_calls.length > 0;

  return (
    <div
      style={{
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'flex-start',
        marginBottom: 16,
        animation: 'fade-in-up 0.25s ease-out',
      }}
    >
      <div
        onClick={isAnimating ? skipToEnd : undefined}
        style={{
          maxWidth: '88%',
          padding: '8px 16px 12px',
          borderLeft: `2px solid ${isAnimating ? 'var(--e-accent-blue)' : 'var(--e-border)'}`,
          cursor: isAnimating ? 'pointer' : 'default',
          position: 'relative',
          backgroundColor: 'var(--e-bg-surface)',
          borderRadius: '0 var(--e-radius-md) var(--e-radius-md) 0',
          transition: 'border-color 0.3s ease',
        }}
        title={isAnimating ? 'Click to reveal full response' : undefined}
      >
        {/* Header row */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 6 }}>
          <RoleLabel
            role="assistant"
            accent={isAnimating ? 'var(--e-accent-blue)' : 'var(--e-text-secondary)'}
          />
          <TimeLabel ts={message.timestamp} />
          <CharCount text={message.content} />
          {/* Streaming indicator */}
          {isStreaming && (
            <div
              style={{
                width: 4,
                height: 4,
                borderRadius: '50%',
                backgroundColor: isAnimating ? 'var(--e-accent-blue)' : 'var(--e-success)',
                marginLeft: 2,
                transition: 'background-color 0.4s ease',
              }}
            />
          )}
        </div>

        {/* Thoughts / Neural Engine Trace */}
        {hasThoughts && (
          <div style={{
            maxHeight: thoughtsCollapsed ? 0 : 600,
            overflow: 'hidden',
            transition: isStreaming ? 'none' : 'max-height 0.5s cubic-bezier(0.4, 0, 0.2, 1), opacity 0.4s ease, margin-bottom 0.4s ease',
            opacity: thoughtsCollapsed ? 0 : 1,
            marginBottom: thoughtsCollapsed ? 0 : 8,
          }}>
            {/* Thought stream header — always visible when expanded */}
            <div style={{
              display: 'flex',
              alignItems: 'center',
              gap: 6,
              marginBottom: 4,
            }}>
              <div style={{
                width: 5,
                height: 5,
                borderRadius: '50%',
                backgroundColor: isStreaming ? 'var(--e-accent-blue)' : 'var(--e-success)',
                animation: isStreaming ? 'pulse-dot 1.2s ease-in-out infinite' : 'none',
                transition: 'background-color 0.3s ease',
              }} />
              <Text style={{
                fontFamily: 'var(--e-font-mono)',
                fontSize: '0.5625rem',
                fontWeight: 600,
                letterSpacing: '0.08em',
                textTransform: 'uppercase',
                color: isStreaming ? 'var(--e-accent-blue)' : 'var(--e-success)',
              }}>
                {isStreaming ? 'Neural Trace — Streaming' : 'Neural Trace — Complete'}
              </Text>
              <Text style={{
                fontFamily: 'var(--e-font-mono)',
                fontSize: '0.5rem',
                color: 'var(--e-text-muted)',
                letterSpacing: '0.04em',
              }}>
                ({message.thoughts!.length})
              </Text>
              {/* Collapse button for completed thoughts */}
              {!isStreaming && (
                <UnstyledButton
                  onClick={() => setThoughtsCollapsed(true)}
                  style={{
                    marginLeft: 'auto',
                    display: 'inline-flex',
                    alignItems: 'center',
                    gap: 3,
                    padding: '1px 4px',
                    color: 'var(--e-text-muted)',
                    fontFamily: 'var(--e-font-mono)',
                    fontSize: '0.5rem',
                    letterSpacing: '0.06em',
                    textTransform: 'uppercase',
                    transition: 'color 0.15s ease',
                  }}
                  onMouseEnter={(e) => (e.currentTarget.style.color = 'var(--e-accent-blue)')}
                  onMouseLeave={(e) => (e.currentTarget.style.color = 'var(--e-text-muted)')}
                >
                  Collapse
                  <IconChevronUp size={9} stroke={1.5} />
                </UnstyledButton>
              )}
            </div>

            {/* Thought entries */}
            <div style={{
              padding: '8px 12px',
              backgroundColor: 'var(--e-bg-subtle)',
              borderRadius: 'var(--e-radius-sm)',
              border: `1px solid ${isStreaming ? 'var(--e-accent-blue)' : 'var(--e-border-subtle)'}`,
              transition: 'border-color 0.3s ease',
              display: 'flex',
              flexDirection: 'column',
              gap: 3,
            }}>
              {message.thoughts!.map((log, i) => {
                const isLatest = isStreaming && i === message.thoughts!.length - 1;
                return (
                  <div
                    key={i}
                    style={{
                      display: 'flex',
                      gap: 8,
                      alignItems: 'flex-start',
                      animation: isLatest ? 'fade-in-up 0.25s ease-out' : 'none',
                    }}
                  >
                    <Text
                      style={{
                        fontFamily: "var(--e-font-mono)",
                        fontSize: '0.5625rem',
                        color: isLatest ? 'var(--e-accent-blue)' : 'var(--e-text-muted)',
                        marginTop: 2,
                        flexShrink: 0,
                        letterSpacing: '0.04em',
                        transition: 'color 0.3s ease',
                      }}
                    >
                      {String(i + 1).padStart(2, '0')}
                    </Text>
                    <Text
                      style={{
                        fontFamily: "var(--e-font-mono)",
                        fontSize: '0.6875rem',
                        color: isLatest ? 'var(--e-text-primary)' : 'var(--e-text-secondary)',
                        lineHeight: 1.5,
                        transition: 'color 0.3s ease',
                      }}
                    >
                      {log}
                    </Text>
                  </div>
                );
              })}
              {isStreaming && (
                <div style={{ display: 'flex', gap: 8, alignItems: 'center', opacity: 0.5 }}>
                  <div style={{
                    width: 3, height: 3, borderRadius: '50%',
                    backgroundColor: 'var(--e-accent-blue)',
                    animation: 'pulse-dot 1.2s ease-in-out infinite'
                  }} />
                  <Text style={{
                    fontFamily: "var(--e-font-mono)",
                    fontSize: '0.625rem',
                    color: 'var(--e-text-muted)',
                    fontStyle: 'italic',
                  }}>
                    allocating...
                  </Text>
                </div>
              )}
            </div>
          </div>
        )}

        {/* Post-collapse: subtle expandable label for completed thoughts */}
        {hasThoughts && thoughtsCollapsed && !isStreaming && (
          <UnstyledButton
            onClick={() => {
              setThoughtsCollapsed(false);
              setShowThoughts(true);
            }}
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: 5,
              padding: '2px 0',
              marginBottom: 8,
              color: 'var(--e-text-tertiary)',
              fontFamily: 'var(--e-font-mono)',
              fontSize: '0.5625rem',
              fontWeight: 600,
              letterSpacing: '0.08em',
              textTransform: 'uppercase',
              transition: 'color 0.15s ease',
            }}
            onMouseEnter={(e) => (e.currentTarget.style.color = 'var(--e-accent-blue)')}
            onMouseLeave={(e) => (e.currentTarget.style.color = 'var(--e-text-tertiary)')}
          >
            <IconTerminal2 size={11} stroke={1.5} />
            Neural Trace ({message.thoughts!.length})
            <IconChevronDown size={10} stroke={1.5} />
          </UnstyledButton>
        )}

        {/* Skills badge */}
        {message.skills && message.skills.length > 0 && (
          <Group gap={4} mb="xs" wrap="wrap">
            {message.skills.map((skill) => (
              <Badge
                key={skill}
                size="xs"
                variant="light"
                color="blue"
                styles={{
                  root: {
                    fontFamily: 'var(--e-font-mono)',
                    fontSize: '0.5625rem',
                    fontWeight: 600,
                    letterSpacing: '0.06em',
                    textTransform: 'uppercase',
                    padding: '2px 6px',
                    height: 'auto',
                  },
                }}
              >
                {skill}
              </Badge>
            ))}
          </Group>
        )}

        {/* Processing pipeline */}
        {hasToolCalls && isStreaming && (
          <ProcessingPipeline toolCalls={message.tool_calls} />
        )}

        {/* Content */}
        {isStreaming && !message.content ? (
          <Text
            style={{
              fontFamily: "var(--e-font-mono)",
              fontSize: '0.6875rem',
              color: 'var(--e-accent-blue)',
              opacity: 0.5,
              letterSpacing: '0.06em',
            }}
          >
            ANALYZING
          </Text>
        ) : (
          <div className="markdown-content" style={{ wordBreak: 'break-word' }}>
            <Markdown
              remarkPlugins={[remarkMath, remarkGfm]}
              rehypePlugins={[rehypeKatex, rehypeRaw, rehypeHighlight]}
              components={{
                img: ({ src, alt }) => (
                  <img
                    src={src}
                    alt={alt || ''}
                    style={{
                      maxWidth: '100%',
                      height: 'auto',
                      border: '1px solid var(--e-border)',
                      borderRadius: 2,
                      display: 'block',
                      margin: '8px 0',
                    }}
                  />
                ),
                table: ({ children }) => (
                  <div style={{ overflowX: 'auto', margin: '10px 0' }}>
                    <table style={{
                      width: '100%',
                      borderCollapse: 'collapse',
                      fontFamily: 'var(--e-font-sans)',
                      fontSize: 'var(--e-type-sm)',
                    }}>
                      {children}
                    </table>
                  </div>
                ),
                thead: ({ children }) => (
                  <thead style={{ borderBottom: '2px solid var(--e-border)' }}>
                    {children}
                  </thead>
                ),
                th: ({ children }) => (
                  <th style={{
                    padding: '7px 12px',
                    textAlign: 'left',
                    fontFamily: 'var(--e-font-sans)',
                    fontSize: 'var(--e-type-xs)',
                    fontWeight: 600,
                    color: 'var(--e-text-secondary)',
                    backgroundColor: 'var(--e-bg-subtle)',
                    borderBottom: '2px solid var(--e-border)',
                    whiteSpace: 'nowrap',
                  }}>
                    {children}
                  </th>
                ),
                td: ({ children }) => (
                  <td style={{
                    padding: '7px 12px',
                    fontFamily: 'var(--e-font-sans)',
                    fontSize: 'var(--e-type-sm)',
                    color: 'var(--e-text-primary)',
                    borderBottom: '1px solid var(--e-border-subtle)',
                    verticalAlign: 'top',
                  }}>
                    {children}
                  </td>
                ),
                tr: ({ children }) => (
                  <tr style={{ transition: 'background-color 0.1s ease' }}>
                    {children}
                  </tr>
                ),
              }}
            >
              {isAnimating ? displayText : message.content}
            </Markdown>
          </div>
        )}

        {/* Streaming cursor */}
        {isAnimating && (
          <Text
            component="span"
            style={{
              fontFamily: "var(--e-font-mono)",
              fontSize: '0.8125rem',
              color: 'var(--e-text-secondary)',
              animation: 'blink 1s step-end infinite',
              lineHeight: 1,
            }}
          >
            ▊
          </Text>
        )}

        {/* Skip hint */}
        {isAnimating && message.content.length > 120 && (
          <Text
            style={{
              fontFamily: "var(--e-font-mono)",
              fontSize: '0.5rem',
              color: 'var(--e-text-muted)',
              opacity: 0.4,
              marginTop: 3,
              letterSpacing: '0.06em',
            }}
          >
            CLICK TO SKIP
          </Text>
        )}

        {/* Tool calls — collapsed after streaming completes */}
        {hasToolCalls && !isStreaming && (
          <div style={{ marginTop: 8 }}>
            <Accordion
              variant="light"
              chevronPosition="right"
              styles={{
                item: {
                  backgroundColor: 'transparent',
                  border: '1px solid var(--e-border-subtle)',
                  marginBottom: 2,
                },
                control: {
                  padding: '5px 10px',
                  minHeight: 0,
                },
                panel: {
                  padding: '5px 10px',
                },
                chevron: {
                  width: 10,
                  height: 12,
                },
              }}
            >
              {message.tool_calls!.map((tc) => (
                <ToolCallDisplay key={tc.id} toolCall={tc} />
              ))}
            </Accordion>
          </div>
        )}

        {/* Visualization */}
        {message.visualization && !message.isStreaming && (
          <div style={{ marginTop: 10 }}>
            <VisualizationPanel data={message.visualization} />
          </div>
        )}
      </div>
    </div>
  );
});

interface MessageBubbleProps {
  message: Message;
}