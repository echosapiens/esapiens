import { Group, Text, ActionIcon, Tooltip, Stack, Image } from '@mantine/core';

interface HeaderProps {
  navbarOpened: boolean;
  onToggleNavbar: () => void;
  onNewChat: () => void;
  messageCount: number;
  sessionCount: number;
}

function PlusIcon() {
  return (
    <svg width={18} height={18} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round">
      <line x1={12} y1={5} x2={12} y2={19} />
      <line x1={5} y1={12} x2={19} y2={12} />
    </svg>
  );
}

export function Header({ onNewChat }: HeaderProps) {
  return (
    <Group
      h="100%"
      w="100%"
      justify="space-between"
    >
      {/* Left: Logo */}
      <Group h="100%" gap="sm" align="center">
        <Image
          src="/logo.png"
          alt="E.sapiens"
          h={40}
          w="auto"
          style={{ objectFit: 'contain' }}
        />

        <Stack gap={0}>
          <Text
            style={{
              fontFamily: 'var(--e-font-sans)',
              fontSize: 'var(--e-type-lg)',
              fontWeight: 700,
              color: '#092426',
              letterSpacing: '-0.03em',
              lineHeight: 1,
            }}
          >
            E.sapiens
          </Text>
          <Text
            style={{
              fontFamily: 'var(--e-font-sans)',
              fontSize: 'var(--e-type-xs)',
              fontWeight: 400,
              color: 'var(--e-text-muted)',
              letterSpacing: '0.04em',
              lineHeight: 1.3,
            }}
          >
            Computational Biology Platform
          </Text>
        </Stack>
      </Group>

      {/* Right: New session */}
      <Group gap="sm">
        <Tooltip label="New session (⌘N)" withArrow>
          <ActionIcon
            variant="subtle"
            color="gray"
            onClick={onNewChat}
            size="md"
            style={{
              border: '1px solid var(--e-border-subtle)',
              borderRadius: 'var(--e-radius-md)',
              transition: 'all 0.15s ease',
            }}
            onMouseEnter={(e) => {
              e.currentTarget.style.borderColor = 'var(--e-brand)';
              e.currentTarget.style.backgroundColor = 'var(--e-bg-subtle)';
            }}
            onMouseLeave={(e) => {
              e.currentTarget.style.borderColor = 'var(--e-border-subtle)';
              e.currentTarget.style.backgroundColor = 'transparent';
            }}
          >
            <PlusIcon />
          </ActionIcon>
        </Tooltip>
      </Group>
    </Group>
  );
}