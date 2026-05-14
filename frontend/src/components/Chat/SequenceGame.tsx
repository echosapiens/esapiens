import { useState, useEffect, useCallback } from 'react';

/* ── Sequence alignment mini-game ── */

const BASES = ['A', 'T', 'C', 'G'];

function randomSeq(len: number): string[] {
  return Array.from({ length: len }, () => BASES[Math.floor(Math.random() * 4)]);
}

function shuffleArray<T>(arr: T[]): T[] {
  const a = [...arr];
  for (let i = a.length - 1; i > 0; i--) {
    const j = Math.floor(Math.random() * (i + 1));
    [a[i], a[j]] = [a[j], a[i]];
  }
  return a;
}

function computeScore(ref: string[], attempt: string[], offset: number): number {
  let score = 0;
  for (let i = 0; i < ref.length; i++) {
    const j = i + offset;
    if (j >= 0 && j < attempt.length && ref[i] === attempt[j]) {
      score++;
    }
  }
  return score;
}

const ROUND_SECONDS = 30;

const baseColorMap: Record<string, string> = {
  A: '#059669',  // green
  T: '#DC2626',  // red
  C: '#2563EB',  // blue
  G: '#D97706',  // amber
};

export function SequenceGame() {
  const [seqLen, setSeqLen] = useState(10);
  const [reference, setReference] = useState<string[]>(() => randomSeq(10));
  const [shuffled, setShuffled] = useState<string[]>(() => {
    const r = randomSeq(10);
    return shuffleArray(r);
  });
  const [offset, setOffset] = useState(0);
  const [timeLeft, setTimeLeft] = useState(ROUND_SECONDS);
  const [running, setRunning] = useState(true);

  const maxShift = seqLen; // allow shifting up to full length in either direction

  const score = computeScore(reference, shuffled, offset);

  // Timer
  useEffect(() => {
    if (!running) return;
    const timer = setInterval(() => {
      setTimeLeft((t) => {
        if (t <= 1) {
          setRunning(false);
          return 0;
        }
        return t - 1;
      });
    }, 1000);
    return () => clearInterval(timer);
  }, [running]);

  const newRound = useCallback(() => {
    const len = 8 + Math.floor(Math.random() * 5); // 8-12
    const ref = randomSeq(len);
    const shf = shuffleArray([...ref]);
    setSeqLen(len);
    setReference(ref);
    setShuffled(shf);
    setOffset(0);
    setTimeLeft(ROUND_SECONDS);
    setRunning(true);
  }, []);

  const shiftLeft = useCallback(() => {
    if (running) setOffset((o) => Math.max(o - 1, -maxShift));
  }, [running, maxShift]);

  const shiftRight = useCallback(() => {
    if (running) setOffset((o) => Math.min(o + 1, maxShift));
  }, [running, maxShift]);

  const perfect = score === reference.length;

  // Auto-stop on perfect score
  useEffect(() => {
    if (perfect && running) {
      setRunning(false);
    }
  }, [perfect, running]);

  const displayRange = Math.max(reference.length + Math.abs(offset), reference.length + 4);

  return (
    <div style={{ padding: '10px 14px' }}>
      {/* Header */}
      <div
        style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          marginBottom: 8,
        }}
      >
        <span
          style={{
            fontFamily: 'var(--e-font-mono, Roboto Mono, monospace)',
            fontSize: '0.55rem',
            fontWeight: 700,
            letterSpacing: '0.14em',
            textTransform: 'uppercase',
            color: 'var(--e-accent-blue, #2563EB)',
          }}
        >
          Sequence alignment
        </span>
        <div style={{ display: 'flex', gap: 12, alignItems: 'center' }}>
          <span
            style={{
              fontFamily: 'var(--e-font-mono, Roboto Mono, monospace)',
              fontSize: '0.7rem',
              color: timeLeft <= 10 ? 'var(--e-accent-red, #DC2626)' : 'var(--e-text-muted, #A3A3A3)',
            }}
          >
            {timeLeft}s
          </span>
          <span
            style={{
              fontFamily: 'var(--e-font-mono, Roboto Mono, monospace)',
              fontSize: '0.7rem',
              color: perfect ? 'var(--e-accent-green, #059669)' : 'var(--e-text-secondary, #525252)',
            }}
          >
            {score}/{reference.length}
          </span>
        </div>
      </div>

      {/* Reference sequence */}
      <div style={{ marginBottom: 4 }}>
        <span
          style={{
            fontFamily: 'var(--e-font-mono, Roboto Mono, monospace)',
            fontSize: '0.5rem',
            color: 'var(--e-text-muted, #A3A3A3)',
            letterSpacing: '0.08em',
          }}
        >
          REFERENCE
        </span>
      </div>
      <div
        style={{
          display: 'flex',
          gap: 3,
          fontFamily: 'var(--e-font-mono, Roboto Mono, monospace)',
          fontSize: '0.75rem',
          marginBottom: 10,
          overflowX: 'auto',
        }}
      >
        {reference.map((base, i) => (
          <div
            key={i}
            style={{
              width: 24,
              height: 24,
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              backgroundColor: 'var(--e-bg-subtle, #F5F5F5)',
              border: `1px solid var(--e-border, #E5E5E5)`,
              borderRadius: 3,
              color: baseColorMap[base] || '#525252',
              fontWeight: 600,
            }}
          >
            {base}
          </div>
        ))}
      </div>

      {/* Shifted sequence */}
      <div style={{ marginBottom: 4 }}>
        <span
          style={{
            fontFamily: 'var(--e-font-mono, Roboto Mono, monospace)',
            fontSize: '0.5rem',
            color: 'var(--e-text-muted, #A3A3A3)',
            letterSpacing: '0.08em',
          }}
        >
          YOUR ALIGNMENT
        </span>
      </div>
      <div
        style={{
          display: 'flex',
          gap: 3,
          fontFamily: 'var(--e-font-mono, Roboto Mono, monospace)',
          fontSize: '0.75rem',
          marginBottom: 10,
          overflowX: 'auto',
          paddingLeft: offset > 0 ? offset * 27 : 0,
          marginLeft: offset < 0 ? offset * 27 : 0,
        }}
      >
        {/* Padding for negative offset */}
        {offset < 0 &&
          Array.from({ length: Math.abs(offset) }).map((_, k) => (
            <div
              key={`pad-l-${k}`}
              style={{
                width: 24,
                height: 24,
                opacity: 0.2,
              }}
            />
          ))}
        {shuffled.map((base, i) => {
          const refIdx = i - offset; // which reference position does this align to?
          const isMatch = refIdx >= 0 && refIdx < reference.length && reference[refIdx] === base;
          return (
            <div
              key={i}
              style={{
                width: 24,
                height: 24,
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                backgroundColor: isMatch ? 'rgba(5,150,105,0.12)' : 'var(--e-bg-subtle, #F5F5F5)',
                border: `1px solid ${isMatch ? 'var(--e-accent-green, #059669)' : 'var(--e-border, #E5E5E5)'}`,
                borderRadius: 3,
                color: isMatch ? 'var(--e-accent-green, #059669)' : baseColorMap[base] || '#525252',
                fontWeight: 600,
                transition: 'all 150ms ease',
              }}
            >
              {base}
            </div>
          );
        })}
        {/* Padding for positive offset */}
        {offset > 0 &&
          Array.from({ length: offset }).map((_, k) => (
            <div
              key={`pad-r-${k}`}
              style={{
                width: 24,
                height: 24,
                opacity: 0.2,
              }}
            />
          ))}
      </div>

      {/* Match indicator row */}
      <div
        style={{
          display: 'flex',
          gap: 3,
          paddingLeft: offset > 0 ? offset * 27 : 0,
          marginLeft: offset < 0 ? offset * 27 : 0,
          fontFamily: 'var(--e-font-mono, Roboto Mono, monospace)',
          fontSize: '0.6rem',
          color: 'var(--e-text-muted, #A3A3A3)',
          marginBottom: 12,
        }}
      >
        {offset < 0 &&
          Array.from({ length: Math.abs(offset) }).map((_, k) => (
            <div key={`mi-l-${k}`} style={{ width: 24, textAlign: 'center' }} />
          ))}
        {reference.map((_, i) => {
          const j = i + offset;
          const isMatch = j >= 0 && j < shuffled.length && reference[i] === shuffled[j];
          return (
            <div key={`mi-${i}`} style={{ width: 24, textAlign: 'center' }}>
              {isMatch ? '|' : ''}
            </div>
          );
        })}
      </div>

      {/* Controls */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <div style={{ display: 'flex', gap: 6 }}>
          <button
            onClick={shiftLeft}
            disabled={!running}
            style={{
              fontFamily: 'var(--e-font-mono, Roboto Mono, monospace)',
              fontSize: '0.65rem',
              padding: '4px 10px',
              border: '1px solid var(--e-border, #E5E5E5)',
              borderRadius: 'var(--e-radius-lg, 8px)',
              background: 'var(--e-bg-surface, #FFFFFF)',
              color: 'var(--e-text-secondary, #525252)',
              cursor: running ? 'pointer' : 'not-allowed',
              opacity: running ? 1 : 0.5,
            }}
          >
            &larr; Shift left
          </button>
          <button
            onClick={shiftRight}
            disabled={!running}
            style={{
              fontFamily: 'var(--e-font-mono, Roboto Mono, monospace)',
              fontSize: '0.65rem',
              padding: '4px 10px',
              border: '1px solid var(--e-border, #E5E5E5)',
              borderRadius: 'var(--e-radius-lg, 8px)',
              background: 'var(--e-bg-surface, #FFFFFF)',
              color: 'var(--e-text-secondary, #525252)',
              cursor: running ? 'pointer' : 'not-allowed',
              opacity: running ? 1 : 0.5,
            }}
          >
            Shift right &rarr;
          </button>
        </div>
        <button
          onClick={newRound}
          style={{
            fontFamily: 'var(--e-font-mono, Roboto Mono, monospace)',
            fontSize: '0.6rem',
            fontWeight: 600,
            letterSpacing: '0.08em',
            textTransform: 'uppercase',
            padding: '4px 12px',
            border: '1px solid var(--e-border, #E5E5E5)',
            borderRadius: 'var(--e-radius-lg, 8px)',
            background: 'var(--e-bg-subtle, #F5F5F5)',
            color: 'var(--e-text-secondary, #525252)',
            cursor: 'pointer',
          }}
        >
          New round
        </button>
      </div>

      {/* Result message */}
      {!running && (
        <div
          style={{
            marginTop: 8,
            fontFamily: 'var(--e-font-mono, Roboto Mono, monospace)',
            fontSize: '0.65rem',
            color: perfect
              ? 'var(--e-accent-green, #059669)'
              : 'var(--e-text-secondary, #525252)',
            textAlign: 'center',
          }}
        >
          {perfect
            ? 'Perfect alignment achieved.'
            : `Time expired. ${score} of ${reference.length} bases aligned.`}
        </div>
      )}
    </div>
  );
}