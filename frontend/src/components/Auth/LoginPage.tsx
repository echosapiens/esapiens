/**
 * LoginPage.tsx — Authentication page for E.sapiens v2
 *
 * Premium SaaS-grade login (Linear/Vercel/Stripe aesthetic).
 * - Glassmorphism card with backdrop-blur on mesh gradient background
 * - Molecular wireframe SVG shapes floating with sine drift
 * - Inline email validation, password visibility toggle, Remember Me
 * - OAuth slot (Google), "Forgot password?" link
 * - Fully responsive, touch-friendly 48px targets
 * - No glow/halos — line-only strokes, never looping
 */

import { useState, useCallback, useEffect, useRef } from 'react';
import {
  TextInput,
  PasswordInput,
  Button,
  Checkbox,
  Divider,
  Alert,
  LoadingOverlay,
} from '@mantine/core';
import { IconEye, IconEyeOff, IconBrandGoogle } from '@tabler/icons-react';
import { useAuth } from '../../lib/auth';

/* ─── Inline Email Validation ─── */
function validateEmail(email: string): string | null {
  if (!email) return null;
  const re = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
  if (!re.test(email)) return 'Please enter a valid email address';
  return null;
}

/* ─── Molecular wireframe background (Canvas) ─── */
interface Mote {
  x: number;
  y: number;
  vx: number;
  vy: number;
  rotation: number;
  rotationSpeed: number;
  type: 'orbital' | 'benzene' | 'doubleBond' | 'helix' | 'lattice' | 'ring';
  scale: number;
  stroke: string;
  strokeW: number;
  driftPhase: number;
  driftSpeed: number;
  driftAmpX: number;
  driftAmpY: number;
}

const STROKES = [
  'rgba(9, 36, 38, 0.06)',
  'rgba(9, 36, 38, 0.04)',
  'rgba(9, 36, 38, 0.08)',
  'rgba(9, 36, 38, 0.05)',
  'rgba(82, 82, 82, 0.05)',
  'rgba(82, 82, 82, 0.03)',
];

const TYPES: Mote['type'][] = ['orbital', 'benzene', 'doubleBond', 'helix', 'lattice', 'ring'];

function MolecularBackground() {
  const ref = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const c = ref.current;
    if (!c) return;
    const ctx = c.getContext('2d');
    if (!ctx) return;

    let animId: number;
    const motes: Mote[] = [];
    const N = 16;

    const resize = () => { c.width = window.innerWidth; c.height = window.innerHeight; };
    resize();
    window.addEventListener('resize', resize);

    for (let i = 0; i < N; i++) {
      motes.push({
        x: Math.random() * c.width,
        y: Math.random() * c.height,
        vx: (Math.random() - 0.5) * 0.04,
        vy: (Math.random() - 0.5) * 0.03,
        rotation: Math.random() * Math.PI * 2,
        rotationSpeed: (Math.random() - 0.5) * 0.0008,
        type: TYPES[Math.floor(Math.random() * TYPES.length)],
        scale: Math.random() * 35 + 20,
        stroke: STROKES[Math.floor(Math.random() * STROKES.length)],
        strokeW: Math.random() * 0.6 + 0.4,
        driftPhase: Math.random() * Math.PI * 2,
        driftSpeed: Math.random() * 0.001 + 0.0004,
        driftAmpX: Math.random() * 0.2 + 0.05,
        driftAmpY: Math.random() * 0.15 + 0.04,
      });
    }

    let t = 0;

    const drawMote = (m: Mote) => {
      ctx.save();
      ctx.translate(m.x, m.y);
      ctx.rotate(m.rotation);
      ctx.strokeStyle = m.stroke;
      ctx.lineWidth = m.strokeW;
      ctx.lineCap = 'round';
      ctx.lineJoin = 'round';
      const s = m.scale;

      switch (m.type) {
        case 'orbital': {
          ctx.beginPath(); ctx.arc(0, 0, s * 0.05, 0, Math.PI * 2);
          ctx.fillStyle = m.stroke; ctx.fill();
          for (let i = 0; i < 3; i++) {
            ctx.save(); ctx.rotate((i * Math.PI) / 3);
            ctx.beginPath(); ctx.ellipse(0, 0, s, s * 0.32, 0, 0, Math.PI * 2); ctx.stroke();
            ctx.restore();
          }
          break;
        }
        case 'benzene': {
          ctx.beginPath();
          for (let i = 0; i < 6; i++) {
            const a = (Math.PI / 3) * i - Math.PI / 6;
            const px = Math.cos(a) * s; const py = Math.sin(a) * s;
            i === 0 ? ctx.moveTo(px, py) : ctx.lineTo(px, py);
          }
          ctx.closePath(); ctx.stroke();
          ctx.beginPath(); ctx.arc(0, 0, s * 0.52, 0, Math.PI * 2); ctx.stroke();
          break;
        }
        case 'doubleBond': {
          const len = s * 2; const gap = s * 0.12;
          ctx.beginPath();
          ctx.moveTo(-len / 2, -gap); ctx.lineTo(len / 2, -gap);
          ctx.moveTo(-len / 2, gap); ctx.lineTo(len / 2, gap);
          ctx.stroke();
          for (const nx of [-len / 2, len / 2]) {
            ctx.beginPath(); ctx.arc(nx, 0, s * 0.06, 0, Math.PI * 2);
            ctx.fillStyle = m.stroke; ctx.fill();
          }
          break;
        }
        case 'helix': {
          const h = s * 2.8; const amp = s * 0.55; const rungs = 4;
          for (const offset of [0, Math.PI]) {
            ctx.beginPath();
            for (let i = 0; i <= 36; i++) {
              const frac = i / 36;
              const py = -h / 2 + frac * h;
              const px = Math.sin(frac * Math.PI * 2 + offset) * amp;
              i === 0 ? ctx.moveTo(px, py) : ctx.lineTo(px, py);
            }
            ctx.stroke();
          }
          for (let i = 0; i < rungs; i++) {
            const frac = (i + 0.5) / rungs;
            const py = -h / 2 + frac * h;
            const px1 = Math.sin(frac * Math.PI * 2) * amp;
            const px2 = Math.sin(frac * Math.PI * 2 + Math.PI) * amp;
            ctx.beginPath(); ctx.moveTo(px1, py); ctx.lineTo(px2, py); ctx.stroke();
          }
          break;
        }
        case 'lattice': {
          const cols = 3; const rows = 3;
          const dx = s * 0.5; const dy = s * 0.55;
          for (let r = 0; r < rows; r++) {
            for (let c = 0; c < cols; c++) {
              const nx = -dx + c * dx + (r % 2 ? dx * 0.5 : 0);
              const ny = -dy + r * dy;
              if (c < cols - 1) {
                const nx2 = nx + dx;
                ctx.beginPath(); ctx.moveTo(nx, ny); ctx.lineTo(nx2, ny); ctx.stroke();
              }
              if (r < rows - 1) {
                const nny = ny + dy;
                const nnx = nx + (r % 2 === 0 ? dx * 0.5 : -dx * 0.5);
                ctx.beginPath(); ctx.moveTo(nx, ny); ctx.lineTo(nnx, nny); ctx.stroke();
              }
              ctx.beginPath(); ctx.arc(nx, ny, s * 0.04, 0, Math.PI * 2);
              ctx.fillStyle = m.stroke; ctx.fill();
            }
          }
          break;
        }
        case 'ring': {
          ctx.beginPath(); ctx.arc(0, 0, s, 0, Math.PI * 2); ctx.stroke();
          ctx.beginPath(); ctx.arc(0, 0, s * 0.85, 0, Math.PI * 2); ctx.stroke();
          break;
        }
      }
      ctx.restore();
    };

    const draw = () => {
      const w = c.width; const h = c.height;
      ctx.clearRect(0, 0, w, h);

      // Mesh gradient: three overlapping radial blobs
      const g1 = ctx.createRadialGradient(w * 0.25, h * 0.2, 0, w * 0.25, h * 0.2, w * 0.6);
      g1.addColorStop(0, 'rgba(9, 36, 38, 0.03)');
      g1.addColorStop(1, 'rgba(9, 36, 38, 0)');
      ctx.fillStyle = g1; ctx.fillRect(0, 0, w, h);

      const g2 = ctx.createRadialGradient(w * 0.75, h * 0.7, 0, w * 0.75, h * 0.7, w * 0.5);
      g2.addColorStop(0, 'rgba(82, 82, 82, 0.025)');
      g2.addColorStop(1, 'rgba(82, 82, 82, 0)');
      ctx.fillStyle = g2; ctx.fillRect(0, 0, w, h);

      const g3 = ctx.createRadialGradient(w * 0.5, h * 0.5, 0, w * 0.5, h * 0.5, w * 0.4);
      g3.addColorStop(0, 'rgba(245, 245, 245, 0.5)');
      g3.addColorStop(1, 'rgba(250, 250, 250, 0)');
      ctx.fillStyle = g3; ctx.fillRect(0, 0, w, h);

      // Ultra-faint grid
      ctx.strokeStyle = 'rgba(0, 0, 0, 0.018)';
      ctx.lineWidth = 0.5;
      const grid = 80;
      for (let x = 0; x < w; x += grid) { ctx.beginPath(); ctx.moveTo(x, 0); ctx.lineTo(x, h); ctx.stroke(); }
      for (let y = 0; y < h; y += grid) { ctx.beginPath(); ctx.moveTo(0, y); ctx.lineTo(w, y); ctx.stroke(); }

      for (const m of motes) {
        m.driftPhase += m.driftSpeed;
        m.x += m.vx + Math.sin(m.driftPhase) * m.driftAmpX * 0.02;
        m.y += m.vy + Math.cos(m.driftPhase * 0.7) * m.driftAmpY * 0.02;
        m.rotation += m.rotationSpeed;
        const margin = 120;
        if (m.x < -margin) m.x = w + margin;
        if (m.x > w + margin) m.x = -margin;
        if (m.y < -margin) m.y = h + margin;
        if (m.y > h + margin) m.y = -margin;
        drawMote(m);
      }

      t += 0.016;
      animId = requestAnimationFrame(draw);
    };

    draw();
    return () => { window.removeEventListener('resize', resize); cancelAnimationFrame(animId); };
  }, []);

  return <canvas ref={ref} style={{ position: 'fixed', inset: 0, width: '100%', height: '100%', zIndex: 0 }} />;
}

/* ─── Shared Input Styles ─── */
const inputStyles = {
  label: {
    fontFamily: 'var(--e-font-sans)',
    fontSize: '0.8125rem',
    fontWeight: 500 as const,
    color: '#525252',
    marginBottom: '6px',
    letterSpacing: '0.01em',
  },
  input: {
    fontFamily: 'var(--e-font-sans)',
    fontSize: '0.9375rem',
    backgroundColor: '#FAFAFA',
    border: '1px solid #E5E5E5',
    borderRadius: '8px',
    color: '#092426',
    padding: '12px 14px',
    height: '48px',
    transition: 'border-color 0.2s ease, box-shadow 0.2s ease, background-color 0.2s ease',
    '&:focus': {
      borderColor: '#092426',
      boxShadow: '0 0 0 3px rgba(9, 36, 38, 0.08)',
      backgroundColor: '#FFFFFF',
    },
    '&::placeholder': {
      color: '#A3A3A3',
    },
  },
  error: {
    fontFamily: 'var(--e-font-sans)',
    fontSize: '0.75rem',
    color: '#DC2626',
    marginTop: '4px',
  },
};

const passwordInputStyles = {
  ...inputStyles,
  innerInput: {
    fontFamily: 'var(--e-font-sans)',
    fontSize: '0.9375rem',
    color: '#092426',
    padding: '12px 14px',
  },
  visibilityToggle: {
    color: '#A3A3A3',
    transition: 'color 0.2s ease',
    '&:hover': {
      color: '#525252',
    },
  },
};

/* ─── Login Page ─── */

export function LoginPage() {
  const { login, register, loading: authLoading } = useAuth();

  const [activeTab, setActiveTab] = useState<'signin' | 'register'>('signin');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [fullName, setFullName] = useState('');
  const [rememberMe, setRememberMe] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const emailError = validateEmail(email);

  const handleSubmit = useCallback(
    async (e: React.FormEvent) => {
      e.preventDefault();
      if (emailError) return;
      setError(null);
      setSubmitting(true);

      try {
        if (activeTab === 'signin') {
          await login(email, password);
        } else {
          await register(email!, password, fullName || undefined);
        }
      } catch (err: unknown) {
        const message = err instanceof Error ? err.message : 'An unexpected error occurred';
        if (message.includes('401') || message.includes('Unauthorized')) {
          setError('Invalid email or password.');
        } else if (message.includes('409') || message.includes('Conflict') || message.includes('already')) {
          setError('An account with this email already exists.');
        } else {
          setError(message);
        }
      } finally {
        setSubmitting(false);
      }
    },
    [activeTab, email, password, fullName, emailError, login, register],
  );

  const isSignIn = activeTab === 'signin';

  return (
    <div
      style={{
        width: '100vw',
        height: '100dvh',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        position: 'relative',
        overflow: 'hidden',
        backgroundColor: '#FAFAFA',
      }}
    >
      <MolecularBackground />

      {/* Glass card */}
      <div
        style={{
          width: '100%',
          maxWidth: 420,
          padding: '44px 40px 36px',
          position: 'relative',
          backgroundColor: 'rgba(255, 255, 255, 0.82)',
          backdropFilter: 'blur(24px) saturate(1.2)',
          WebkitBackdropFilter: 'blur(24px) saturate(1.2)',
          borderRadius: '16px',
          border: '1px solid rgba(229, 229, 229, 0.6)',
          boxShadow:
            '0 0 0 1px rgba(255, 255, 255, 0.5), 0 1px 3px rgba(0, 0, 0, 0.04), 0 8px 32px rgba(0, 0, 0, 0.06)',
          zIndex: 2,
        }}
      >
        <LoadingOverlay visible={authLoading} />

        {/* ─── Branding ─── */}
        <div style={{ textAlign: 'center', marginBottom: '32px' }}>
          <h1
            style={{
              fontFamily: 'var(--e-font-display)',
              fontSize: '1.75rem',
              fontWeight: 700,
              fontStyle: 'italic',
              color: '#092426',
              letterSpacing: '-0.03em',
              lineHeight: 1,
              margin: 0,
            }}
          >
            E<span style={{ color: '#525252' }}>.</span>sapiens
          </h1>
          <p
            style={{
              fontFamily: 'var(--e-font-sans)',
              fontSize: '0.8125rem',
              color: '#A3A3A3',
              letterSpacing: '0.08em',
              textTransform: 'uppercase',
              fontWeight: 500,
              margin: '8px 0 0',
            }}
          >
            Computational Biology Platform
          </p>
        </div>

        {/* ─── Tab Switch ─── */}
        <div
          style={{
            display: 'flex',
            backgroundColor: '#F5F5F5',
            borderRadius: '8px',
            padding: '3px',
            marginBottom: '28px',
          }}
        >
          {(['signin', 'register'] as const).map((tab) => (
            <button
              key={tab}
              onClick={() => setActiveTab(tab)}
              style={{
                flex: 1,
                padding: '10px 0',
                fontFamily: 'var(--e-font-sans)',
                fontSize: '0.8125rem',
                fontWeight: activeTab === tab ? 600 : 500,
                color: activeTab === tab ? '#092426' : '#737373',
                backgroundColor: activeTab === tab ? '#FFFFFF' : 'transparent',
                border: 'none',
                borderRadius: '6px',
                cursor: 'pointer',
                transition: 'all 0.2s ease',
                boxShadow: activeTab === tab ? '0 1px 3px rgba(0, 0, 0, 0.06)' : 'none',
                letterSpacing: '0.01em',
              }}
            >
              {tab === 'signin' ? 'Sign in' : 'Create account'}
            </button>
          ))}
        </div>

        {/* ─── Error ─── */}
        {error && (
          <Alert
            color="red"
            variant="light"
            radius="md"
            mb="md"
            styles={{
              root: {
                backgroundColor: '#FEF2F2',
                border: '1px solid #FECACA',
                borderRadius: '8px',
              },
              label: { fontFamily: 'var(--e-font-sans)', fontWeight: 600, color: '#991B1B', fontSize: '0.8125rem' },
              body: { fontFamily: 'var(--e-font-sans)', fontSize: '0.8125rem', color: '#991B1B' },
            }}
          >
            {error}
          </Alert>
        )}

        {/* ─── Form ─── */}
        <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
          {!isSignIn && (
            <TextInput
              label="Full name"
              placeholder="Jane Doe"
              value={fullName}
              onChange={(e) => setFullName(e.currentTarget.value)}
              styles={inputStyles}
            />
          )}

          <TextInput
            label="Email"
            placeholder="you@institution.edu"
            type="email"
            required
            value={email}
            onChange={(e) => setEmail(e.currentTarget.value)}
            error={email && emailError ? emailError : undefined}
            styles={{
              ...inputStyles,
              input: {
                ...inputStyles.input,
                ...(email && emailError ? {
                  borderColor: '#FCA5A5',
                  '&:focus': {
                    borderColor: '#DC2626',
                    boxShadow: '0 0 0 3px rgba(220, 38, 38, 0.08)',
                  },
                } : {}),
              },
            }}
          />

          <PasswordInput
            label="Password"
            placeholder="Your password"
            required
            value={password}
            onChange={(e) => setPassword(e.currentTarget.value)}
            styles={passwordInputStyles}
            visibilityToggleIcon={({ reveal }) =>
              reveal ? <IconEyeOff size={18} stroke={1.5} /> : <IconEye size={18} stroke={1.5} />
            }
          />

          {/* ─── Remember Me / Forgot Password ─── */}
          {isSignIn && (
            <div
              style={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'space-between',
                marginTop: '-4px',
              }}
            >
              <Checkbox
                label="Remember me"
                checked={rememberMe}
                onChange={(e) => setRememberMe(e.currentTarget.checked)}
                size="sm"
                styles={{
                  root: { cursor: 'pointer' },
                  label: {
                    fontFamily: 'var(--e-font-sans)',
                    fontSize: '0.8125rem',
                    color: '#737373',
                    cursor: 'pointer',
                  },
                  input: {
                    cursor: 'pointer',
                    borderColor: '#D4D4D4',
                    transition: 'all 0.2s ease',
                    '&:checked': {
                      backgroundColor: '#092426',
                      borderColor: '#092426',
                    },
                  },
                }}
              />
              <a
                href="#"
                onClick={(e) => e.preventDefault()}
                style={{
                  fontFamily: 'var(--e-font-sans)',
                  fontSize: '0.8125rem',
                  color: '#525252',
                  textDecoration: 'none',
                  fontWeight: 500,
                  transition: 'color 0.2s ease',
                  cursor: 'pointer',
                }}
                onMouseEnter={(e) => (e.currentTarget.style.color = '#092426')}
                onMouseLeave={(e) => (e.currentTarget.style.color = '#525252')}
              >
                Forgot password?
              </a>
            </div>
          )}

          <button
            type="submit"
            disabled={submitting || !!emailError}
            style={{
              fontFamily: 'var(--e-font-sans)',
              fontSize: '0.9375rem',
              fontWeight: 600,
              height: '48px',
              borderRadius: '8px',
              backgroundColor: submitting ? '#525252' : '#092426',
              color: '#FFFFFF',
              border: 'none',
              cursor: submitting ? 'not-allowed' : 'pointer',
              transition: 'all 0.2s ease',
              letterSpacing: '0.01em',
              marginTop: '4px',
              opacity: submitting ? 0.7 : 1,
            }}
            onMouseEnter={(e) => {
              if (!submitting) e.currentTarget.style.backgroundColor = '#1a3a3c';
            }}
            onMouseLeave={(e) => {
              if (!submitting) e.currentTarget.style.backgroundColor = '#092426';
            }}
            onMouseDown={(e) => {
              if (!submitting) e.currentTarget.style.transform = 'translateY(1px)';
            }}
            onMouseUp={(e) => {
              e.currentTarget.style.transform = 'translateY(0)';
            }}
          >
            {submitting ? 'Signing in…' : isSignIn ? 'Sign in' : 'Create account'}
          </button>
        </form>

        {/* ─── Divider ─── */}
        <div
          style={{
            display: 'flex',
            alignItems: 'center',
            gap: '12px',
            margin: '24px 0',
          }}
        >
          <div style={{ flex: 1, height: '1px', backgroundColor: '#E5E5E5' }} />
          <span
            style={{
              fontFamily: 'var(--e-font-sans)',
              fontSize: '0.75rem',
              color: '#A3A3A3',
              fontWeight: 500,
              letterSpacing: '0.04em',
              textTransform: 'uppercase',
            }}
          >
            Or continue with
          </span>
          <div style={{ flex: 1, height: '1px', backgroundColor: '#E5E5E5' }} />
        </div>

        {/* ─── OAuth Slot ─── */}
        <button
          type="button"
          style={{
            width: '100%',
            height: '48px',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            gap: '10px',
            fontFamily: 'var(--e-font-sans)',
            fontSize: '0.875rem',
            fontWeight: 500,
            color: '#525252',
            backgroundColor: '#FFFFFF',
            border: '1px solid #E5E5E5',
            borderRadius: '8px',
            cursor: 'pointer',
            transition: 'all 0.2s ease',
          }}
          onMouseEnter={(e) => {
            e.currentTarget.style.backgroundColor = '#F5F5F5';
            e.currentTarget.style.borderColor = '#D4D4D4';
          }}
          onMouseLeave={(e) => {
            e.currentTarget.style.backgroundColor = '#FFFFFF';
            e.currentTarget.style.borderColor = '#E5E5E5';
          }}
        >
          <IconBrandGoogle size={18} stroke={1.5} />
          Google
        </button>

        {/* ─── Footer ─── */}
        <p
          style={{
            textAlign: 'center',
            fontFamily: 'var(--e-font-sans)',
            fontSize: '0.8125rem',
            color: '#A3A3A3',
            marginTop: '24px',
            marginBottom: 0,
          }}
        >
          {isSignIn ? "Don't have an account? " : 'Already have an account? '}
          <span
            style={{
              color: '#092426',
              cursor: 'pointer',
              fontWeight: 600,
              transition: 'opacity 0.2s ease',
            }}
            onClick={() => setActiveTab(isSignIn ? 'register' : 'signin')}
            onMouseEnter={(e) => (e.currentTarget.style.opacity = '0.7')}
            onMouseLeave={(e) => (e.currentTarget.style.opacity = '1')}
          >
            {isSignIn ? 'Create account' : 'Sign in'}
          </span>
        </p>
      </div>
    </div>
  );
}