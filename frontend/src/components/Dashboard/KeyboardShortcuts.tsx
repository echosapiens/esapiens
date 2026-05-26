import { Modal, Stack, Text, Group, Badge } from '@mantine/core';

interface KeyboardShortcutsProps {
  opened: boolean;
  onClose: () => void;
}

interface ShortcutEntry {
  keys: string[];
  label: string;
}

const SHORTCUTS: ShortcutEntry[] = [
  { keys: ['⌘K'], label: 'Command palette' },
  { keys: ['⌘N'], label: 'New chat session' },
  { keys: ['⌘B'], label: 'Toggle sidebar' },
  { keys: ['⌘J'], label: 'Job monitor' },
  { keys: ['?'], label: 'Keyboard shortcuts' },
  { keys: ['⌘', '↑'], label: 'Scroll to top' },
  { keys: ['⌘', '↓'], label: 'Scroll to bottom' },
  { keys: ['Esc'], label: 'Stop generation / Close modal' },
];

export function KeyboardShortcuts({ opened, onClose }: KeyboardShortcutsProps) {
  return (
    <Modal
      opened={opened}
      onClose={onClose}
      title={
        <Text style={{ fontFamily: "var(--e-font-sans)", fontSize: '0.875rem', fontWeight: 600 }}>
          Keyboard Shortcuts
        </Text>
      }
      size="md"
      radius="md"
    >
      <Stack gap="sm">
        {SHORTCUTS.map((shortcut, idx) => (
          <Group key={idx} justify="space-between" align="center" py={4} style={{ borderBottom: '1px solid #eeeeee' }}>
            <Text style={{ fontFamily: "var(--e-font-sans)", fontSize: '0.875rem' }}>
              {shortcut.label}
            </Text>
            <Group gap={4}>
              {shortcut.keys.map((key, kidx) => (
                <Badge
                  key={kidx}
                  style={{
                    fontFamily: "var(--e-font-mono)",
                    fontSize: '0.75rem',
                    fontWeight: 600,
                    letterSpacing: '0.05em',
                    padding: '4px 8px',
                    backgroundColor: '#f5f5f5',
                    color: '#1a1a1a',
                    border: '1px solid #eeeeee',
                  }}
                >
                  {key}
                </Badge>
              ))}
            </Group>
          </Group>
        ))}
      </Stack>
    </Modal>
  );
}
