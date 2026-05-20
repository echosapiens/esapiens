import { useState, useEffect, useRef, useCallback } from 'react';

/**
 * Character-level typewriter animation hook.
 * Reveals text one character at a time at a configurable speed.
 * When content changes, resets and replays.
 */
export function useTypewriter(
  fullText: string,
  speed: number = 20,
  enabled: boolean = true,
): { displayText: string; isAnimating: boolean; skipToEnd: () => void } {
  const [displayIndex, setDisplayIndex] = useState(0);
  const [skipped, setSkipped] = useState(false);
  const prevTextRef = useRef(fullText);
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  // Reset when text content changes
  useEffect(() => {
    if (prevTextRef.current !== fullText) {
      // If the change is small (streaming chunk), don't reset the counter
      // This prevents the flicker/reset during live typing
      const diff = fullText.length - prevTextRef.current.length;
      if (diff > 0 && diff < 500 && fullText.startsWith(prevTextRef.current)) {
         // Keep current index, let the interval catch up
      } else {
         setDisplayIndex(0);
         setSkipped(false);
      }
      prevTextRef.current = fullText;
    }
  }, [fullText]);

  // Character reveal interval
  useEffect(() => {
    if (!enabled || skipped || !fullText) {
      if (intervalRef.current) {
        clearInterval(intervalRef.current);
        intervalRef.current = null;
      }
      if (!enabled || skipped) {
        setDisplayIndex(fullText.length);
      }
      return;
    }

    // If already fully revealed, do nothing
    if (displayIndex >= fullText.length) {
      return;
    }

    intervalRef.current = setInterval(() => {
      setDisplayIndex((prev) => {
        // Reveal 1-3 chars per tick for natural feel
        const increment = Math.random() < 0.3 ? 3 : Math.random() < 0.5 ? 2 : 1;
        const next = Math.min(prev + increment, fullText.length);
        if (next >= fullText.length && intervalRef.current) {
          clearInterval(intervalRef.current);
          intervalRef.current = null;
        }
        return next;
      });
    }, speed);

    return () => {
      if (intervalRef.current) {
        clearInterval(intervalRef.current);
        intervalRef.current = null;
      }
    };
  }, [enabled, skipped, fullText, speed, displayIndex]);

  const skipToEnd = useCallback(() => {
    setSkipped(true);
    setDisplayIndex(fullText.length);
    if (intervalRef.current) {
      clearInterval(intervalRef.current);
      intervalRef.current = null;
    }
  }, [fullText]);

  return {
    displayText: fullText.slice(0, displayIndex),
    isAnimating: enabled && !skipped && displayIndex < fullText.length,
    skipToEnd,
  };
}