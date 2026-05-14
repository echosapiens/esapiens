import { useRef, useEffect, useCallback } from 'react';

interface DNAHelixProps {
  progress: number; // 0-100
  toolName?: string;
}

/* ── Pure-canvas DNA double helix with scanning overlay ── */
export function DNAHelix({ progress, toolName }: DNAHelixProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const frameRef = useRef<number>(0);
  const progressRef = useRef(progress);
  progressRef.current = progress;

  const draw = useCallback(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    const dpr = window.devicePixelRatio || 1;
    const w = canvas.clientWidth;
    const h = canvas.clientHeight;
    canvas.width = w * dpr;
    canvas.height = h * dpr;
    ctx.scale(dpr, dpr);

    // Clear with subtle background
    ctx.fillStyle = '#FAFAFA';
    ctx.fillRect(0, 0, w, h);

    const now = Date.now();
    const phase = now * 0.0004; // slow rotation

    const cx = w / 2;
    const topY = 20;
    const bottomY = h - 30;
    const helixHeight = bottomY - topY;
    const amplitude = Math.min(w * 0.22, 80);
    const pairs = 12; // number of base-pair rungs
    const stepY = helixHeight / pairs;

    // Draw base-pair connections and nucleotide labels
    const complementMap: Record<string, string> = { A: 'T', T: 'A', C: 'G', G: 'C' };
    const bases = ['A', 'T', 'C', 'G'];

    for (let i = 0; i <= pairs; i++) {
      const y = topY + i * stepY;
      const angle = phase + i * 0.55;
      const x1 = cx + Math.sin(angle) * amplitude;
      const x2 = cx + Math.sin(angle + Math.PI) * amplitude;

      // Depth-based opacity — "back" strand is dimmer
      const depthA = (Math.cos(angle) + 1) / 2;
      const depthB = (Math.cos(angle + Math.PI) + 1) / 2;

      // Draw base-pair rung (thin line connecting the two strands)
      const rungAlpha = 0.12 + 0.18 * Math.min(depthA, depthB);
      ctx.beginPath();
      ctx.moveTo(x1, y);
      ctx.lineTo(x2, y);
      ctx.strokeStyle = `rgba(8,145,178,${rungAlpha})`;
      ctx.lineWidth = 0.8;
      ctx.stroke();

      // Small nucleotide labels at every other rung
      if (i % 2 === 0 && i < pairs) {
        const baseL = bases[(i * 3 + 1) % 4];
        const baseR = complementMap[baseL];
        const labelAlpha = 0.25 + 0.35 * depthA;
        const labelAlpha2 = 0.25 + 0.35 * depthB;
        ctx.font = '7px Roboto Mono, monospace';
        ctx.textAlign = 'center';
        ctx.textBaseline = 'middle';
        ctx.fillStyle = `rgba(8,145,178,${labelAlpha * 0.7})`;
        ctx.fillText(baseL, x1, y);
        ctx.fillStyle = `rgba(37,99,235,${labelAlpha2 * 0.7})`;
        ctx.fillText(baseR, x2, y);
      }
    }

    // Draw the two backbone strands (on top of rungs)
    for (let strand = 0; strand < 2; strand++) {
      const offset = strand * Math.PI;
      ctx.beginPath();
      for (let i = 0; i <= pairs * 4; i++) {
        const t = i / (pairs * 4);
        const y = topY + t * helixHeight;
        const angle = phase + t * pairs * 0.55 + offset;
        const x = cx + Math.sin(angle) * amplitude;
        const depth = (Math.cos(angle) + 1) / 2;
        if (i === 0) {
          ctx.moveTo(x, y);
        } else {
          ctx.lineTo(x, y);
        }
      }

      const strandColor = strand === 0 ? '8,145,178' : '37,99,235'; // cyan / blue
      // Draw glow pass
      ctx.strokeStyle = `rgba(${strandColor},0.15)`;
      ctx.lineWidth = 4;
      ctx.stroke();
      // Draw crisp pass
      ctx.strokeStyle = `rgba(${strandColor},0.8)`;
      ctx.lineWidth = 1.4;
      ctx.stroke();
    }

    // ── Scanning overlay line ──
    const scanPeriod = 4000; // ms for one down+up cycle
    const scanT = ((now % scanPeriod) / scanPeriod) * 2; // 0..2
    const scanY = scanT <= 1
      ? topY + scanT * helixHeight
      : topY + (2 - scanT) * helixHeight;

    const scanGrad = ctx.createLinearGradient(0, scanY - 6, 0, scanY + 6);
    scanGrad.addColorStop(0, 'rgba(8,145,178,0)');
    scanGrad.addColorStop(0.5, 'rgba(8,145,178,0.18)');
    scanGrad.addColorStop(1, 'rgba(8,145,178,0)');
    ctx.fillStyle = scanGrad;
    ctx.fillRect(0, scanY - 6, w, 12);

    ctx.beginPath();
    ctx.moveTo(0, scanY);
    ctx.lineTo(w, scanY);
    ctx.strokeStyle = 'rgba(8,145,178,0.35)';
    ctx.lineWidth = 0.7;
    ctx.stroke();

    // ── Progress text overlay ──
    const pct = Math.round(progressRef.current);
    ctx.font = '600 11px Roboto Mono, monospace';
    ctx.textAlign = 'right';
    ctx.textBaseline = 'top';
    ctx.fillStyle = 'rgba(9,36,38,0.55)';
    ctx.fillText(`${pct}%`, w - 10, 8);

    if (toolName) {
      ctx.font = '9px Roboto Mono, monospace';
      ctx.textAlign = 'left';
      ctx.textBaseline = 'top';
      ctx.fillStyle = 'rgba(9,36,38,0.35)';
      ctx.fillText(toolName, 10, 8);
    }

    frameRef.current = requestAnimationFrame(draw);
  }, []);

  useEffect(() => {
    frameRef.current = requestAnimationFrame(draw);
    return () => cancelAnimationFrame(frameRef.current);
  }, [draw]);

  return (
    <canvas
      ref={canvasRef}
      style={{
        width: '100%',
        height: 180,
        display: 'block',
        borderRadius: 'var(--e-radius-lg, 8px)',
        background: 'var(--e-bg-base, #FAFAFA)',
      }}
    />
  );
}