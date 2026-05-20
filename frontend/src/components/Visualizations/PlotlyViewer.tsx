import { useRef, useEffect, useState } from 'react';
import { Text, Center, Loader } from '@mantine/core';
import type { PlotlyVisualizationData } from '../../lib/api';

export function PlotlyViewer({ html, title }: PlotlyVisualizationData) {
  const containerRef = useRef<HTMLIFrameElement>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [isVisible, setIsVisible] = useState(false);

  // Intersection Observer to lazy-load the plot
  useEffect(() => {
    const observer = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting) {
          setIsVisible(true);
          observer.disconnect();
        }
      },
      { threshold: 0.1, rootMargin: '200px' }
    );

    if (containerRef.current) {
      observer.observe(containerRef.current);
    }

    return () => observer.disconnect();
  }, []);

  useEffect(() => {
    if (!html) {
      setError('NO HTML PROVIDED');
      setLoading(false);
      return;
    }

    // Only set srcdoc when visible to avoid crashing the tab on session load
    if (isVisible && containerRef.current) {
      try {
        const iframe = containerRef.current;
        // Optimization: only update if changed
        if (iframe.srcdoc !== html) {
          iframe.srcdoc = html;
        }
        setLoading(false);
      } catch (err: unknown) {
        const msg = err instanceof Error ? err.message : 'FAILED TO RENDER PLOTLY';
        setError(msg);
        setLoading(false);
      }
    }
  }, [html, isVisible]);

if (error) {
return (
<div style={{ padding: '8px 10px' }}>
{title && (
<Text
style={{
fontFamily: "var(--e-font-mono)",
fontSize: '0.65rem',
color: 'var(--e-text-secondary)',
marginBottom: 4,
}}
>
{title}
</Text>
)}
<Text
style={{
fontFamily: "var(--e-font-mono)",
fontSize: '0.6rem',
color: 'var(--e-accent-red)',
}}
>
✗ {error}
</Text>
</div>
);
}

return (
<div style={{ padding: '8px 10px' }}>
{title && (
<Text
style={{
fontFamily: "var(--e-font-mono)",
fontSize: '0.65rem',
color: 'var(--e-text-secondary)',
marginBottom: 4,
}}
>
{title}
</Text>
)}
<div style={{ position: 'relative', width: '100%', minHeight: 400 }}>
{loading && (
<Center style={{ position: 'absolute', inset: 0 }}>
<Loader size="sm" color="var(--e-accent-cyan)" />
</Center>
)}
<iframe
ref={containerRef}
title={title || 'Plotly Visualization'}
style={{
width: '100%',
height: '400px',
border: '1px solid var(--e-border)',
}}
sandbox="allow-scripts"
/>
</div>
</div>
);
}
