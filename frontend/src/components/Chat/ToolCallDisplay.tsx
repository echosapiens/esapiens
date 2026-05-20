import { memo } from 'react';
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

export const ToolCallDisplay = memo(function ToolCallDisplay({ toolCall }: ToolCallDisplayProps) {
  // Truncate heavy payloads even before JSON stringify if they are huge
  const stringifiedArgs = JSON.stringify(toolCall.args, null, 2);
  const truncatedArgs = stringifiedArgs.length > 5000 
    ? `${stringifiedArgs.slice(0, 5000)}\n... (args truncated, ${stringifiedArgs.length} chars)`
    : stringifiedArgs;

  return (
    <Accordion.Item key={toolCall.id} value={toolCall.id}>
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
              maxHeight: '200px',
            }}
          >
            {truncatedArgs}
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
                maxHeight: '300px',
              }}
            >
              {toolCall.result.length > 3000
                ? `${toolCall.result.slice(0, 3000)}\n... (result truncated, ${toolCall.result.length} chars)`
                : toolCall.result}
            </pre>
          </div>
        )}
      </Accordion.Panel>
    </Accordion.Item>
  );
});
