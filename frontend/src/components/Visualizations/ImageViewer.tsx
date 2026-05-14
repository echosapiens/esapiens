import { Paper, Image, Text } from '@mantine/core';
import type { ImageVisualizationData } from '../../lib/api';

export function ImageViewer({ image, format, title }: ImageVisualizationData) {
  if (!image) return null;

  // Handle both raw base64 and already-prefixed data URIs
  let dataUri: string;
  if (image.startsWith('data:')) {
    dataUri = image;
  } else {
    const mimeType = format
      ? `image/${format}`
      : image.startsWith('/9j/')
        ? 'image/jpeg'
        : image.startsWith('iVBOR')
          ? 'image/png'
          : image.startsWith('R0lGOD')
            ? 'image/gif'
            : image.startsWith('PD94bWwg') || image.startsWith('PHN2Zy')
              ? 'image/svg+xml'
              : 'image/png';
    dataUri = `data:${mimeType};base64,${image}`;
  }

  return (
    <div style={{ padding: '8px 10px' }}>
      {title && (
        <Text
          style={{
            fontFamily: "var(--e-font-mono)",
            fontSize: '0.65rem',
            color: 'var(--e-text-secondary)',
            marginBottom: 6,
          }}
        >
          {title}
        </Text>
      )}
      <div style={{ maxWidth: '100%', overflow: 'auto' }}>
        <Image
          src={dataUri}
          alt={title ?? 'Visualization'}
          style={{ maxWidth: '100%', height: 'auto' }}
          fit="contain"
          fallbackSrc="data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='200' height='100'%3E%3Crect width='200' height='100' fill='%2312121E'/%3E%3Ctext x='100' y='55' text-anchor='middle' fill='%23555570' font-size='10' font-family='monospace'%3ENO DATA%3C/text%3E%3C/svg%3E"
        />
      </div>
    </div>
  );
}
