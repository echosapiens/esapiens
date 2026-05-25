import { Text, ActionIcon, ScrollArea } from '@mantine/core';
import { IconTrash, IconPlus, IconX } from '@tabler/icons-react';
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
    <>
      {/* Mobile Header */}
      {isMobile && (
        <div style={{
          display: 'flex', alignItems: 'center',
          justifyContent: 'space-between',
          padding: '12px 16px',
          borderBottom: '1px solid var(--e-border)',
        }}>
          <Text style={{
            fontSize: '0.75rem', fontWeight: 600,
            letterSpacing: '0.1em', textTransform: 'uppercase',
            color: 'var(--e-text-secondary)',
          }}>Sessions</Text>
          <ActionIcon variant="subtle" color="gray" onClick={onClose} size="lg">
            <IconX size={20} />
          </ActionIcon>
        </div>
      )}

      {/* New Chat */}
      <div style={{ padding: '12px 12px 8px 12px' }}>
        <div onClick={onNewChat} style={{
          display: 'flex', alignItems: 'center',
          justifyContent: 'center', gap: 8,
          padding: '8px 12px',
          border: '1px dashed var(--e-border)',
          borderRadius: 'var(--e-radius-ld)',
          cursor: 'pointer',
          minHeight: 44,
          transition: 'all 0.15s ease',
        }}>
          <IconPlus size={16} style={{ color: 'var(--e-accent-cyan)' }} />
          <Text style={{ fontSize: '0.65rem', color: 'var(--e-text-secondary)' }}>New session</Text>
        </div>
      </div>

      {/* Session List */}
      <ScrollArea style={{ flex: 1 }} type="auto">
          {sessions.map((session) => (
            <div key={session.id}
              onClick={() => {
                onSelectSession(session.id);
                if (isMobile && onClose) onClose();
              }}
              style={{
                padding: '12px 16px',
                cursor: 'pointer',
                borderLeft: session.id === activeSessionId
                  ? '3px solid var(--e-accent-cyan)'
                  : '3px solid transparent',
                background: session.id === activeSessionId
                  ? 'var(--e-bg-subtle)'
                  : 'transparent',
                minHeight: 44,
              }}>
              <div style={{
                display: 'flex', alignItems: 'center',
                justifyContent: 'space-between',
              }}>
                <Text style={{
                  fontSize: '0.65rem',
                  color: session.id === activeSessionId ? 'var(--e-text-primary)' : 'var(--e-text-secondary)',
                  whiteSpace: 'nowrap',
                  overflow: 'hidden',
                  textOverflow: 'ellipsis',
                  flex: 1,
                }}>
                  {session.title || 'New Session'}
                </Text>
                <div onClick={(e) => { e.stopPropagation(); onDeleteSession(session.id); }}
                     style={{
                      cursor: 'pointer', opacity: 0.4,
                      padding: '4px', minWidth: 32, height: 32,
                      display: 'flex', alignItems: 'center',
                      justifyContent: 'center',
                    }}>
                  <IconTrash size={14} style={{ color: 'var(--e-accent-red)' }} />
                </div>
              </div>
            </div>
          ))}
      </ScrollArea>

      {/* Mobile Footer */}
      {isMobile && (
        <div style={{ padding: '12px 16px', borderTop: '1px solid var(--e-border)', textAlign: 'center' }}>
          <Text style={{
            fontSize: '0.5rem', color: 'var(--e-text-muted)',
            letterSpacing: '0.1em',
          }}>
            E.sapiens v2   by Shabab Khan
          </Text>
        </div>
      )}
    </>
  );
}
