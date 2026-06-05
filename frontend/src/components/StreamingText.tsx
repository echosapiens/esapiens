"use client";

import { useState, useEffect, useRef } from "react";

interface StreamingTextProps {
  text: string;
  speed?: number;
}

export default function StreamingText({
  text,
  speed = 30,
}: StreamingTextProps) {
  const [displayedChars, setDisplayedChars] = useState(0);
  const [done, setDone] = useState(false);
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  useEffect(() => {
    // Reset when text changes
    setDisplayedChars(0);
    setDone(false);

    if (!text) {
      setDone(true);
      return;
    }

    intervalRef.current = setInterval(() => {
      setDisplayedChars((prev) => {
        const next = prev + 1;
        if (next >= text.length) {
          if (intervalRef.current) clearInterval(intervalRef.current);
          setDone(true);
          return text.length;
        }
        return next;
      });
    }, speed);

    return () => {
      if (intervalRef.current) clearInterval(intervalRef.current);
    };
  }, [text, speed]);

  // If text is empty or fully displayed
  if (!text) return null;

  const visibleText = text.slice(0, displayedChars);

  return (
    <span>
      {visibleText}
      {!done && (
        <span className="inline-block w-[2px] h-4 bg-cyan-400 ml-0.5 animate-pulse align-middle" />
      )}
    </span>
  );
}
