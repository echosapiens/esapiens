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

    const w = canvas.clientWidth;
    const h = canvas.clientHeight;

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

    // Scan speed based on tool name\n    const isModal = toolName?.toLowerCase().includes('modal');\n    const scanPeriod = isModal ? 1200 : 4000; // Fast scan for Modal, slow for normal\n    const scanT = ((now % scanPeriod) / scanPeriod) * 2; // 0..2\n    const scanY = scanT <= 1\n      ? topY + scanT * helixHeight\n      : topY + (2 - scanT) * helixHeight;\n\n    const scanColor = isModal ? '244,63,94' : '8,145,178'; // Rose-red for Modal, Cyan for normal\n\n    const scanGrad = ctx.createLinearGradient(0, scanY - 6, 0, scanY + 6);\n    scanGrad.addColorStop(0, `rgba(${scanColor},0)`);\n    scanGrad.addColorStop(0.5, `rgba(${scanColor},0.18)`);\n    scanGrad.addColorStop(1, `rgba(${scanColor},0)`);\n    ctx.fillStyle = scanGrad;\n    ctx.fillRect(0, scanY - 6, w, 12);\n\n    ctx.beginPath();\n    ctx.moveTo(0, scanY);\n    ctx.lineTo(w, scanY);\n    ctx.strokeStyle = `rgba(${scanColor},0.35)`;\n    ctx.lineWidth = 0.7;\n    ctx.stroke();\n\n    // ── Progress text overlay ──\n    const pct = Math.round(progressRef.current);\n    ctx.font = '600 11px Roboto Mono, monospace';\n    ctx.textAlign = 'right';\n    ctx.textBaseline = 'top';\n    ctx.fillStyle = 'rgba(9,36,38,0.55)';\n    ctx.fillText(`${pct}%`, w - 10, 8);\n\n    if (toolName) {\n      ctx.font = '700 9px Roboto Mono, monospace';\n      ctx.textAlign = 'left';\n      ctx.textBaseline = 'top';\n      ctx.fillStyle = isModal ? 'rgba(244,63,94,0.8)' : 'rgba(9,36,38,0.35)';\n      ctx.fillText(isModal ? `MODAL.COM • ${toolName.toUpperCase()}` : toolName, 10, 8);\n    }

    frameRef.current = requestAnimationFrame(draw);
  }, []);

  // Handle resizing outside the draw loop
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    const updateSize = () => {
      const dpr = window.devicePixelRatio || 1;
      const w = canvas.clientWidth;
      const h = canvas.clientHeight;
      if (canvas.width !== w * dpr || canvas.height !== h * dpr) {
        canvas.width = w * dpr;
        canvas.height = h * dpr;
        const ctx = canvas.getContext('2d');
        if (ctx) ctx.scale(dpr, dpr);
      }
    };

    updateSize();
    window.addEventListener('resize', updateSize);
    return () => window.removeEventListener('resize', updateSize);
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