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
      justify="center"
      style={{ position: 'relative' }}
    >
      {/* Centered Group: Logo + Text + Ghost Logo */}
      <Group h="100%" gap="md" align="center" justify="center">
        <Image
          src="/logo.png"
          alt="E.sapiens"
          h={32}
          w="auto"
          style={{ objectFit: 'contain' }}
        />

        <Stack gap={0} align="center">
          <Text
            style={{
              fontFamily: 'var(--e-font-sans)',
              fontSize: 'var(--e-type-lg)',
              fontWeight: 700,
              color: '#092426',
              letterSpacing: '-0.03em',
              lineHeight: 1,
              fontStyle: 'italic', // User requested italic
            }}
          >
            E.sapiens
          </Text>
          <Text
            style={{
              fontFamily: 'var(--e-font-sans)',
              fontSize: 'var(--e-type-xs)',
              fontWeight: 500,
              color: 'var(--e-text-muted)',
              letterSpacing: '0.14em',
              lineHeight: 1.3,
              textTransform: 'uppercase',
              marginTop: 2,
            }}
          >
            Computational Biology Platform
          </Text>
        </Stack>

        <Image
          src="/logo.png"
          alt="E.sapiens"
          h={32}
          w="auto"
          style={{ objectFit: 'contain', opacity: 0.1, filter: 'grayscale(1)' }}
        />
      </Group>

      {/* New Session Button - Pulled to Right */}
      <div style={{ position: 'absolute', right: 0 }}>
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
          >
            <PlusIcon />
          </ActionIcon>
        </Tooltip>
      </div>
    </Group>
  );
}
