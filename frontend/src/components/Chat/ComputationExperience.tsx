import { useState, useEffect } from 'react';
import { Text } from '@mantine/core';
import { DNAHelix } from './DNAHelix';
import { BioFactTicker } from './BioFactTicker';
import { SequenceGame } from './SequenceGame';
import type { ToolCall } from '../../lib/api';

/* ── Types ── */

type TabId = 'facts' | 'game';

interface ComputationExperienceProps {
  isLoading: boolean;
  toolCalls: ToolCall[];
  /** Milliseconds since loading started */
  elapsedMs?: number;
}

/* ── Tool name formatter ── */
function formatToolName(name: string): string {
  // Convert snake_case or camelCase to a readable label
  return name
    .replace(/_/g, ' ')
    .replace(/([a-z])([A-Z])/g, '$1 $2')
    .toLowerCase()
    .replace(/\b\w/g, (c) => c.toUpperCase());
}

/* ── Progress narrative line ── */
function ProgressNarrative({
  toolCalls,
  elapsedSeconds,
}: {
  toolCalls: ToolCall[];
  elapsedSeconds: number;
}) {
  const running = toolCalls.filter((tc) => tc.status === 'running');
  const completed = toolCalls.filter((tc) => tc.status === 'success');
  const currentTool = running.length > 0 ? running[running.length - 1] : null;

  const statusText = currentTool
    ? `Running ${formatToolName(currentTool.name)}...`
    : completed.length > 0
    ? `${completed.length} tool${completed.length > 1 ? 's' : ''} completed`
    : 'Initializing computation...';

  const mm = String(Math.floor(elapsedSeconds / 60)).padStart(1, '0');
  const ss = String(elapsedSeconds % 60).padStart(2, '0');

  return (
    <div
      style={{
        padding: '8px 14px',
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'center',
      }}
    >
      <Text
        style={{
          fontFamily: 'var(--e-font-mono, Roboto Mono, monospace)',
          fontSize: '0.7rem',
          color: 'var(--e-text-secondary, #525252)',
        }}
      >
        {statusText}
      </Text>
      <Text
        style={{
          fontFamily: 'var(--e-font-mono, Roboto Mono, monospace)',
          fontSize: '0.65rem',
          color: 'var(--e-text-muted, #A3A3A3)',
          fontVariantNumeric: 'tabular-nums',
        }}
      >
        {mm}:{ss}
      </Text>
    </div>
  );
}

/* ── Main component ── */
export function ComputationExperience({
  isLoading,
  toolCalls,
  elapsedMs: elapsedMsProp,
}: ComputationExperienceProps) {
  const [activeTab, setActiveTab] = useState<TabId>('facts');
  const [startTs] = useState(() => Date.now());
  const [elapsed, setElapsed] = useState(0);

  // Track elapsed seconds
  useEffect(() => {
    if (!isLoading) return;
    const timer = setInterval(() => {
      setElapsed(Math.floor((Date.now() - startTs) / 1000));
    }, 1000);
    return () => clearInterval(timer);
  }, [isLoading, startTs]);

  // Use prop value if provided, otherwise derived
  const elapsedSeconds = elapsedMsProp != null ? Math.floor(elapsedMsProp / 1000) : elapsed;

  // Estimate progress: asymptotic approach toward 95%
  const progress = Math.min(95, Math.round(Math.log(elapsedSeconds + 1) * 25 + 5));
  const currentTool = toolCalls
    .filter((tc) => tc.status === 'running')
    .pop();
  const toolName = currentTool?.name;

  if (!isLoading) return null;

  return (
    <div
      style={{
        borderRadius: 'var(--e-radius-2xl, 16px)',
        boxShadow: 'var(--e-shadow-md, 0 2px 8px rgba(0,0,0,0.06))',
        background: 'var(--e-bg-surface, #FFFFFF)',
        border: '1px solid var(--e-border, #E5E5E5)',
        display: 'flex',
        flexDirection: 'column',
        gap: 10,
        padding: 0,
        overflow: 'hidden',
        animation: 'fade-in 300ms ease-out',
      }}
    >
      {/* DNA helix animation */}
      <div style={{ padding: '10px 10px 0 10px' }}>
        <DNAHelix progress={progress} toolName={toolName} />
      </div>

      {/* Progress narrative */}
      <ProgressNarrative toolCalls={toolCalls} elapsedSeconds={elapsedSeconds} />

      {/* Thin separator */}
      <div
        style={{
          height: 1,
          background: 'var(--e-border-subtle, #F0F0F0)',
          margin: '0 14px',
        }}
      />

      {/* Tab header */}
      <div
        style={{
          display: 'flex',
          gap: 0,
          padding: '0 14px',
        }}
      >
        {(['facts', 'game'] as TabId[]).map((tab) => (
          <button
            key={tab}
            onClick={() => setActiveTab(tab)}
            style={{
              fontFamily: 'var(--e-font-mono, Roboto Mono, monospace)',
              fontSize: '0.6rem',
              fontWeight: activeTab === tab ? 700 : 500,
              letterSpacing: '0.1em',
              textTransform: 'uppercase',
              padding: '6px 14px',
              border: 'none',
              borderBottom: activeTab === tab
                ? '2px solid var(--e-accent-cyan, #0891B2)'
                : '2px solid transparent',
              background: 'transparent',
              color: activeTab === tab
                ? 'var(--e-brand)'
                : 'var(--e-text-muted, #A3A3A3)',
              cursor: 'pointer',
              transition: 'all 150ms ease',
            }}
          >
            {tab === 'facts' ? 'Facts' : 'Sequence game'}
          </button>
        ))}
      </div>

      {/* Tab content */}
      <div style={{ minHeight: 72 }}>
        {activeTab === 'facts' ? <BioFactTicker /> : <SequenceGame />}
      </div>
    </div>
  );
}