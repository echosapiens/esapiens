import { useRef, useEffect } from 'react';

/**
 * Purely decorative: floating 0/1 binary digits that drift upward
 * behind the plexus background. Useless. Beautiful.
 */
export function BinaryRain() {
  const canvasRef = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    let animId: number;

    // Characters — hex + binary for richness
    const chars = '01';
    const fontSize = 10;
    const columns: number[] = [];

    function resize() {
      if (!canvas) return;
      canvas.width = window.innerWidth;
      canvas.height = window.innerHeight;

      // Reset columns on resize
      columns.length = 0;
      const colCount = Math.floor(canvas.width / (fontSize * 1.5));
      for (let i = 0; i < colCount; i++) {
        columns.push(Math.random() * -canvas.height); // staggered start
      }
    }

    resize();

    function draw() {
      if (!ctx || !canvas) return;
      ctx.clearRect(0, 0, canvas.width, canvas.height);

      // Very subtle dark tint
      ctx.fillStyle = 'rgba(7, 7, 11, 0.05)';
      ctx.fillRect(0, 0, canvas.width, canvas.height);

      ctx.font = `${fontSize}px 'Roboto Mono', monospace`;

      for (let i = 0; i < columns.length; i++) {
        const x = i * fontSize * 1.5;
        const y = columns[i];

        // Draw a character
        const char = chars[Math.floor(Math.random() * chars.length)];
        const alpha = Math.max(0, 0.08 - (y / canvas.height) * 0.06);
        ctx.fillStyle = `rgba(0, 245, 255, ${alpha})`;
        ctx.fillText(char, x, y);

        // Move column down
        columns[i] += fontSize * 0.3;

        // Reset when off-screen
        if (columns[i] > canvas.height + fontSize) {
          columns[i] = -fontSize * Math.random() * 10;
        }
      }

      animId = requestAnimationFrame(draw);
    }

    draw();

    window.addEventListener('resize', resize);

    return () => {
      cancelAnimationFrame(animId);
      window.removeEventListener('resize', resize);
    };
  }, []);

  return (
    <canvas
      ref={canvasRef}
      style={{
        position: 'fixed',
        inset: 0,
        pointerEvents: 'none',
        zIndex: 0,
        opacity: 0.5,
      }}
    />
  );
}