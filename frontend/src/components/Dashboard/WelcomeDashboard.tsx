import { useState, useEffect } from 'react';
import { Group, Stack, Text, Paper, Center } from '@mantine/core';

interface DashboardProps {
  onNewChat: () => void;
  sessionCount: number;
}

/* ─── Executive Stat Card ─── */
function StatCard({ label, value, accent }: { label: string; value: string; accent: string }) {
  return (
    <Paper
      p="md"
      radius="md"
      style={{
        backgroundColor: 'var(--e-bg-surface)',
        border: '1px solid var(--e-border-subtle)',
        flex: 1,
        minWidth: 120,
        transition: 'all 0.2s ease',
      }}
      onMouseEnter={(e) => {
        e.currentTarget.style.borderColor = accent;
        e.currentTarget.style.boxShadow = 'var(--e-shadow-md)';
      }}
      onMouseLeave={(e) => {
        e.currentTarget.style.borderColor = 'var(--e-border-subtle)';
        e.currentTarget.style.boxShadow = 'none';
      }}
    >
      <Text
        style={{
          fontFamily: 'var(--e-font-sans)',
          fontSize: '0.75rem',
          fontWeight: 500,
          color: 'var(--e-text-tertiary)',
          marginBottom: 6,
          textTransform: 'capitalize',
        }}
      >
        {label}
      </Text>
      <Text
        style={{
          fontFamily: 'var(--e-font-display)',
          fontSize: '1.5rem',
          fontWeight: 700,
          color: accent,
          letterSpacing: '-0.02em',
          lineHeight: 1.1,
        }}
      >
        {value}
      </Text>
    </Paper>
  );
}

/* ─── Quick Action Button ─── */
function QuickAction({
  label,
  shortcut,
  onClick,
  color,
}: {
  label: string;
  shortcut: string;
  onClick: () => void;
  color: string;
}) {
  return (
    <Paper
      p="sm"
      radius="md"
      onClick={onClick}
      style={{
        backgroundColor: 'var(--e-bg-surface)',
        border: '1px solid var(--e-border-subtle)',
        cursor: 'pointer',
        transition: 'all 0.15s ease',
        userSelect: 'none',
      }}
      onMouseEnter={(e) => {
        e.currentTarget.style.borderColor = color;
        e.currentTarget.style.backgroundColor = `${color}06`;
      }}
      onMouseLeave={(e) => {
        e.currentTarget.style.borderColor = 'var(--e-border-subtle)';
        e.currentTarget.style.backgroundColor = 'var(--e-bg-surface)';
      }}
    >
      <Group justify="space-between" align="center">
        <Text
          style={{
            fontFamily: 'var(--e-font-sans)',
            fontSize: '0.875rem',
            color: 'var(--e-text-primary)',
          }}
        >
          {label}
        </Text>
        <Text
          style={{
            fontFamily: 'var(--e-font-mono)',
            fontSize: '0.6875rem',
            color: 'var(--e-text-muted)',
            backgroundColor: 'var(--e-bg-subtle)',
            padding: '3px 8px',
            borderRadius: '4px',
          }}
        >
          {shortcut}
        </Text>
      </Group>
    </Paper>
  );
}

/* ─── Clock Widget ─── */
function ClockWidget() {
  const [time, setTime] = useState(new Date());

  useEffect(() => {
    const timer = setInterval(() => setTime(new Date()), 1000);
    return () => clearInterval(timer);
  }, []);

  const hh = String(time.getHours()).padStart(2, '0');
  const mm = String(time.getMinutes()).padStart(2, '0');

  return (
    <Text
      style={{
        fontFamily: 'var(--e-font-display)',
        fontSize: '3rem',
        fontWeight: 300,
        color: 'var(--e-text-primary)',
        letterSpacing: '-0.02em',
        lineHeight: 1,
      }}
    >
      {hh}:{mm}
    </Text>
  );
}

/* ─── Date Display ─── */
function DateDisplay() {
  const [date] = useState(new Date());

  const options: Intl.DateTimeFormatOptions = {
    weekday: 'long',
    year: 'numeric',
    month: 'long',
    day: 'numeric',
  };

  return (
    <Text
      style={{
        fontFamily: 'var(--e-font-sans)',
        fontSize: '0.875rem',
        color: 'var(--e-text-tertiary)',
        fontWeight: 400,
      }}
    >
      {date.toLocaleDateString('en-US', options)}
    </Text>
  );
}

/* ─── System Metrics Row ─── */
function SystemMetrics() {
  const [metrics, setMetrics] = useState({
    cpu: 23,
    mem: 62,
    latency: 12,
  });

  useEffect(() => {
    const interval = setInterval(() => {
      setMetrics({
        cpu: Math.floor(Math.random() * 40 + 10),
        mem: Math.floor(Math.random() * 20 + 55),
        latency: Math.floor(Math.random() * 60 + 5),
      });
    }, 5000);
    return () => clearInterval(interval);
  }, []);

  return (
    <Group gap="lg">
      {[
        {
          label: 'CPU Load',
          value: `${metrics.cpu}%`,
          color: metrics.cpu > 50 ? 'var(--e-warning)' : 'var(--e-success)',
        },
        {
          label: 'Memory',
          value: `${metrics.mem}%`,
          color: metrics.mem > 75 ? 'var(--e-warning)' : 'var(--e-success)',
        },
        {
          label: 'Latency',
          value: `${metrics.latency}ms`,
          color: metrics.latency > 50 ? 'var(--e-warning)' : 'var(--e-info)',
        },
      ].map((m) => (
        <div key={m.label} style={{ textAlign: 'center' }}>
          <Text
            style={{
              fontFamily: 'var(--e-font-sans)',
              fontSize: '0.6875rem',
              color: 'var(--e-text-tertiary)',
              marginBottom: 2,
            }}
          >
            {m.label}
          </Text>
          <Text
            style={{
              fontFamily: 'var(--e-font-mono)',
              fontSize: '0.875rem',
              fontWeight: 600,
              color: m.color,
            }}
          >
            {m.value}
          </Text>
        </div>
      ))}
    </Group>
  );
}

/* ─── Welcome Dashboard ─── */
export function WelcomeDashboard({ onNewChat, sessionCount }: DashboardProps) {
  return (
    <Center h="100%" px="xl">
      <Stack align="center" gap="xl" style={{ maxWidth: 640, width: '100%' }}>
        {/* Logo & Branding */}
        <Stack align="center" gap={8}>
          <Text
            style={{
              fontFamily: 'var(--e-font-display)',
              fontSize: '2rem',
              fontWeight: 700,
              color: 'var(--e-text-primary)',
              letterSpacing: '-0.03em',
            }}
          >
            E.sapiens
          </Text>
          <Text
            style={{
              fontFamily: 'var(--e-font-sans)',
              fontSize: '0.875rem',
              color: 'var(--e-text-tertiary)',
              fontWeight: 400,
            }}
          >
            Bioinformatics Research Platform
          </Text>
        </Stack>

        {/* Clock & Date */}
        <Stack align="center" gap={4}>
          <ClockWidget />
          <DateDisplay />
        </Stack>

        {/* Stat cards */}
        <Group grow style={{ width: '100%' }} gap="md">
          <StatCard label="Sessions" value={String(sessionCount)} accent="var(--e-info)" />
          <StatCard label="Status" value="Online" accent="var(--e-success)" />
          <StatCard label="Model" value="GLM 5.1" accent="var(--e-brand)" />
        </Group>

        {/* System metrics */}
        <Paper
          p="md"
          radius="md"
          style={{
            width: '100%',
            backgroundColor: 'var(--e-bg-surface)',
            border: '1px solid var(--e-border-subtle)',
          }}
        >
          <Group justify="space-between" align="center">
            <Text
              style={{
                fontFamily: 'var(--e-font-sans)',
                fontSize: '0.8125rem',
                fontWeight: 500,
                color: 'var(--e-text-secondary)',
              }}
            >
              System Performance
            </Text>
            <SystemMetrics />
          </Group>
        </Paper>

        {/* Quick Actions */}
        <Stack gap="sm" style={{ width: '100%' }}>
          <Text
            style={{
              fontFamily: 'var(--e-font-sans)',
              fontSize: '0.75rem',
              fontWeight: 500,
              color: 'var(--e-text-tertiary)',
              marginBottom: 4,
            }}
          >
            Quick Actions
          </Text>
          <QuickAction
            label="Start a new session"
            shortcut="⌘N"
            onClick={onNewChat}
            color="var(--e-info)"
          />
          <QuickAction
            label="View keyboard shortcuts"
            shortcut="?"
            onClick={() => {
              window.dispatchEvent(new CustomEvent('open-shortcuts'));
            }}
            color="var(--e-brand)"
          />
        </Stack>

        {/* Bottom hint */}
        <Text
          style={{
            fontFamily: 'var(--e-font-sans)',
            fontSize: '0.8125rem',
            color: 'var(--e-text-muted)',
            marginTop: 8,
          }}
        >
          Type a query or press{' '}
          <Text component="span" style={{ fontFamily: 'var(--e-font-mono)', fontSize: '0.75rem' }}>
            ⌘K
          </Text>{' '}
          to open commands
        </Text>
      </Stack>
    </Center>
  );
}
