import { useState } from 'react';
import { useState as useReactState } from 'react';
import {
  Group,
  Text,
  Button,
  ScrollArea,
  Stack,
  ActionIcon,
  Tooltip,
  Modal,
} from '@mantine/core';
import { useDisclosure } from '@mantine/hooks';
import type { Session } from '../../lib/api';

interface SessionSidebarProps {
  sessions: Session[];
  activeSessionId: string | null;
  onSelectSession: (sessionId: string) => void;
  onNewChat: () => void;
  onDeleteSession: (sessionId: string) => void;
  collapsed: boolean;
  onToggleCollapse: () => void;
}

/* Inline SVG icons */
function PlusIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
      <line x1="12" y1="5" x2="12" y2="19" />
      <line x1="5" y1="12" x2="19" y2="12" />
    </svg>
  );
}

function TrashIcon() {
  return (
    <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <polyline points="3 6 5 6 21 6" />
      <path d="M19 6L17.5 20.5C17.3 21.9 16.1 23 14.7 23H9.3C7.9 23 6.7 21.9 6.5 20.5L5 6" />
      <path d="M8 6V4c0-1.1.9-2 2-2h4c1.1 0 2 .9 2 2v2" />
    </svg>
  );
}

function CollapseIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <polyline points="15 18 9 12 15 6" />
    </svg>
  );
}

function ExpandIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <polyline points="9 18 15 12 9 6" />
    </svg>
  );
}

/* ─── Session Log Entry ─── */
function SessionEntry({
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
  const date = new Date(session.updated_at);
  const hh = String(date.getHours()).padStart(2, '0');
  const mm = String(date.getMinutes()).padStart(2, '0');
  const count = session.message_count || 0;

  return (
    <div
      onClick={onSelect}
      style={{
        display: 'flex',
        alignItems: 'center',
        gap: 8,
        padding: '8px 12px',
        cursor: 'pointer',
        borderLeft: isActive ? '2px solid var(--e-info)' : '2px solid transparent',
        backgroundColor: isActive ? 'rgba(59, 130, 246, 0.06)' : 'transparent',
        borderRadius: '0 var(--e-radius-sm) var(--e-radius-sm) 0',
        transition: 'all 0.1s ease',
        userSelect: 'none',
      }}
      onMouseEnter={(e) => {
        if (!isActive) {
          e.currentTarget.style.backgroundColor = 'var(--e-bg-hover)';
        }
      }}
      onMouseLeave={(e) => {
        if (!isActive) {
          e.currentTarget.style.backgroundColor = 'transparent';
        }
      }}
    >
      {/* Timestamp */}
      <Text
        style={{
          fontFamily: 'var(--e-font-mono)',
          fontSize: '0.6875rem',
          color: 'var(--e-text-muted)',
          minWidth: 36,
        }}
      >
        {hh}:{mm}
      </Text>

      {/* Title */}
      <Text
        style={{
          fontFamily: 'var(--e-font-sans)',
          fontSize: '0.8125rem',
          color: isActive ? 'var(--e-info)' : 'var(--e-text-secondary)',
          flex: 1,
          overflow: 'hidden',
          textOverflow: 'ellipsis',
          whiteSpace: 'nowrap',
        }}
      >
        {session.title || 'New conversation'}
      </Text>

      {/* Message count */}
      {count > 0 && (
        <Text
          style={{
            fontFamily: 'var(--e-font-mono)',
            fontSize: '0.6875rem',
            color: 'var(--e-text-muted)',
          }}
        >
          {count}
        </Text>
      )}

      {/* Delete button */}
      <div
        className="session-delete-btn"
        style={{
          opacity: 0,
          transition: 'opacity 0.2s ease',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          width: 16,
          height: 16,
          borderRadius: 4,
        }}
        onMouseEnter={(e) => {
          e.currentTarget.style.opacity = '1';
          e.currentTarget.style.backgroundColor = 'rgba(255, 255, 255, 0.1)';
        }}
        onMouseLeave={(e) => {
          e.currentTarget.style.opacity = '0';
          e.currentTarget.style.backgroundColor = 'transparent';
        }}
        onClick={(e) => { e.stopPropagation(); onDelete(); }}
      >
        <TrashIcon />
      </div>
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
}: SessionSidebarProps) {
  const [deleteConfirm, setDeleteConfirm] = useReactState<string | null>(null);
  const [opened, { open, close }] = useDisclosure(false);

  const handleDelete = (sessionId: string) => {
    setDeleteConfirm(sessionId);
    open();
  };

  const confirmDelete = () => {
    if (deleteConfirm) {
      onDeleteSession(deleteConfirm);
    }
    setDeleteConfirm(null);
    close();
  };

  const cancelDelete = () => {
    setDeleteConfirm(null);
    close();
  };

  // Sort sessions by updated_at descending
  const sorted = [...sessions].sort(
    (a, b) => new Date(b.updated_at).getTime() - new Date(a.updated_at).getTime(),
  );

  // Collapsed state: narrow rail with icons
  if (collapsed) {
    return (
      <Stack
        h="100%"
        gap={0}
        align="center"
        style={{
          width: 52,
          backgroundColor: 'var(--e-bg-surface)',
          transition: 'width 0.2s ease',
        }}
      >
        {/* Collapse toggle (expand) */}
        <div
          style={{
            padding: '12px 0',
            width: '100%',
            display: 'flex',
            justifyContent: 'center',
          }}
        >
          <Tooltip label="Expand sidebar" withArrow position="right">
            <ActionIcon
              variant="subtle"
              color="gray"
              onClick={onToggleCollapse}
              size="sm"
            >
              <ExpandIcon />
            </ActionIcon>
          </Tooltip>
        </div>

        {/* New session icon */}
        <div style={{ padding: '10px 0' }}>
          <Tooltip label="New session" withArrow position="right">
            <ActionIcon
              variant="subtle"
              color="gray"
              onClick={onNewChat}
              size="sm"
            >
              <PlusIcon />
            </ActionIcon>
          </Tooltip>
        </div>

        {/* Session count */}
        <Text
          style={{
            fontFamily: 'var(--e-font-mono)',
            fontSize: '0.625rem',
            color: 'var(--e-text-muted)',
            marginTop: 4,
          }}
        >
          {sessions.length}
        </Text>
      </Stack>
    );
  }

  // Expanded state: full sidebar
  return (
    <>
      <Stack h="100%" gap={0} style={{ width: 260, transition: 'width 0.2s ease' }}>
        {/* Sidebar Header */}
        <div
          style={{
            padding: '10px 12px',
            display: 'flex',
            alignItems: 'center',
            gap: 8,
          }}
        >
          <Text
            style={{
              fontFamily: 'var(--e-font-sans)',
              fontSize: '0.8125rem',
              fontWeight: 600,
              color: 'var(--e-text-secondary)',
              flex: 1,
            }}
          >
            Sessions
          </Text>
          <Text
            style={{
              fontFamily: 'var(--e-font-mono)',
              fontSize: '0.75rem',
              color: 'var(--e-info)',
            }}
          >
            {sessions.length}
          </Text>
          <Tooltip label="Collapse sidebar" withArrow>
            <ActionIcon
              variant="subtle"
              color="gray"
              size="sm"
              onClick={onToggleCollapse}
              style={{ marginLeft: 4 }}
            >
              <CollapseIcon />
            </ActionIcon>
          </Tooltip>
        </div>

        {/* Session list */}
        <ScrollArea style={{ flex: 1 }} px={0}>
          {sorted.length === 0 ? (
            <Stack align="center" py="xl" gap={4}>
              <Text
                style={{
                  fontFamily: 'var(--e-font-sans)',
                  fontSize: '0.875rem',
                  color: 'var(--e-text-tertiary)',
                }}
              >
                No sessions yet
              </Text>
              <Text
                style={{
                  fontFamily: 'var(--e-font-sans)',
                  fontSize: '0.8125rem',
                  color: 'var(--e-text-muted)',
                }}
              >
                Start a new conversation to begin
              </Text>
            </Stack>
          ) : (
            <Stack gap={0} py={4}>
              {sorted.map((session) => (
                <SessionEntry
                  key={session.id}
                  session={session}
                  isActive={session.id === activeSessionId}
                  onSelect={() => onSelectSession(session.id)}
                  onDelete={() => handleDelete(session.id)}
                />
              ))}
            </Stack>
          )}
        </ScrollArea>

        {/* New session button */}
        <div
          style={{
            padding: '8px 10px',
          }}
        >
          <Button
            fullWidth
            variant="light"
            color="gray"
            leftSection={<PlusIcon />}
            onClick={onNewChat}
            size="xs"
          >
            New Session
          </Button>
        </div>
      </Stack>

      {/* Delete confirmation modal */}
      <Modal
        opened={opened}
        onClose={cancelDelete}
        title="Delete Session"
        size="sm"
        centered
        styles={{
          title: { fontFamily: 'var(--e-font-sans)', fontWeight: 600 },
        }}
      >
        <Text
          size="sm"
          mb="lg"
          style={{
            fontFamily: 'var(--e-font-sans)',
            color: 'var(--e-text-secondary)',
            fontSize: '0.875rem',
          }}
        >
          Are you sure you want to delete this conversation? This action cannot be undone.
        </Text>
        <Group justify="flex-end" gap="sm">
          <Button variant="outline" onClick={cancelDelete} size="sm" color="gray">
            Cancel
          </Button>
          <Button color="red" onClick={confirmDelete} size="sm">
            Delete
          </Button>
        </Group>
      </Modal>
    </>
  );
}