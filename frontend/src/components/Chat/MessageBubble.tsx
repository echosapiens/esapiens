import { memo, useState, useEffect } from 'react';
import { Group, Text, Badge, Tooltip, Collapse, UnstyledButton, Accordion } from '@mantine/core';
import { IconChevronDown, IconChevronUp, IconTerminal2 } from '@tabler/icons-react';
import Markdown from 'react-markdown';
import remarkMath from 'remark-math';
import remarkGfm from 'remark-gfm';
import rehypeKatex from 'rehype-katex';
import type { Message } from '../../lib/api';
import { ToolCallDisplay } from './ToolCallDisplay';
import { VisualizationPanel } from '../Visualizations';
import { ProcessingPipeline } from './ProcessingPipeline';
import { useTypewriter } from '../../hooks/useTypewriter';

interface MessageBubbleProps {
  message: Message;
}

/* ─── Timestamp ─── */
function TimeLabel({ ts }: { ts: number }) {
  const d = new Date(ts);
  const hh = String(d.getHours()).padStart(2, '0');
  const mm = String(d.getMinutes()).padStart(2, '0');
  const ss = String(d.getSeconds()).padStart(2, '0');
  return (
    <Text
      style={{
        fontFamily: "var(--e-font-mono)",
        fontSize: '0.55rem',
        color: 'var(--e-text-dimmed)',
        opacity: 0.5,
        userSelect: 'none',
      }}
    >
      [{hh}:{mm}:{ss}]
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
          fontSize: '0.45rem',
          color: 'var(--e-text-dimmed)',
          opacity: 0.3,
          marginLeft: 6,
          cursor: 'default',
        }}
      >
        [{text.length}]
      </Text>
    </Tooltip>
  );
}

export function MessageBubble({ message }: MessageBubbleProps) {
  const isUser = message.role === 'user';
  const isStreaming = message.isStreaming;
  const [showThoughts, setShowThoughts] = useState(true);

  /* ─── Typewriter effect for streaming assistant content ─── */
  const { displayText, isAnimating, skipToEnd } = useTypewriter(
    message.content,
    15,   // ms per chunk
    !!message.isStreaming && !!message.content,
  );

  useEffect(() => {
    if (!message.isStreaming && isAnimating) {
      skipToEnd();
    }
  }, [message.isStreaming, isAnimating, skipToEnd]);

  /* ─── User Message (terminal input style) ─── */
  if (isUser) {
    return (
      <div
        style={{
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'flex-end',
          marginBottom: 12,
          animation: 'fade-in-up 0.2s ease-out',
        }}
      >
        <div
          style={{
            maxWidth: '80%',
            padding: '6px 14px',
            borderRight: '2px solid var(--e-accent-blue)',
            backgroundColor: 'rgba(37, 99, 235, 0.03)',
          }}
        >
          {/* Header */}
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 2 }}>
            <Text
              style={{
                fontFamily: "var(--e-font-mono)",
                fontSize: '0.6rem',
                fontWeight: 600,
                letterSpacing: '0.12em',
                textTransform: 'uppercase',
                color: 'var(--e-accent-blue)',
              }}
            >
              USER_INPUT
            </Text>
            <TimeLabel ts={message.timestamp} />
            <CharCount text={message.content} />
          </div>
          {/* Content */}
          <div className="markdown-content" style={{ wordBreak: 'break-word' }}>
            <Markdown
              remarkPlugins={[remarkMath, remarkGfm]}
              rehypePlugins={[rehypeKatex]}
            >
              {message.content}
            </Markdown>
          </div>
        </div>
      </div>
    );
  }

  /* ─── Assistant Message (terminal output style) ─── */
  const hasToolCalls = message.tool_calls && message.tool_calls.length > 0;

  return (
    <div
      style={{
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'flex-start',
        marginBottom: 12,
        animation: 'fade-in-up 0.25s ease-out',
      }}
    >
      <div
        onClick={isAnimating ? skipToEnd : undefined}
        style={{
          maxWidth: '85%',
          padding: '8px 14px',
          borderLeft: '2px solid var(--e-accent-blue)',
          cursor: isAnimating ? 'pointer' : 'default',
          position: 'relative',
        }}
        title={isAnimating ? 'Click to show full response' : undefined}
      >
        {/* Header */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 4 }}>
          {/* Streaming pulse dot */}
          {isStreaming && (
            <div
              style={{
                width: 4,
                height: 4,
                borderRadius: '50%',
                backgroundColor: isAnimating ? 'var(--e-accent-blue)' : 'var(--e-accent-green)',
                transition: 'all 0.3s ease',
              }}
            />
          )}
          <Text
            style={{
              fontFamily: "var(--e-font-mono)",
              fontSize: '0.6rem',
              fontWeight: 600,
              letterSpacing: '0.12em',
              textTransform: 'uppercase',
              color: isAnimating ? 'var(--e-accent-blue)' : '#1a3a3c',
              transition: 'color 0.3s ease',
            }}
          >
            {isAnimating ? 'STREAMING' : 'E.SAPIENS'}
          </Text>
          <TimeLabel ts={message.timestamp} />
          <CharCount text={message.content} />
        </div>

        {/* Thoughts / Reasoning logs */}
        {message.thoughts && message.thoughts.length > 0 && (
          <div style={{ marginBottom: 12 }}>
            <UnstyledButton
              onClick={() => setShowThoughts((v) => !v)}
              style={{
                display: 'flex',
                alignItems: 'center',
                gap: 6,
                padding: '4px 0',
                opacity: 0.8,
                color: 'var(--e-text-secondary)',
              }}
            >
              <IconTerminal2 size={12} style={{ color: 'var(--e-accent-blue)' }} />
              <Text
                style={{
                  fontFamily: "var(--e-font-mono)",
                  fontSize: '0.65rem',
                  fontWeight: 600,
                  letterSpacing: '0.05em',
                  textTransform: 'uppercase',
                }}
              >
                Neural Engine Trace
              </Text>
              {showThoughts ? <IconChevronUp size={12} /> : <IconChevronDown size={12} />}
            </UnstyledButton>
            <Collapse in={showThoughts}>
              <div
                style={{
                  marginTop: 4,
                  padding: '8px 12px',
                  backgroundColor: 'var(--e-bg-subtle)',
                  borderRadius: 'var(--e-radius-md)',
                  borderLeft: '1px solid var(--e-border)',
                  display: 'flex',
                  flexDirection: 'column',
                  gap: 4,
                }}
              >
                {message.thoughts.map((log, i) => (
                  <div key={i} style={{ display: 'flex', gap: 8, alignItems: 'flex-start' }}>
                    <Text
                      style={{
                        fontFamily: "var(--e-font-mono)",
                        fontSize: '0.6rem',
                        color: 'var(--e-text-dimmed)',
                        opacity: 0.5,
                        marginTop: 2,
                        flexShrink: 0,
                      }}
                    >
                      {String(i + 1).padStart(2, '0')}
                    </Text>
                    <Text
                      style={{
                        fontFamily: "var(--e-font-mono)",
                        fontSize: '0.7rem',
                        color: 'var(--e-text-secondary)',
                        lineHeight: 1.4,
                      }}
                    >
                      {log}
                    </Text>
                  </div>
                ))}
                {isStreaming && (
                  <div style={{ display: 'flex', gap: 8, alignItems: 'center', opacity: 0.6 }}>
                    <div className="pulse-indicator" style={{ width: 3, height: 3, borderRadius: '50%', backgroundColor: 'var(--e-accent-blue)' }} />
                    <Text style={{ fontFamily: "var(--e-font-mono)", fontSize: '0.65rem', fontStyle: 'italic' }}>allocating next cycle...</Text>
                  </div>
                )}
              </div>
            </Collapse>
          </div>
        )}

        {/* Skills badge */}
        {message.skills && message.skills.length > 0 && (
          <Group gap={4} mb="xs" wrap="wrap">
            {message.skills.map((skill) => (
              <Badge key={skill} size="sm" variant="light" color="electricBlue">
                {skill}
              </Badge>
            ))}
          </Group>
        )}

        {/* Processing pipeline — show tool calls as visual flow */}
        {hasToolCalls && isStreaming && (
          <ProcessingPipeline toolCalls={message.tool_calls} />
        )}

        {/* Content with typewriter effect */}
        {isStreaming && !message.content ? (
          <div
            style={{
              fontFamily: "var(--e-font-mono)",
              fontSize: '0.75rem',
              color: 'var(--e-accent-blue)',
              opacity: 0.6,
            }}
          >
            <div style={{ display: 'flex', gap: 4 }}>
              <span>○</span>
              <span>ANALYZING</span>
            </div>
          </div>
        ) : (
          <div className="markdown-content" style={{ wordBreak: 'break-word' }}>
            <Markdown
              remarkPlugins={[remarkMath, remarkGfm]}
              rehypePlugins={[rehypeKatex]}
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
                  <div style={{ overflowX: 'auto', margin: '12px 0' }}>
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
                  <thead style={{
                    borderBottom: '2px solid var(--e-border)',
                  }}>
                    {children}
                  </thead>
                ),
                th: ({ children }) => (
                  <th style={{
                    padding: '8px 12px',
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
                    padding: '8px 12px',
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
                  <tr style={{
                    transition: 'background-color 0.1s ease',
                  }}>
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
              fontSize: '0.85rem',
              color: 'var(--e-text-secondary)',
              animation: 'blink 1s step-end infinite',
              lineHeight: 1,
            }}
          >
            ▊
          </Text>
        )}

        {/* \"Skip animation\" hint */}
        {isAnimating && message.content.length > 100 && (
          <Text
            style={{
              fontFamily: "var(--e-font-mono)",
              fontSize: '0.45rem',
              color: 'var(--e-text-dimmed)',
              opacity: 0.3,
              marginTop: 2,
            }}
          >
            CLICK TO SKIP
          </Text>
        )}

        {/* Tool calls (collapsed) */}
        {hasToolCalls && !isStreaming && (
          <div style={{ marginTop: 4 }}>
            <Accordion
              variant="contained"
              chevronPosition="right"
              styles={{
                item: {
                  backgroundColor: 'transparent',
                  border: '1px solid var(--e-border)',
                  marginBottom: 2,
                },
                control: {
                  padding: '4px 10px',
                  minHeight: 0,
                },
                panel: {
                  padding: '6px 10px',
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
          <div style={{ marginTop: 8 }}>
            <VisualizationPanel data={message.visualization} />
          </div>
        )}
      </div>
    </div>
  );
}
