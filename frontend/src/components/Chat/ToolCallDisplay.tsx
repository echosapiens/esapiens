import { Accordion, Text } from '@mantine/core';
import type { ToolCall } from '../../lib/api';

interface ToolCallDisplayProps {
  toolCall: ToolCall;
}

/* ─── Status Indicator ─── */
function StatusBadge({ status }: { status?: string }) {
  const config = {
    running: { icon: '◌', color: 'var(--e-accent-amber)' },
    success: { icon: '✓', color: 'var(--e-accent-green)' },
    error: { icon: '✗', color: 'var(--e-accent-red)' },
  } as const;

  const { icon, color } = config[status as keyof typeof config] || config.running;
  const label = status === 'error' ? 'FAILED' : status === 'success' ? 'DONE' : 'RUNNING';

  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
      <Text
        style={{
          fontFamily: "var(--e-font-mono)",
          fontSize: '0.6rem',
          color,
          fontWeight: 600,
        }}
      >
        {icon}
      </Text>
      <Text
        style={{
          fontFamily: "var(--e-font-mono)",
          fontSize: '0.55rem',
          color,
          fontWeight: 500,
          letterSpacing: '0.1em',
        }}
      >
        {label}
      </Text>
    </div>
  );
}

/* ─── Accordion Label ─── */
function ToolCallLabel({ name, status }: { name: string; status?: string }) {
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 8, width: '100%' }}>
      <Text
        style={{
          fontFamily: "var(--e-font-mono)",
          fontSize: '0.65rem',
          color: 'var(--e-text-secondary)',
          fontWeight: 500,
        }}
      >
        {name}
      </Text>
      <StatusBadge status={status} />
    </div>
  );
}

export function ToolCallDisplay({ toolCall }: ToolCallDisplayProps) {
  return (
    <Accordion
      variant="contained"
      mt={4}
      styles={{
        item: {
          backgroundColor: 'transparent',
          border: '1px solid var(--e-border)',
          marginBottom: 2,
        },
        control: {
          padding: '6px 10px',
          minHeight: 0,
          '&:hover': {
            backgroundColor: 'rgba(0, 191, 255, 0.03)',
          },
        },
        panel: {
          padding: '6px 10px',
        },
        chevron: {
          width: 12,
          height: 12,
          color: 'var(--e-text-dimmed)',
        },
      }}
    >
      <Accordion.Item value={toolCall.id}>
        <Accordion.Control>
          <ToolCallLabel name={toolCall.name} status={toolCall.status} />
        </Accordion.Control>
        <Accordion.Panel>
          {/* Arguments */}
          <div style={{ marginBottom: 4 }}>
            <Text
              style={{
                fontFamily: "var(--e-font-mono)",
                fontSize: '0.5rem',
                fontWeight: 600,
                letterSpacing: '0.12em',
                textTransform: 'uppercase',
                color: 'var(--e-text-dimmed)',
                marginBottom: 2,
              }}
            >
              ARGS
            </Text>
            <pre
              style={{
                fontFamily: "var(--e-font-mono)",
                fontSize: '0.6rem',
                color: 'var(--e-text-secondary)',
                backgroundColor: 'var(--e-bg-deep)',
                padding: '6px 8px',
                margin: 0,
                overflow: 'auto',
                border: '1px solid var(--e-border)',
              }}
            >
              {JSON.stringify(toolCall.args, null, 2)}
            </pre>
          </div>

          {/* Result */}
          {toolCall.result !== undefined && toolCall.result !== null && (
            <div>
              <Text
                style={{
                  fontFamily: "var(--e-font-mono)",
                  fontSize: '0.5rem',
                  fontWeight: 600,
                  letterSpacing: '0.12em',
                  textTransform: 'uppercase',
                  color: 'var(--e-text-dimmed)',
                  marginBottom: 2,
                  marginTop: 6,
                }}
              >
                RESULT
              </Text>
              <pre
                style={{
                  fontFamily: "var(--e-font-mono)",
                  fontSize: '0.6rem',
                  color: toolCall.status === 'error' ? 'var(--e-accent-red)' : 'var(--e-accent-green)',
                  backgroundColor: 'var(--e-bg-deep)',
                  padding: '6px 8px',
                  margin: 0,
                  overflow: 'auto',
                  border: '1px solid var(--e-border)',
                  lineHeight: 1.6,
                }}
              >
                {toolCall.result.length > 2000
                  ? `${toolCall.result.slice(0, 2000)}\n... (truncated, ${toolCall.result.length} chars)`
                  : toolCall.result}
              </pre>
            </div>
          )}
        </Accordion.Panel>
      </Accordion.Item>
    </Accordion>
  );
}