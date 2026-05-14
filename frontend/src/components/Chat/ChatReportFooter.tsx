import { useCallback } from 'react';
import { Group, Text, Paper, Tooltip } from '@mantine/core';

interface ChatReportFooterProps {
  sessionId: string;
  messageCount: number;
}

function PDFIcon() {
  return (
    <svg width={16} height={16} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round">
      <path d="M14 3v4a1 1 0 0 0 1 1h4" />
      <path d="M17 21H7a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h7l5 5v11a2 2 0 0 1-2 2z" />
      <line x1="9" y1="9" x2="10" y2="9" />
      <line x1="9" y1="13" x2="15" y2="13" />
      <line x1="9" y1="17" x2="12" y2="17" />
    </svg>
  );
}

export function ChatReportFooter({ sessionId, messageCount }: ChatReportFooterProps) {
  const hasContent = messageCount > 0;

  const handleDownload = useCallback(() => {
    if (!sessionId || !hasContent) return;
    window.open(`/chat/report/${encodeURIComponent(sessionId)}`, '_blank');
  }, [sessionId, hasContent]);

  if (!hasContent) return null;

  return (
    <div
      style={{
        display: 'flex',
        justifyContent: 'center',
        padding: '8px 0 16px',
        animation: 'fade-in-up 0.3s ease-out',
      }}
    >
      <Paper
        p={0}
        radius={0}
        onClick={handleDownload}
        style={{
          backgroundColor: 'transparent',
          border: '1px solid var(--e-border)',
          cursor: 'pointer',
          transition: 'all 0.15s ease',
          userSelect: 'none',
        }}
        onMouseEnter={(e) => {
          e.currentTarget.style.borderColor = 'var(--e-accent-green)';
          e.currentTarget.style.boxShadow = '0 0 20px rgba(0, 255, 136, 0.12)';
        }}
        onMouseLeave={(e) => {
          e.currentTarget.style.borderColor = 'var(--e-border)';
          e.currentTarget.style.boxShadow = 'none';
        }}
      >
        <Group gap="xs" px="lg" py="sm">
          {/* Decorative green dot */}
          <div
            style={{
              width: 4,
              height: 4,
              borderRadius: '50%',
              backgroundColor: 'var(--e-accent-green)',
              boxShadow: '0 0 8px rgba(0, 255, 136, 0.4)',
              animation: 'breathe 2s ease-in-out infinite',
            }}
          />

          <PDFIcon />

          <div style={{ display: 'flex', flexDirection: 'column', gap: 0 }}>
            <Text
              style={{
                fontFamily: "var(--e-font-mono)",
                fontSize: '0.65rem',
                fontWeight: 600,
                letterSpacing: '0.12em',
                textTransform: 'uppercase',
                color: 'var(--e-accent-green)',
                lineHeight: 1.4,
              }}
            >
              DOWNLOAD PDF REPORT
            </Text>
            <Text
              style={{
                fontFamily: "var(--e-font-mono)",
                fontSize: '0.5rem',
                color: 'var(--e-text-dimmed)',
                lineHeight: 1.3,
              }}
            >
              SESSION {messageCount} MESSAGES
            </Text>
          </div>

          <Text
            style={{
              fontFamily: "var(--e-font-mono)",
              fontSize: '0.6rem',
              color: 'var(--e-accent-green)',
              opacity: 0.6,
            }}
          >
            ↓
          </Text>
        </Group>
      </Paper>
    </div>
  );
}