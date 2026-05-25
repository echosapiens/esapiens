import { Group, Text, ActionIcon, Tooltip } from '@mantine/core';
import { IconMenu2, IconPlus } from '@tabler/icons-react';
import { useMobile } from '../../hooks/useMobile';

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
    <Group h="100%" w="100%" justify="space-between" align="center" px="md">
      {/* Left: Hamburger icon */}
      {isMobile && (
        <ActionIcon
          variant="subtle"
          color="gray"
          onClick={onToggleNavbar}
          size="lg"
          style={{
            border: '1px solid var(--e-border-subtle)',
            borderRadius: 'var(--e-radius-md)',
          }}
        >
          <IconMenu2 size={20} />
        </ActionIcon>
      )}

      {/* Center: Logo + Name */}
      <Group gap="sm" align="center" justify="center" style={{ flex: 1 }}>
        <img
          src="/logo.png"
          alt="E.sapiens"
          height={28}
          style={{ objectFit: 'contain' }}
        />
        <Text
          fz={20}
          ff="sans-serif"
          style={{ fontWeight: 600, letterSpacing: '-0.03em', color: 'var(--e-text-primary)' }}
        >
          E.sapiens
        </Text>
        {/* Tagline - hidden on mobile */}
        {!isMobile && (
          <Text size="sm" c="dimmed" ff="monospace">
            ai-native bioinformatics agent
          </Text>
        )}
      </Group>

      {/* Right: New Chat Button */}
      <Group gap="md">
        <Tooltip label="New session (i⌋N)" withArrow>
          <ActionIcon
            variant="subtle"
            color="gray"
            onClick={onNewChat}
            size="lg"
            style={{
              border: '1px solid var(--e-border-subtle)',
              borderRadius: 'var(--e-radius-md)',
              transition: 'all 0.15s ease',
            }}
          >
            <IconPlus size={18} />
          </ActionIcon>
        </Tooltip>
      </Group>
    </Group>
  );
}
