import { Group, Text, ActionIcon, Tooltip } from '@mantine/core';
import { IconMenu2, IconPlus, IconTrash } from '@tabler/icons-react';
import { useMobile } from '../../hooks/useMobile';
import { ThemeToggle } from './ThemeToggle';

interface HeaderProps {
  navbarOpened: boolean;
  onToggleNavbar: () => void;
  onNewChat: () => void;
  messageCount: number;
  sessionCount: number;
}

export function Header({ onToggleNavbar, onNewChat }: HeaderProps) {
  const isMobile = useMobile();

  return (
    <Group h="100%" w="100%" justify="space-between" align="center" px="md" gap="sm">

      {/* Left: Nav toggle (mobile only) */}
      {isMobile && (
        <ActionIcon
          variant="subtle"
          color="gray"
          onClick={onToggleNavbar}
          size={40}
          style={{
            border: '1px solid var(--e-border-subtle)',
            borderRadius: 'var(--e-radius-md)',
            transition: 'border-color 0.15s ease',
          }}
        >
          <IconMenu2 size={18} stroke={1.5} />
        </ActionIcon>
      )}

      {/* Center: Wordmark */}
      <Group gap={6} align="center" style={{ flex: 1, justifyContent: 'center' }}>
        <img
          src="/logo.png"
          alt="E.sapiens"
          height={26}
          style={{ objectFit: 'contain' }}
        />
        <Text
          fz={18}
          ff="var(--e-font-display)"
          fw={700}
          style={{
            letterSpacing: '-0.03em',
            color: 'var(--e-text-primary)',
            fontStyle: 'italic',
          }}
        >
          E<span style={{ color: 'var(--e-text-tertiary)', fontStyle: 'normal' }}>.</span>sapiens
        </Text>
        {!isMobile && (
          <Text
            fz="xs"
            c="dimmed"
            ff="var(--e-font-mono)"
            style={{ letterSpacing: '0.04em', marginLeft: 4 }}
          >
            v2
          </Text>
        )}
      </Group>

      {/* Right: Actions */}
      <Group gap={6}>
        <Tooltip label="New session (⌘N)" withArrow>
          <ActionIcon
            variant="subtle"
            color="gray"
            onClick={onNewChat}
            size={40}
            style={{
              border: '1px solid var(--e-border-subtle)',
              borderRadius: 'var(--e-radius-md)',
              transition: 'all 0.15s ease',
            }}
            onMouseEnter={(e) => {
              e.currentTarget.style.borderColor = 'var(--e-brand)';
              e.currentTarget.style.color = 'var(--e-brand)';
            }}
            onMouseLeave={(e) => {
              e.currentTarget.style.borderColor = 'var(--e-border-subtle)';
              e.currentTarget.style.color = 'var(--e-text-secondary)';
            }}
          >
            <IconPlus size={17} stroke={2} />
          </ActionIcon>
        </Tooltip>
        <ThemeToggle />
      </Group>
    </Group>
  );
}