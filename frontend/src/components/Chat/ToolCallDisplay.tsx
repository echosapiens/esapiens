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
  if (!toolCall) return null;
  const tcId = toolCall.id || `tc_missing_fallback`;

  // Truncate heavy payloads even before JSON stringify if they are huge
  const stringifiedArgs = JSON.stringify(toolCall.args || {}, null, 2);
  const truncatedArgs = stringifiedArgs.length > 5000 
    ? `${stringifiedArgs.slice(0, 5000)}\n... (args truncated, ${stringifiedArgs.length} chars)`
    : stringifiedArgs;

  return (
    <Accordion.Item key={tcId} value={tcId}>
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
            <ResultRenderer result={toolCall.result} status={toolCall.status} />
          </div>
        )}
      </Accordion.Panel>
    </Accordion.Item>
  );
});

/* ─── Result renderer — images vs JSON vs raw text ─── */
function ResultRenderer({ result, status }: { result: string; status?: string }) {
  // Case 1: data URL (image)
  if (/^data:image\//.test(result)) {
    return (
      <div style={{ padding: '6px 8px', backgroundColor: 'var(--e-bg-deep)', border: '1px solid var(--e-border)' }}>
        <img
          src={result}
          alt="Result visualization"
          style={{ maxWidth: '100%', maxHeight: 300, borderRadius: 4 }}
        />
      </div>
    );
  }

  // Case 2: JSON string with image field
  let parsed: Record<string, unknown> | null = null;
  try { parsed = JSON.parse(result); } catch { /* not JSON */ }

  if (parsed && typeof parsed === 'object') {
    const p = parsed as Record<string, unknown>;

    // { type: 'image', image: 'data:image/...' }
    if (p.type === 'image' && typeof p.image === 'string' && /^data:image\//.test(p.image)) {
      return (
        <div style={{ padding: '6px 8px', backgroundColor: 'var(--e-bg-deep)', border: '1px solid var(--e-border)' }}>
          <img
            src={p.image}
            alt="Result visualization"
            style={{ maxWidth: '100%', maxHeight: 300, borderRadius: 4 }}
          />
        </div>
      );
    }

    // { type: 'image', data: 'base64,...' } — Some backends flatten it this way
    if (p.type === 'image' && typeof p.data === 'string') {
      const raw = p.data as string;
      if (raw.startsWith('data:image/') || /^[A-Za-z0-9+/=]{40,}$/.test(raw)) {
        const mime = (p.format as string) || 'image/png';
        return (
          <div style={{ padding: '6px 8px', backgroundColor: 'var(--e-bg-deep)', border: '1px solid var(--e-border)' }}>
            <img
              src={raw.startsWith('data:') ? raw : `data:${mime};base64,${raw}`}
              alt="Result visualization"
              style={{ maxWidth: '100%', maxHeight: 300, borderRadius: 4 }}
            />
          </div>
        );
      }
    }

    // Case 3: Structured JSON (non-image) — pretty-print
    const jsonStr = JSON.stringify(p, null, 2);
    const truncated = jsonStr.length > 3000
      ? `${jsonStr.slice(0, 3000)}\n... (result truncated, ${jsonStr.length} chars)`
      : jsonStr;

    return (
      <pre
        style={{
          fontFamily: "var(--e-font-mono)",
          fontSize: '0.6rem',
          color: status === 'error' ? 'var(--e-accent-red)' : 'var(--e-accent-green)',
          backgroundColor: 'var(--e-bg-deep)',
          padding: '6px 8px',
          margin: 0,
          overflow: 'auto',
          border: '1px solid var(--e-border)',
          lineHeight: 1.6,
          maxHeight: '300px',
        }}
      >
        {truncated}
      </pre>
    );
  }

  // Case 4: Plain text — truncate
  const truncated = result.length > 3000
    ? `${result.slice(0, 3000)}\n... (result truncated, ${result.length} chars)`
    : result;

  return (
    <pre
      style={{
        fontFamily: "var(--e-font-mono)",
        fontSize: '0.6rem',
        color: status === 'error' ? 'var(--e-accent-red)' : 'var(--e-accent-green)',
        backgroundColor: 'var(--e-bg-deep)',
        padding: '6px 8px',
        margin: 0,
        overflow: 'auto',
        border: '1px solid var(--e-border)',
        lineHeight: 1.6,
        maxHeight: '300px',
      }}
    >
      {truncated}
    </pre>
  );
}
