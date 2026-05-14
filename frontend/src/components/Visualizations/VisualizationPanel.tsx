import { Paper, Title, Text } from '@mantine/core';
import type { VisualizationData } from '../../lib/api';
import { ImageViewer } from './ImageViewer';
import { PlotlyViewer } from './PlotlyViewer';
import { StructureViewer } from './StructureViewer';

interface VisualizationPanelProps {
  data: VisualizationData | null | undefined;
}

export function VisualizationPanel({ data }: VisualizationPanelProps) {
  if (!data) {
    return null;
  }

  const typeLabel = data.type === 'image' ? 'IMAGE_DATA' : data.type === 'plotly' ? 'PLOTLY_VIS' : 'STRUCTURE_VIEW';

  return (
    <div style={{ marginTop: 8 }}>
      {/* Terminal-style type label */}
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: 6,
          marginBottom: 4,
        }}
      >
        <div
          style={{
            width: 4,
            height: 4,
            backgroundColor: 'var(--e-accent-blue)',
            borderRadius: '50%',
          }}
        />
        <Text
          style={{
            fontFamily: "var(--e-font-mono)",
            fontSize: '0.5rem',
            fontWeight: 600,
            letterSpacing: '0.15em',
            textTransform: 'uppercase',
            color: 'var(--e-text-dimmed)',
          }}
        >
          {typeLabel}
        </Text>
      </div>

      <div
        style={{
          border: '1px solid var(--e-border)',
          borderLeft: '2px solid var(--e-accent-blue)',
          overflow: 'hidden',
        }}
      >
        {data.type === 'image' && <ImageViewer {...data} />}
        {data.type === 'plotly' && <PlotlyViewer {...data} />}
        {data.type === 'structure' && <StructureViewer {...data} />}
      </div>
    </div>
  );
}
