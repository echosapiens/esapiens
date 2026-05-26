import { useState, useEffect, useCallback, useRef } from 'react';
import { Modal, TextInput, Stack, Text, Group, ScrollArea } from '@mantine/core';

interface Command {
  id: string;
  label: string;
  shortcut?: string;
  category: string;
  action: () => void;
}

interface CommandPaletteProps {
  opened: boolean;
  onClose: () => void;
  onNewChat: () => void;
  onToggleSidebar: () => void;
  onOpenShortcuts: () => void;
  onGenerateReport: () => void;
}

/* ─── Categories ─── */
const CATEGORIES: Record<string, string> = {
  navigation: 'Navigation',
  session: 'Session',
  system: 'System',
};

export function CommandPalette({ opened, onClose, onNewChat, onToggleSidebar, onOpenShortcuts }: CommandPaletteProps) {
  const [query, setQuery] = useState('');
  const inputRef = useRef<HTMLInputElement>(null);

  // Auto-focus input when opened
  useEffect(() => {
    if (opened) {
      setTimeout(() => inputRef.current?.focus(), 50);
    } else {
      setQuery('');
    }
  }, [opened]);

  const commands: Command[] = [
    { id: 'new-chat', label: 'New chat session', shortcut: '⌘N', category: 'session', action: () => { onNewChat(); onClose(); } },
    { id: 'toggle-sidebar', label: 'Toggle sidebar', shortcut: '⌘B', category: 'navigation', action: () => { onToggleSidebar(); onClose(); } },
    { id: 'shortcuts', label: 'Keyboard shortcuts', shortcut: '?', category: 'system', action: () => { onOpenShortcuts(); onClose(); } },
    { id: 'clear-chat', label: 'Clear current chat', shortcut: '', category: 'session', action: () => { onNewChat(); onClose(); } },
    { id: 'generate-report', label: 'Generate PDF report', shortcut: '', category: 'system', action: () => { onGenerateReport(); onClose(); } },
  ];

  const filtered = query
    ? commands.filter((c) => c.label.toLowerCase().includes(query.toLowerCase()))
    : commands;

  // Group by category
  const grouped = filtered.reduce<Record<string, Command[]>>((acc, cmd) => {
    if (!acc[cmd.category]) acc[cmd.category] = [];
    acc[cmd.category].push(cmd);
    return acc;
  }, {});

  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent) => {
      if (e.key === 'Escape') {
        onClose();
      }
    },
    [onClose],
  );

  return (
    <Modal
      opened={opened}
      onClose={onClose}
      size="md"
      padding={0}
      withCloseButton={false}
      centered
      styles={{
        content: {
          backgroundColor: 'var(--e-bg-surface)',
          border: '1px solid var(--e-border-subtle)',
          borderRadius: 'var(--e-radius-lg)',
          overflow: 'hidden',
          boxShadow: 'var(--e-shadow-lg)',
        },
      }}
    >
      {/* Search input */}
      <div
        style={{
          borderBottom: '1px solid var(--e-border-subtle)',
          padding: '12px 16px',
          display: 'flex',
          alignItems: 'center',
          gap: 12,
        }}
      >
        <TextInput
          ref={inputRef as React.RefObject<HTMLInputElement>}
          variant="unstyled"
          placeholder="Search commands..."
          value={query}
          onChange={(e) => setQuery(e.currentTarget.value)}
          onKeyDown={handleKeyDown}
          style={{ flex: 1 }}
          styles={{
            input: {
              fontFamily: 'var(--e-font-sans)',
              fontSize: '0.9375rem',
              color: 'var(--e-text-primary)',
              backgroundColor: 'transparent',
              border: 'none',
              padding: '4px 0',
              '&::placeholder': {
                color: 'var(--e-text-muted)',
              },
            },
          }}
        />
      </div>

      {/* Results */}
      <ScrollArea style={{ maxHeight: 320 }}>
        {Object.entries(grouped).length === 0 ? (
          <Text
            py="xl"
            ta="center"
            style={{
              fontFamily: 'var(--e-font-sans)',
              fontSize: '0.875rem',
              color: 'var(--e-text-tertiary)',
            }}
          >
            No matching commands
          </Text>
        ) : (
          <Stack gap={0} py={4}>
            {Object.entries(grouped).map(([category, cmds]) => (
              <div key={category}>
                <Text
                  px="md"
                  py={8}
                  style={{
                    fontFamily: 'var(--e-font-sans)',
                    fontSize: '0.6875rem',
                    fontWeight: 600,
                    color: 'var(--e-text-tertiary)',
                    borderBottom: '1px solid var(--e-border-subtle)',
                  }}
                >
                  {CATEGORIES[category] || category}
                </Text>
                {cmds.map((cmd) => (
                  <div
                    key={cmd.id}
                    onClick={() => cmd.action()}
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      gap: 12,
                      padding: '10px 16px',
                      cursor: 'pointer',
                      transition: 'all 0.1s ease',
                    }}
                    onMouseEnter={(e) => {
                      e.currentTarget.style.backgroundColor = 'var(--e-bg-subtle)';
                    }}
                    onMouseLeave={(e) => {
                      e.currentTarget.style.backgroundColor = 'transparent';
                    }}
                  >
                    <Text
                      style={{
                        fontFamily: 'var(--e-font-sans)',
                        fontSize: '0.875rem',
                        color: 'var(--e-text-primary)',
                        flex: 1,
                      }}
                    >
                      {cmd.label}
                    </Text>
                    {cmd.shortcut && (
                      <Text
                        style={{
                          fontFamily: 'var(--e-font-mono)',
                          fontSize: '0.6875rem',
                          color: 'var(--e-text-muted)',
                          backgroundColor: 'var(--e-bg-subtle)',
                          padding: '3px 8px',
                          borderRadius: 'var(--e-radius-sm)',
                        }}
                      >
                        {cmd.shortcut}
                      </Text>
                    )}
                  </div>
                ))}
              </div>
            ))}
          </Stack>
        )}
      </ScrollArea>

      {/* Footer hint */}
      <div
        style={{
          borderTop: '1px solid var(--e-border-subtle)',
          padding: '8px 16px',
          display: 'flex',
          gap: 16,
        }}
      >
        <Text style={{ fontFamily: 'var(--e-font-sans)', fontSize: '0.6875rem', color: 'var(--e-text-muted)' }}>
          ↑↓ Navigate
        </Text>
        <Text style={{ fontFamily: 'var(--e-font-sans)', fontSize: '0.6875rem', color: 'var(--e-text-muted)' }}>
          ↵ Select
        </Text>
        <Text style={{ fontFamily: 'var(--e-font-sans)', fontSize: '0.6875rem', color: 'var(--e-text-muted)' }}>
          Esc Close
        </Text>
      </div>
    </Modal>
  );
}
