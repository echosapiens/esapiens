import { ActionIcon, Tooltip, useMantineColorScheme } from '@mantine/core';
import { IconSun, IconMoon } from '@tabler/icons-react';

export function ThemeToggle() {
  const { colorScheme, toggleColorScheme } = useMantineColorScheme();
  const isDark = colorScheme === 'dark';

  return (
    <Tooltip label={isDark ? 'Light mode' : 'Dark mode'} withArrow>
      <ActionIcon
        variant="subtle"
        color="gray"
        onClick={toggleColorScheme}
        size="lg"
        aria-label="Toggle color scheme"
        style={{
          border: '1px solid var(--e-border-subtle)',
          borderRadius: 'var(--e-radius-md)',
          transition: 'all 0.15s ease',
        }}
      >
        {isDark ? <IconSun size={18} stroke={1.5} /> : <IconMoon size={18} stroke={1.5} />}
      </ActionIcon>
    </Tooltip>
  );
}
