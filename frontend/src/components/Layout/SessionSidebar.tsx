import { Text, ActionIcon, ScrollArea, Stack } from '@mantine/core';
import { IconTrash, IconPlus, IconX, IconMessage } from '@tabler/icons-react';
import type { Session } from '../../lib/api';
import { useMobile } from '../../hooks/useMobile';

interface SessionSidebarProps {
  sessions: Session[];
  activeSessionId: string;
  onSelectSession: (id: string) => void;
  onNewChat: () => void;
  onDeleteSession: (id: string) => void;
  collapsed: boolean;
  onToggleCollapse: () => void;
  onClose?: () => void;
}

/* ─── Session item row ─── */
function SessionItem({
  session,
  isActive,
  onSelect,
  onDelete,
}: {
  session: Session;
  isActive: boolean;
  onSelect: () => void;
  onDelete: () => void;
}) {
  return (
    <div
      onClick={onSelect}
      style={{
        display: 'flex',
        alignItems: 'center',
        gap: 8,
        padding: '10px 14px',
        cursor: 'pointer',
        borderLeft: isActive ? '2px solid var(--e-brand)' : '2px solid transparent',
        backgroundColor: isActive ? 'var(--e-bg-subtle)' : 'transparent',
        transition: 'background-color 0.12s ease, border-color 0.12s ease',
        minHeight: 44,
        borderRadius: '0 var(--e-radius-sm) var(--e-radius-sm) 0',
      }}
      onMouseEnter={(e) => {
        if (!isActive) e.currentTarget.style.backgroundColor = 'var(--e-bg-hover)';
      }}
      onMouseLeave={(e) => {
        if (!isActive) e.currentTarget.style.backgroundColor = 'transparent';
      }}
    >
      {/* Session icon */}
      <IconMessage
        size={14}
        stroke={1.5}
        style={{
          color: isActive ? 'var(--e-brand)' : 'var(--e-text-muted)',
          flexShrink: 0,
          transition: 'color 0.12s ease',
        }}
      />

      {/* Title */}
      <Text
        style={{
          fontFamily: 'var(--e-font-sans)',
          fontSize: '0.8125rem',
          fontWeight: isActive ? 500 : 400,
          color: isActive ? 'var(--e-text-primary)' : 'var(--e-text-secondary)',
          whiteSpace: 'nowrap',
          overflow: 'hidden',
          textOverflow: 'ellipsis',
          flex: 1,
          transition: 'color 0.12s ease',
        }}
      >
        {session.title || 'New session'}
      </Text>

      {/* Delete */}
      <ActionIcon
        variant="subtle"
        color="gray"
        size={28}
        onClick={(e) => {
          e.stopPropagation();
          onDelete();
        }}
        style={{
          opacity: 0,
          transition: 'opacity 0.15s ease',
          flexShrink: 0,
        }}
        className="session-delete-btn"
      >
        <IconTrash size={13} stroke={1.5} style={{ color: 'var(--e-accent-red)' }} />
      </ActionIcon>
    </div>
  );
}

export function SessionSidebar({
  sessions,
  activeSessionId,
  onSelectSession,
  onNewChat,
  onDeleteSession,
  collapsed,
  onToggleCollapse,
  onClose,
}: SessionSidebarProps) {
  const isMobile = useMobile();

  return (
    <Stack gap={0} style={{ height: '100%' }}>
      {/* ─── Mobile header ─── */}
      {isMobile && (
        <div style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          padding: '12px 16px',
          borderBottom: '1px solid var(--e-border)',
          flexShrink: 0,
        }}>
          <Text style={{
            fontFamily: 'var(--e-font-mono)',
            fontSize: '0.6875rem',
            fontWeight: 600,
            letterSpacing: '0.1em',
            textTransform: 'uppercase',
            color: 'var(--e-text-tertiary)',
          }}>
            Sessions
          </Text>
          <ActionIcon
            variant="subtle"
            color="gray"
            onClick={onClose}
            size={32}
          >
            <IconX size={16} stroke={1.5} />
          </ActionIcon>
        </div>
      )}

      {/* ─── New session button ─── */}
      <div style={{ padding: '12px 12px 8px' }}>
        <div
          onClick={onNewChat}
          role="button"
          tabIndex={0}
          onKeyDown={(e) => e.key === 'Enter' && onNewChat()}
          style={{
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            gap: 6,
            padding: '10px 14px',
            border: '1px dashed var(--e-border)',
            borderRadius: 'var(--e-radius-md)',
            cursor: 'pointer',
            minHeight: 40,
            transition: 'all 0.15s ease',
            backgroundColor: 'transparent',
          }}
          onMouseEnter={(e) => {
            e.currentTarget.style.borderColor = 'var(--e-brand)';
            e.currentTarget.style.backgroundColor = 'rgba(37, 99, 235, 0.03)';
          }}
          onMouseLeave={(e) => {
            e.currentTarget.style.borderColor = 'var(--e-border)';
            e.currentTarget.style.backgroundColor = 'transparent';
          }}
        >
          <IconPlus size={14} stroke={2} style={{ color: 'var(--e-brand)' }} />
          <Text style={{
            fontFamily: 'var(--e-font-sans)',
            fontSize: '0.75rem',
            fontWeight: 500,
            color: 'var(--e-text-secondary)',
          }}>
            New session
          </Text>
        </div>
      </div>

      {/* ─── Session list ─── */}
      <ScrollArea style={{ flex: 1 }} type="auto">
        <Stack gap={0}>
          {sessions.length === 0 && (
            <div style={{
              padding: '24px 16px',
              textAlign: 'center',
            }}>
              <Text style={{
                fontFamily: 'var(--e-font-sans)',
                fontSize: '0.8125rem',
                color: 'var(--e-text-muted)',
                lineHeight: 1.5,
              }}>
                No sessions yet.
                <br />
                Start a new conversation.
              </Text>
            </div>
          )}
          {sessions.map((session) => (
            <SessionItem
              key={session.id}
              session={session}
              isActive={session.id === activeSessionId}
              onSelect={() => {
                onSelectSession(session.id);
                if (isMobile && onClose) onClose();
              }}
              onDelete={() => onDeleteSession(session.id)}
            />
          ))}
        </Stack>
      </ScrollArea>

      {/* ─── CSS to show delete on row hover ─── */}
      <style>{`
        .session-item-row:hover .session-delete-btn { opacity: 1 !important; }
      `}</style>

      {/* ─── Mobile footer ─── */}
      {isMobile && (
        <div style={{
          padding: '10px 16px',
          borderTop: '1px solid var(--e-border)',
          textAlign: 'center',
          flexShrink: 0,
        }}>
          <Text style={{
            fontFamily: 'var(--e-font-mono)',
            fontSize: '0.5625rem',
            color: 'var(--e-text-muted)',
            letterSpacing: '0.08em',
          }}>
            E.sapiens v2
          </Text>
        </div>
      )}
    </Stack>
  );
}