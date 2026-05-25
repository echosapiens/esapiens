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

import { useState, useCallback } from 'react';
import {
  TextInput,
  PasswordInput,
  Checkbox,
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
    color: '#2563EB',
    padding: '12px 14px',
    height: '48px',
    transition: 'border-color 0.2s ease, box-shadow 0.2s ease, background-color 0.2s ease',
    '&:focus': {
      borderColor: '#2563EB',
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
    color: '#2563EB',
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
      {/* Background image */}
      <div
        className="e-login-backdrop"
        style={{
          position: 'fixed',
          inset: 0,
          zIndex: 0,
          backgroundImage: "url('/login-background.webp')",
          backgroundSize: 'cover',
          backgroundPosition: 'center',
          backgroundRepeat: 'no-repeat',
        }}
      />
      {/* Dark overlay for readability */}
      <div
        className="e-login-overlay"
        style={{
          position: 'fixed',
          inset: 0,
          zIndex: 1,
          backgroundColor: 'rgba(250, 250, 250, 0.45)',
        }}
      />

      {/* Glass card */}
      <div
        className="e-login-card"
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
              color: '#2563EB',
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
                color: activeTab === tab ? '#2563EB' : '#737373',
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
                      backgroundColor: '#2563EB',
                      borderColor: '#2563EB',
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
                onMouseEnter={(e) => (e.currentTarget.style.color = '#2563EB')}
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
              backgroundColor: submitting ? '#525252' : '#2563EB',
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
              if (!submitting) e.currentTarget.style.backgroundColor = '#2563EB';
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
              color: '#2563EB',
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