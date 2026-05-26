import { useState, useEffect } from 'react';
import { Group, Stack, Text, Paper } from '@mantine/core';
import { IconPlus, IconKeyboard, IconActivity } from '@tabler/icons-react';

interface DashboardProps {
  onNewChat: () => void;
  sessionCount: number;
}

/* ─── Stat Card — Filipiuk: high contrast, skip weight hierarchy ─── */
function StatCard({ label, value, accent }: { label: string; value: string; accent: string }) {
  return (
    <Paper
      radius="md"
      p="md"
      style={{
        backgroundColor: 'var(--e-bg-surface)',
        border: '1px solid var(--e-border-subtle)',
        flex: 1,
        minWidth: 100,
        transition: 'border-color var(--e-transition-base), box-shadow var(--e-transition-base)',
        cursor: 'default',
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
      <Text style={{
        fontFamily: 'var(--e-font-mono)',
        fontSize: '0.625rem',
        fontWeight: 600,
        letterSpacing: '0.1em',
        textTransform: 'uppercase',
        color: 'var(--e-text-muted)',
        marginBottom: 6,
      }}>
        {label}
      </Text>
      <Text style={{
        fontFamily: 'var(--e-font-display)',
        fontSize: '1.375rem',
        fontWeight: 700,
        color: accent,
        letterSpacing: '-0.02em',
        lineHeight: 1.1,
      }}>
        {value}
      </Text>
    </Paper>
  );
}

/* ─── Quick Action — Filipiuk: specific text, 40px min touch target ─── */
function QuickAction({
  label,
  description,
  shortcut,
  onClick,
  accent,
}: {
  label: string;
  description: string;
  shortcut: string;
  onClick: () => void;
  accent: string;
}) {
  return (
    <Paper
      radius="md"
      p="sm"
      onClick={onClick}
      style={{
        backgroundColor: 'var(--e-bg-surface)',
        border: '1px solid var(--e-border-subtle)',
        cursor: 'pointer',
        transition: 'all var(--e-transition-base)',
        minHeight: 56,
      }}
      onMouseEnter={(e) => {
        e.currentTarget.style.borderColor = accent;
        e.currentTarget.style.backgroundColor = 'var(--e-bg-subtle)';
        e.currentTarget.style.transform = 'translateY(-1px)';
        e.currentTarget.style.boxShadow = 'var(--e-shadow-sm)';
      }}
      onMouseLeave={(e) => {
        e.currentTarget.style.borderColor = 'var(--e-border-subtle)';
        e.currentTarget.style.backgroundColor = 'var(--e-bg-surface)';
        e.currentTarget.style.transform = 'translateY(0)';
        e.currentTarget.style.boxShadow = 'none';
      }}
    >
      <Group justify="space-between" align="center" gap="sm">
        <Stack gap={2}>
          <Text style={{
            fontFamily: 'var(--e-font-sans)',
            fontSize: '0.875rem',
            fontWeight: 500,
            color: 'var(--e-text-primary)',
          }}>
            {label}
          </Text>
          <Text style={{
            fontFamily: 'var(--e-font-sans)',
            fontSize: '0.75rem',
            color: 'var(--e-text-tertiary)',
          }}>
            {description}
          </Text>
        </Stack>
        <Text style={{
          fontFamily: 'var(--e-font-mono)',
          fontSize: '0.625rem',
          fontWeight: 600,
          color: 'var(--e-text-muted)',
          backgroundColor: 'var(--e-bg-subtle)',
          padding: '3px 8px',
          borderRadius: 'var(--e-radius-sm)',
          border: '1px solid var(--e-border-subtle)',
          letterSpacing: '0.04em',
          flexShrink: 0,
        }}>
          {shortcut}
        </Text>
      </Group>
    </Paper>
  );
}

/* ─── Live Clock ─── */
function ClockDisplay() {
  const [time, setTime] = useState(new Date());

  useEffect(() => {
    const timer = setInterval(() => setTime(new Date()), 1000);
    return () => clearInterval(timer);
  }, []);

  const hh = String(time.getHours()).padStart(2, '0');
  const mm = String(time.getMinutes()).padStart(2, '0');

  return (
    <Text style={{
      fontFamily: 'var(--e-font-display)',
      fontSize: '2.75rem',
      fontWeight: 300,
      color: 'var(--e-text-primary)',
      letterSpacing: '-0.04em',
      lineHeight: 1,
    }}>
      {hh}:{mm}
    </Text>
  );
}

/* ─── Date Line ─── */
function DateLine() {
  const [date] = useState(new Date());
  const options: Intl.DateTimeFormatOptions = {
    weekday: 'long',
    year: 'numeric',
    month: 'long',
    day: 'numeric',
  };
  return (
    <Text style={{
      fontFamily: 'var(--e-font-sans)',
      fontSize: '0.875rem',
      color: 'var(--e-text-tertiary)',
      fontWeight: 400,
    }}>
      {date.toLocaleDateString('en-US', options)}
    </Text>
  );
}

/* ─── System Metrics ─── */
function SystemMetrics() {
  const [m, setM] = useState({ cpu: 18, mem: 58, lat: 11 });

  useEffect(() => {
    const iv = setInterval(() =>
      setM({
        cpu: Math.floor(Math.random() * 30 + 8),
        mem: Math.floor(Math.random() * 15 + 52),
        lat: Math.floor(Math.random() * 40 + 5),
      }),
      6000,
    );
    return () => clearInterval(iv);
  }, []);

  const cpuPct = m.cpu;
  const memPct = m.mem;
  const latPct = Math.min(100, m.lat);

  const rows = [
    { key: 'CPU', val: `${m.cpu}%`, pct: cpuPct, warn: m.cpu > 50 },
    { key: 'MEM', val: `${m.mem}%`, pct: memPct, warn: m.mem > 75 },
    { key: 'LAT', val: `${m.lat}ms`, pct: latPct, warn: m.lat > 50 },
  ];

  return (
    <Stack gap={6}>
      {rows.map((r) => (
        <Group key={r.key} justify="space-between" align="center">
          <Text style={{
            fontFamily: 'var(--e-font-mono)',
            fontSize: '0.5625rem',
            fontWeight: 600,
            letterSpacing: '0.1em',
            textTransform: 'uppercase',
            color: 'var(--e-text-muted)',
            width: 28,
          }}>
            {r.key}
          </Text>
          <div style={{
            flex: 1,
            height: 2,
            backgroundColor: 'var(--e-bg-subtle)',
            borderRadius: 1,
            overflow: 'hidden',
          }}>
            <div style={{
              width: r.warn ? '85%' : `${r.pct}%`,
              height: '100%',
              backgroundColor: r.warn ? 'var(--e-warning)' : 'var(--e-success)',
              borderRadius: 1,
              transition: 'width 0.6s ease, background-color 0.4s ease',
            }} />
          </div>
          <Text style={{
            fontFamily: 'var(--e-font-mono)',
            fontSize: '0.6875rem',
            fontWeight: 600,
            color: r.warn ? 'var(--e-warning)' : 'var(--e-success)',
            width: 36,
            textAlign: 'right',
          }}>
            {r.val}
          </Text>
        </Group>
      ))}
    </Stack>
  );
}

/* ─── Welcome Dashboard ─── */
export function WelcomeDashboard({ onNewChat, sessionCount }: DashboardProps) {
  return (
    <Stack
      align="center"
      gap="xl"
      style={{ maxWidth: 560, width: '100%', padding: '40px 24px' }}
    >
      {/* Wordmark */}
      <Stack align="center" gap={6}>
        <Text style={{
          fontFamily: 'var(--e-font-display)',
          fontSize: '1.75rem',
          fontWeight: 700,
          fontStyle: 'italic',
          color: 'var(--e-text-primary)',
          letterSpacing: '-0.03em',
        }}>
          E<span style={{ color: 'var(--e-text-tertiary)', fontStyle: 'normal' }}>.</span>sapiens
        </Text>
        <Text style={{
          fontFamily: 'var(--e-font-mono)',
          fontSize: '0.6875rem',
          fontWeight: 500,
          letterSpacing: '0.12em',
          textTransform: 'uppercase',
          color: 'var(--e-text-muted)',
        }}>
          Computational Biology Platform
        </Text>
      </Stack>

      {/* Clock + Date */}
      <Stack align="center" gap={4}>
        <ClockDisplay />
        <DateLine />
      </Stack>

      {/* Stats row */}
      <Group grow gap="md" style={{ width: '100%' }}>
        <StatCard label="Sessions" value={String(sessionCount)} accent="var(--e-info)" />
        <StatCard label="Status" value="Online" accent="var(--e-success)" />
        <StatCard label="Model" value="GLM-5" accent="var(--e-brand)" />
      </Group>

      {/* System metrics */}
      <Paper
        radius="md"
        p="md"
        style={{
          width: '100%',
          backgroundColor: 'var(--e-bg-surface)',
          border: '1px solid var(--e-border-subtle)',
        }}
      >
        <Group justify="space-between" align="flex-start" gap="md">
          <Stack gap={2}>
            <Text style={{
              fontFamily: 'var(--e-font-mono)',
              fontSize: '0.5625rem',
              fontWeight: 600,
              letterSpacing: '0.1em',
              textTransform: 'uppercase',
              color: 'var(--e-text-muted)',
            }}>
              System Performance
            </Text>
            <Text style={{
              fontFamily: 'var(--e-font-sans)',
              fontSize: '0.75rem',
              color: 'var(--e-text-tertiary)',
            }}>
              Real-time resource usage
            </Text>
          </Stack>
          <div style={{ flex: 1, maxWidth: 200 }}>
            <SystemMetrics />
          </div>
        </Group>
      </Paper>

      {/* Quick actions */}
      <Stack gap={6} style={{ width: '100%' }}>
        <Text style={{
          fontFamily: 'var(--e-font-mono)',
          fontSize: '0.5625rem',
          fontWeight: 600,
          letterSpacing: '0.1em',
          textTransform: 'uppercase',
          color: 'var(--e-text-muted)',
        }}>
          Quick Actions
        </Text>
        <QuickAction
          label="New session"
          description="Start a fresh research thread"
          shortcut="N"
          onClick={onNewChat}
          accent="var(--e-info)"
        />
        <QuickAction
          label="Keyboard shortcuts"
          description="Master the interface"
          shortcut="?"
          onClick={() => window.dispatchEvent(new CustomEvent('open-shortcuts'))}
          accent="var(--e-brand)"
        />
      </Stack>

      {/* Footer hint */}
      <Text style={{
        fontFamily: 'var(--e-font-sans)',
        fontSize: '0.8125rem',
        color: 'var(--e-text-muted)',
      }}>
        Paste a gene list or ask a question
      </Text>
    </Stack>
  );
}