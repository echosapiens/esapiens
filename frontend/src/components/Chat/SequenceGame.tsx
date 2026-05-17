import { useState, useEffect, useCallback } from 'react';

/* ── Sequence alignment mini-game ──
   A reference sequence is shown. The player's sequence is shuffled
   and they must swap adjacent bases to sort it back into the correct
   order. 30-second timer, score = number of bases in correct position.
*/

const BASES = ['A', 'T', 'C', 'G'];

function randomSeq(len: number): string[] {
  return Array.from({ length: len }, () => BASES[Math.floor(Math.random() * 4)]);
}

/** Fisher-Yates shuffle; guarantees the result differs from original. */
function shuffleArray<T>(arr: T[]): T[] {
  const a = [...arr];
  for (let i = a.length - 1; i > 0; i--) {
    const j = Math.floor(Math.random() * (i + 1));
    [a[i], a[j]] = [a[j], a[i]];
  }
  // Ensure at least 2 positions are different (avoid trivial solution)
  if (a.every((v, i) => v === arr[i])) {
    // swap first two non-identical elements
    for (let i = 0; i < a.length - 1; i++) {
      if (a[i] !== a[i + 1]) {
        [a[i], a[i + 1]] = [a[i + 1], a[i]];
        break;
      }
    }
  }
  return a;
}

/** Count positions where attempt matches reference */
function computeMatches(reference: string[], attempt: string[]): number {
  let matches = 0;
  for (let i = 0; i < reference.length; i++) {
    if (i < attempt.length && reference[i] === attempt[i]) matches++;
  }
  return matches;
}

const ROUND_SECONDS = 30;

const baseColorMap: Record<string, string> = {
  A: '#059669',  // green
  T: '#DC2626',  // red
  C: '#2563EB',  // blue
  G: '#D97706',  // amber
};

export function SequenceGame() {
  const [reference, setReference] = useState<string[]>(() => randomSeq(10));
  const [playerSeq, setPlayerSeq] = useState<string[]>(() => {
    const r = randomSeq(10);
    return shuffleArray(r);
  });
  const [selectedIdx, setSelectedIdx] = useState<number | null>(null);
  const [timeLeft, setTimeLeft] = useState(ROUND_SECONDS);
  const [running, setRunning] = useState(true);
  const [moveCount, setMoveCount] = useState(0);

  const matches = computeMatches(reference, playerSeq);
  const perfect = matches === reference.length;

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

  // Auto-stop on perfect score
  useEffect(() => {
    if (perfect && running) {
      setRunning(false);
    }
  }, [perfect, running]);

  const newRound = useCallback(() => {
    const len = 8 + Math.floor(Math.random() * 5); // 8-12
    const ref = randomSeq(len);
    const shf = shuffleArray([...ref]);
    setReference(ref);
    setPlayerSeq(shf);
    setSelectedIdx(null);
    setTimeLeft(ROUND_SECONDS);
    setRunning(true);
    setMoveCount(0);
  }, []);

  /** Click a base to select it; if already selected, swap the two */
  const handleBaseClick = useCallback((idx: number) => {
    if (!running) return;
    if (selectedIdx === null) {
      setSelectedIdx(idx);
    } else if (selectedIdx === idx) {
      // Deselect
      setSelectedIdx(null);
    } else {
      // Swap the two bases
      setPlayerSeq((prev) => {
        const next = [...prev];
        [next[selectedIdx], next[idx]] = [next[idx], next[selectedIdx]];
        return next;
      });
      setMoveCount((m) => m + 1);
      setSelectedIdx(null);
    }
  }, [selectedIdx, running]);

  const formatKey = (base: string, i: number) => `${base}-${i}`;

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
            {matches}/{reference.length}
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
              border: '1px solid var(--e-border, #E5E5E5)',
              borderRadius: 3,
              color: baseColorMap[base] || '#525252',
              fontWeight: 600,
            }}
          >
            {base}
          </div>
        ))}
      </div>

      {/* Match indicators */}
      <div
        style={{
          display: 'flex',
          gap: 3,
          fontFamily: 'var(--e-font-mono, Roboto Mono, monospace)',
          fontSize: '0.6rem',
          marginBottom: 4,
        }}
      >
        {reference.map((base, i) => {
          const isMatch = playerSeq[i] === base;
          return (
            <div key={i} style={{ width: 24, textAlign: 'center', color: isMatch ? 'var(--e-accent-green, #059669)' : 'transparent', fontWeight: 700 }}>
              |
            </div>
          );
        })}
      </div>

      {/* Player sequence (swappable) */}
      <div style={{ marginBottom: 4 }}>
        <span
          style={{
            fontFamily: 'var(--e-font-mono, Roboto Mono, monospace)',
            fontSize: '0.5rem',
            color: 'var(--e-text-muted, #A3A3A3)',
            letterSpacing: '0.08em',
          }}
        >
          YOUR ALIGNMENT — tap two bases to swap
        </span>
      </div>
      <div
        style={{
          display: 'flex',
          gap: 3,
          fontFamily: 'var(--e-font-mono, Roboto Mono, monospace)',
          fontSize: '0.75rem',
          marginBottom: 10,
        }}
      >
        {playerSeq.map((base, i) => {
          const isMatch = reference[i] === base;
          const isSelected = selectedIdx === i;
          return (
            <div
              key={formatKey(base, i)}
              onClick={() => handleBaseClick(i)}
              style={{
                width: 24,
                height: 24,
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                backgroundColor: isSelected
                  ? 'rgba(37,99,235,0.15)'
                  : isMatch
                  ? 'rgba(5,150,105,0.12)'
                  : 'var(--e-bg-subtle, #F5F5F5)',
                border: `1.5px solid ${
                  isSelected
                    ? 'var(--e-accent-blue, #2563EB)'
                    : isMatch
                    ? 'var(--e-accent-green, #059669)'
                    : 'var(--e-border, #E5E5E5)'
                }`,
                borderRadius: 3,
                color: isSelected
                  ? 'var(--e-accent-blue, #2563EB)'
                  : isMatch
                  ? 'var(--e-accent-green, #059669)'
                  : baseColorMap[base] || '#525252',
                fontWeight: 600,
                cursor: running ? 'pointer' : 'default',
                transition: 'all 120ms ease',
                boxShadow: isSelected ? '0 0 0 2px rgba(37,99,235,0.25)' : 'none',
              }}
            >
              {base}
            </div>
          );
        })}
      </div>

      {/* Controls */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <div style={{ display: 'flex', gap: 12, alignItems: 'center' }}>
          <span
            style={{
              fontFamily: 'var(--e-font-mono, Roboto Mono, monospace)',
              fontSize: '0.6rem',
              color: 'var(--e-text-muted, #A3A3A3)',
            }}
          >
            {moveCount} {moveCount === 1 ? 'move' : 'moves'}
          </span>
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
            ? `Perfect alignment in ${moveCount} ${moveCount === 1 ? 'move' : 'moves'}.`
            : `Time expired. ${matches} of ${reference.length} bases aligned.`}
        </div>
      )}
    </div>
  );
}