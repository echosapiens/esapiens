import { useEffect, useState } from 'react';

/**
 * CRT power-on flicker effect.
 * On first mount, the whole app does a brief CRT-style flicker.
 * Then a very subtle static noise overlay persists.
 */
export function CRTEffect() {
  const [flickering, setFlickering] = useState(true);
  const [staticNoise, setStaticNoise] = useState(true);

  useEffect(() => {
    // Power-on flicker — runs once on mount
    const flickerTimer = setTimeout(() => {
      setFlickering(false);
    }, 800);

    return () => clearTimeout(flickerTimer);
  }, []);

  // Generate random static pattern as data URI
  const [noiseStyle, setNoiseStyle] = useState('');

  useEffect(() => {
    // Create a small canvas with random noise pixels
    const noiseCanvas = document.createElement('canvas');
    noiseCanvas.width = 128;
    noiseCanvas.height = 128;
    const nctx = noiseCanvas.getContext('2d');
    if (!nctx) { setStaticNoise(false); return; }

    const imageData = nctx.createImageData(128, 128);
    for (let i = 0; i < imageData.data.length; i += 4) {
      const val = Math.random() * 255;
      imageData.data[i] = val;     // R
      imageData.data[i + 1] = val; // G
      imageData.data[i + 2] = val; // B
      imageData.data[i + 3] = 30;  // very low alpha
    }
    nctx.putImageData(imageData, 0, 0);
    setNoiseStyle(noiseCanvas.toDataURL());
  }, []);

  return (
    <>
      {/* Power-on flicker overlay */}
      {flickering && (
        <div
          className="e-crt-start"
          style={{
            position: 'fixed',
            inset: 0,
            zIndex: 10000,
            backgroundColor: '#07070B',
            pointerEvents: 'none',
          }}
        />
      )}

      {/* Subtle continuous static */}
      {staticNoise && noiseStyle && (
        <div
          style={{
            position: 'fixed',
            inset: 0,
            pointerEvents: 'none',
            zIndex: 9998,
            opacity: 0.06,
            backgroundImage: `url(${noiseStyle})`,
            backgroundRepeat: 'repeat',
            animation: 'static-noise 0.3s steps(3) infinite',
            mixBlendMode: 'overlay' as const,
          }}
        />
      )}
    </>
  );
}