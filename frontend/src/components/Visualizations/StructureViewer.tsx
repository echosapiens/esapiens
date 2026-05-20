import { useRef, useEffect, useState, useCallback } from 'react';
import { Text, Loader, Center, SegmentedControl, Button, Group } from '@mantine/core';
import type { StructureVisualizationData } from '../../lib/api';

type NGLModule = typeof import('ngl');

type RepresentationType = 'cartoon' | 'ball+stick' | 'surface' | 'licorice' | 'backbone' | 'spacefill';

const REPRESENTATIONS: { label: string; value: RepresentationType }[] = [
  { label: 'Cartoon', value: 'cartoon' },
  { label: 'Surface', value: 'surface' },
  { label: 'Ball+Stick', value: 'ball+stick' },
  { label: 'Licorice', value: 'licorice' },
  { label: 'Spacefill', value: 'spacefill' },
];

interface Preset {
  label: string;
  description: string;
  reps: { type: RepresentationType | string; params: Record<string, any> }[]; // eslint-disable-line @typescript-eslint/no-explicit-any
  selection?: string;
}

const PRESETS: Preset[] = [
  {
    label: 'Rainbow Cartoon',
    description: 'Secondary structure colored N-to-C (blue to red)',
    reps: [
      { type: 'cartoon', params: { colorScheme: 'residueindex' } },
    ],
  },
  {
    label: 'Surface + Cartoon',
    description: 'Translucent surface over cartoon backbone',
    reps: [
      { type: 'surface', params: { opacity: 0.5, colorScheme: 'chainname', smooth: 2 } },
      { type: 'cartoon', params: { colorScheme: 'chainname' } },
    ],
  },
  {
    label: 'Ligand Focus',
    description: 'Cartoon backbone with ligand highlighted in ball+stick',
    reps: [
      { type: 'cartoon', params: { colorScheme: 'chainname', opacity: 0.7 } },
      { type: 'ball+stick', params: { colorScheme: 'element', aspectRatio: 1.5, sele: 'ligand' } },
    ],
  },
  {
    label: 'Electrostatic',
    description: 'Surface colored by electrostatic potential (red acidic, blue basic)',
    reps: [
      { type: 'surface', params: { colorScheme: 'electrostatic', smooth: 2 } },
    ],
  },
];

const VIEWER_WIDTH = 560;
const VIEWER_HEIGHT = 420;

export function StructureViewer({ pdb_id, pdb_file, title, representation: initialRepresentation }: StructureVisualizationData) {
  const containerRef = useRef<HTMLDivElement>(null);
  const stageRef = useRef<unknown>(null);
  const componentRef = useRef<unknown>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [activeRep, setActiveRep] = useState<RepresentationType>(initialRepresentation || 'cartoon');
  const [activePreset, setActivePreset] = useState<string | null>(null);
  const [isVisible, setIsVisible] = useState(false);

  // Intersection Observer for lazy loading
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

  const applyReps = useCallback((reps: { type: string; params: Record<string, any> }[]) => { // eslint-disable-line @typescript-eslint/no-explicit-any
    const comp = componentRef.current as any; // eslint-disable-line @typescript-eslint/no-explicit-any
    if (!comp) return;
    comp.removeAllRepresentations();
    for (const rep of reps) {
      const { sele, ...params } = rep.params;
      if (sele) {
        comp.addRepresentation(rep.type, params).setSelection(sele);
      } else {
        comp.addRepresentation(rep.type, params);
      }
    }
    // Refit after changing representation
    (comp as { autoView: (duration?: number) => void }).autoView(200);
  }, []);

  // Switch single representation without reloading
  const switchRepresentation = useCallback((rep: RepresentationType) => {
    const params: Record<string, any> = {}; // eslint-disable-line @typescript-eslint/no-explicit-any

    if (rep === 'surface') {
      params.opacity = 0.85;
      params.colorScheme = 'chainname';
      params.smooth = 2;
    } else if (rep === 'cartoon') {
      params.colorScheme = 'chainname';
    } else if (rep === 'ball+stick') {
      params.colorScheme = 'element';
      params.aspectRatio = 1.5;
    } else if (rep === 'licorice') {
      params.colorScheme = 'element';
    } else if (rep === 'spacefill') {
      params.colorScheme = 'element';
      params.radiusScale = 1.0;
    }

    applyReps([{ type: rep, params }]);
    setActiveRep(rep);
    setActivePreset(null);
  }, [applyReps]);

  // Apply a preset
  const applyPreset = useCallback((preset: Preset) => {
    applyReps(preset.reps);
    setActivePreset(preset.label);
    setActiveRep(preset.reps[0].type as RepresentationType);
  }, [applyReps]);

  useEffect(() => {
    let mounted = true;

    async function init() {
      if (!containerRef.current || !isVisible) return;

      try {
        const NGL = await import('ngl') as unknown as NGLModule;
        if (!mounted || !containerRef.current) return;

        // eslint-disable-next-line @typescript-eslint/no-unsafe-call, @typescript-eslint/no-unsafe-assignment, new-cap
        const stage = new NGL.Stage(containerRef.current, {
          backgroundColor: '#0d0d12',
          impostor: true,
        });
        stageRef.current = stage;

        const pdbString = pdb_id || pdb_file;
        if (!pdbString) {
          setError('No PDB data provided');
          setLoading(false);
          return;
        }

        const loadUrl = pdb_id ? `rcsb://${pdb_id}` : undefined;
        const loadData = pdb_file ? pdb_file : undefined;

        const loadPromise = loadUrl
          ? stage.loadFile(loadUrl, { defaultRepresentation: false })
          : loadData
          ? stage.loadFile(new Blob([loadData], { type: 'text/plain' }), { defaultRepresentation: false, ext: 'pdb' })
          : Promise.reject(new Error('No PDB data provided'));

        loadPromise.then((comp: unknown) => {
          if (!mounted) return;
          componentRef.current = comp;

          const startRep = initialRepresentation || 'cartoon';
          const params: Record<string, any> = {}; // eslint-disable-line @typescript-eslint/no-explicit-any

          if (startRep === 'surface') {
            params.opacity = 0.85;
            params.colorScheme = 'chainname';
            params.smooth = 2;
          } else if (startRep === 'cartoon') {
            params.colorScheme = 'chainname';
          } else if (startRep === 'ball+stick') {
            params.colorScheme = 'element';
            params.aspectRatio = 1.5;
          } else if (startRep === 'spacefill') {
            params.colorScheme = 'element';
            params.radiusScale = 1.0;
          }

          // eslint-disable-next-line @typescript-eslint/no-unsafe-call, @typescript-eslint/no-unsafe-member-access
          (comp as any).addRepresentation(startRep, params); // eslint-disable-line @typescript-eslint/no-explicit-any
          // eslint-disable-next-line @typescript-eslint/no-unsafe-call
          (comp as { autoView: (duration?: number) => void }).autoView(500);
          setLoading(false);
        }).catch((err: Error) => {
          if (!mounted) return;
          setError(`Load failed: ${err.message}`);
          setLoading(false);
        });
      } catch (err: unknown) {
        if (!mounted) return;
        const msg = err instanceof Error ? err.message : 'NGL load failed';
        setError(msg);
        setLoading(false);
      }
    }

    void init();

    // Handle NGL stage resize on window resize
    function handleResize() {
      const stage = stageRef.current as any; // eslint-disable-line @typescript-eslint/no-explicit-any
      if (stage) {
        try {
          stage.handleResize();
        } catch {
          // ignore resize errors on disposed stage
        }
      }
    }
    window.addEventListener('resize', handleResize);

    return () => {
      mounted = false;
      window.removeEventListener('resize', handleResize);
      if (stageRef.current) {
        try {
          // eslint-disable-next-line @typescript-eslint/no-unsafe-call, @typescript-eslint/no-unsafe-member-access
          (stageRef.current as { dispose: () => void }).dispose();
        } catch {
          // ignore dispose errors
        }
        stageRef.current = null;
        componentRef.current = null;
      }
    };
  }, [pdb_id, pdb_file, initialRepresentation, isVisible]);

  if (error) {
    return (
      <div style={{ padding: '8px 10px' }}>
        {title && (
          <Text
            style={{
              fontFamily: 'var(--e-font-sans)',
              fontSize: 'var(--e-type-sm)',
              color: 'var(--e-text-secondary)',
              marginBottom: 4,
            }}
          >
            {title}
          </Text>
        )}
        <Text
          style={{
            fontFamily: 'var(--e-font-sans)',
            fontSize: 'var(--e-type-xs)',
            color: 'var(--e-error)',
          }}
        >
          {error}
        </Text>
      </div>
    );
  }

  return (
    <div style={{ padding: '0' }}>
      {title && (
        <Text
          style={{
            fontFamily: 'var(--e-font-sans)',
            fontSize: 'var(--e-type-sm)',
            color: 'var(--e-text-secondary)',
            padding: '8px 10px 0',
            marginBottom: 4,
          }}
        >
          {title}
        </Text>
      )}
      {/* Controls bar: representation + presets */}
      <div style={{ padding: '4px 10px 6px', display: 'flex', flexDirection: 'column', gap: 6 }}>
        <SegmentedControl
          size="xs"
          value={activeRep}
          onChange={(val) => switchRepresentation(val as RepresentationType)}
          data={REPRESENTATIONS}
        />
        <Group gap={6} wrap="wrap">
          {PRESETS.map((preset) => (
            <Button
              key={preset.label}
              size="compact-xs"
              variant={activePreset === preset.label ? 'filled' : 'light'}
              color={activePreset === preset.label ? '#092426' : 'gray'}
              radius="sm"
              onClick={() => applyPreset(preset)}
              title={preset.description}
              styles={{
                root: { fontFamily: 'var(--e-font-sans)', fontSize: 'var(--e-type-xs)' },
              }}
            >
              {preset.label}
            </Button>
          ))}
        </Group>
      </div>
      {/* NGL viewport — defined size, centered */}
      <div style={{ display: 'flex', justifyContent: 'center' }}>
        <div
          ref={containerRef}
          style={{
            width: VIEWER_WIDTH,
            height: VIEWER_HEIGHT,
            maxWidth: '100%',
            overflow: 'hidden',
            position: 'relative',
            backgroundColor: '#0d0d12',
            borderRadius: 4,
          }}
        >
          {loading && (
            <Center style={{ position: 'absolute', inset: 0 }}>
              <Loader size="sm" />
            </Center>
          )}
        </div>
      </div>
      {pdb_id && (
        <Text
          style={{
            fontFamily: 'var(--e-font-mono)',
            fontSize: 'var(--e-type-xs)',
            color: 'var(--e-text-muted)',
            padding: '4px 10px 8px',
          }}
        >
          PDB: {pdb_id}
        </Text>
      )}
    </div>
  );
}