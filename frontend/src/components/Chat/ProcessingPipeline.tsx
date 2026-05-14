import { useState, useEffect, useRef } from 'react';
import { Group, Text } from '@mantine/core';
import type { ToolCall } from '../../lib/api';

interface ProcessingPipelineProps {
  toolCalls: ToolCall[];
}

/* ─── Animated Step Node ─── */
function StepNode({
  name,
  status,
  index,
  isLast,
}: {
  name: string;
  status?: string;
  index: number;
  isLast: boolean;
}) {
  const isRunning = status === 'running' || !status;
  const isSuccess = status === 'success';
  const isError = status === 'error';

  const icon = isRunning ? '◌' : isSuccess ? '✓' : '✗';
  const color = isError ? 'var(--e-accent-red)' : isRunning ? 'var(--e-accent-amber)' : 'var(--e-accent-green)';
  const [pulsing, setPulsing] = useState(isRunning);

  useEffect(() => {
    if (isRunning) {
      const interval = setInterval(() => setPulsing((p) => !p), 800);
      return () => clearInterval(interval);
    }
    setPulsing(false);
  }, [isRunning]);

  return (
    <div
      style={{
        display: 'flex',
        alignItems: 'stretch',
        gap: 0,
        opacity: isRunning ? 1 : isSuccess ? 0.8 : 0.7,
        animation: isSuccess ? 'fade-in-up 0.3s ease-out' : undefined,
      }}
    >
      {/* Connector line */}
      <div
        style={{
          display: 'flex',
          flexDirection: 'column',
          alignItems: 'center',
          width: 20,
          position: 'relative',
        }}
      >
        {/* Node dot */}
        <div
          style={{
            width: 12,
            height: 12,
            borderRadius: '50%',
            backgroundColor: color,
            boxShadow: pulsing ? `0 0 12px ${color}` : 'none',
            transition: 'all 0.3s ease',
            zIndex: 1,
            flexShrink: 0,
          }}
        />
        {/* Vertical connector line */}
        {!isLast && (
          <div
            style={{
              width: 1,
              flex: 1,
              backgroundColor: 'var(--e-border)',
              marginTop: 2,
            }}
          />
        )}
      </div>

      {/* Step content */}
      <div
        style={{
          flex: 1,
          paddingLeft: 8,
          paddingBottom: isLast ? 0 : 12,
        }}
      >
        <Group gap={6} mb={2}>
          <Text
            style={{
              fontFamily: "var(--e-font-mono)",
              fontSize: '0.6rem',
              color,
              fontWeight: 600,
              letterSpacing: '0.08em',
            }}
          >
            {icon}
          </Text>
          <Text
            style={{
              fontFamily: "var(--e-font-mono)",
              fontSize: '0.65rem',
              color: 'var(--e-text-secondary)',
            }}
          >
            {name}
          </Text>
        </Group>
      </div>
    </div>
  );
}

/* ─── ProcessingPipeline ─── */
export function ProcessingPipeline({ toolCalls }: ProcessingPipelineProps) {
  if (!toolCalls || toolCalls.length === 0) return null;

  // Show last 5 tool calls max
  const visible = toolCalls.slice(-5);

  return (
    <div
      style={{
        padding: '8px 0',
        marginBottom: 4,
      }}
    >
      <Text
        style={{
          fontFamily: "var(--e-font-mono)",
          fontSize: '0.5rem',
          fontWeight: 600,
          letterSpacing: '0.12em',
          textTransform: 'uppercase',
          color: 'var(--e-text-dimmed)',
          marginBottom: 6,
          marginLeft: 28,
        }}
      >
        PIPELINE
      </Text>
      {visible.map((tc, idx) => (
        <StepNode
          key={tc.id}
          name={tc.name}
          status={tc.status}
          index={idx}
          isLast={idx === visible.length - 1}
        />
      ))}
    </div>
  );
}