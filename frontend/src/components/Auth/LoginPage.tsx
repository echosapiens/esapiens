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
 * - Now compliant with 8pt grid and 4pt internal spacing, typography multiples of 4px
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
    fontSize: 'var(--e-type-sm)', /* 16px */
    fontWeight: 500 as const,
    color: 'var(--e-text-secondary)',
    marginBottom: 'var(--e-space-2)', /* 8px */
    letterSpacing: '0.01em',
  },
  input: {
    fontFamily: 'var(--e-font-sans)',
    fontSize: 'var(--e-type-base)', /* 20px */
    backgroundColor: 'var(--e-bg-surface)',
    border: '1px solid var(--e-border)',
    borderRadius: 'var(--e-radius-lg)',
    color: 'var(--e-text-primary)',
    padding: 'var(--e-space-4) var(--e-space-4)', /* 16px 16px */
    height: '48px', /* touch target */
    transition: 'border-color 0.2s ease, box-shadow 0.2s ease, background-color 0.2s ease',
    '&:focus': {
      borderColor: 'var(--e-brand)',
      boxShadow: '0 0 0 3px rgba(79, 70, 229, 0.1)',
      backgroundColor: 'var(--e-bg-surface)',
    },
    '&::placeholder': {
      color: 'var(--e-text-muted)',
    },
  },
  error: {
    fontFamily: 'var(--e-font-sans)',
    fontSize: 'var(--e-type-xs)', /* 12px */
    color: 'var(--e-error)',
    marginTop: 'var(--e-space-1)', /* 4px */
  },
};

const passwordInputStyles = {
  ...inputStyles,
  innerInput: {
    fontFamily: 'var(--e-font-sans)',
    fontSize: 'var(--e-type-base)',
    color: 'var(--e-text-primary)',
    padding: 'var(--e-space-4) var(--e-space-4)',
  },
  visibilityToggle: {
    color: 'var(--e-text-muted)',
    transition: 'color 0.2s ease',
    '&:hover': {
      color: 'var(--e-text-secondary)',
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
        backgroundColor: 'var(--e-bg-base)',
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
          padding: 'var(--e-space-10) var(--e-space-10) var(--e-space-10)', /* 40px all around */
          position: 'relative',
          backgroundColor: 'rgba(255, 255, 255, 0.82)',
          backdropFilter: 'blur(24px) saturate(1.2)',
          WebkitBackdropFilter: 'blur(24px) saturate(1.2)',
          borderRadius: 'var(--e-radius-xl)',
          border: '1px solid rgba(229, 229, 229, 0.6)',
          boxShadow:
            '0 0 0 1px rgba(255, 255, 255, 0.5), 0 1px 3px rgba(0, 0, 0, 0.04), 0 8px 32px rgba(0, 0, 0, 0.06)',
          zIndex: 2,
        }}
      >
        <LoadingOverlay visible={authLoading} />

        {/* ─── Branding ─── */}
        <div style={{ textAlign: 'center', marginBottom: 'var(--e-space-8)' }}> {/* 32px */}
          <h1
            style={{
              fontFamily: 'var(--e-font-display)',
              fontSize: 'var(--e-type-lg)', /* 28px */
              fontWeight: 700,
              fontStyle: 'italic',
              color: 'var(--e-brand)',
              letterSpacing: '-0.03em',
              lineHeight: 1,
              margin: 0,
            }}
          >
            E<span style={{ color: 'var(--e-text-tertiary)', fontStyle: 'normal' }}>.</span>sapiens
          </h1>
          <p
            style={{
              fontFamily: 'var(--e-font-sans)',
              fontSize: 'var(--e-type-xs)', /* 12px */
              color: 'var(--e-text-muted)',
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
            backgroundColor: 'var(--e-bg-subtle)',
            borderRadius: 'var(--e-radius-md)',
            padding: 'var(--e-space-2)', /* 4px */
            marginBottom: 'var(--e-space-5)', /* 24px */
          }}
        >
          {(['signin', 'register'] as const).map((tab) => (
            <button
              key={tab}
              onClick={() => setActiveTab(tab)}
              style={{
                flex: 1,
                padding: 'var(--e-space-2) 0', /* 8px vertical */
                fontFamily: 'var(--e-font-sans)',
                fontSize: 'var(--e-type-xs)', /* 12px */
                fontWeight: activeTab === tab ? 600 : 500,
                color: activeTab === tab ? 'var(--e-brand)' : 'var(--e-text-tertiary)',
                backgroundColor: activeTab === tab ? 'var(--e-bg-surface)' : 'transparent',
                border: 'none',
                borderRadius: 'var(--e-radius-sm)',
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
                backgroundColor: 'var(--e-error-bg)',
                border: '1px solid var(--e-error)',
                borderRadius: 'var(--e-radius-lg)',
              },
              label: { fontFamily: 'var(--e-font-sans)', fontWeight: 600, color: 'var(--e-error)', fontSize: 'var(--e-type-sm)' },
              body: { fontFamily: 'var(--e-font-sans)', fontSize: 'var(--e-type-sm)', color: 'var(--e-error)' },
            }}
          >
            {error}
          </Alert>
        )}

        {/* ─── Form ─── */}
        <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: 'var(--e-space-5)' }}> {/* 24px */}
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
                  borderColor: 'var(--e-error)',
                  '&:focus': {
                    borderColor: 'var(--e-error)',
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
                marginTop: '0',
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
                    fontSize: 'var(--e-type-xs)', /* 12px */
                    color: 'var(--e-text-tertiary)',
                    cursor: 'pointer',
                  },
                  input: {
                    cursor: 'pointer',
                    borderColor: 'var(--e-border-subtle)',
                    transition: 'all 0.2s ease',
                    '&:checked': {
                      backgroundColor: 'var(--e-brand)',
                      borderColor: 'var(--e-brand)',
                    },
                  },
                }}
              />
              <a
                href="#"
                onClick={(e) => e.preventDefault()}
                style={{
                  fontFamily: 'var(--e-font-sans)',
                  fontSize: 'var(--e-type-xs)', /* 12px */
                  color: 'var(--e-text-secondary)',
                  textDecoration: 'none',
                  fontWeight: 500,
                  transition: 'color 0.2s ease',
                  cursor: 'pointer',
                }}
                onMouseEnter={(e) => (e.currentTarget.style.color = 'var(--e-brand)')}
                onMouseLeave={(e) => (e.currentTarget.style.color = 'var(--e-text-secondary)')}>
                Forgot password?
              </a>
            </div>
          )}

          <button
            type="submit"
            disabled={submitting || !!emailError}
            style={{
              fontFamily: 'var(--e-font-sans)',
              fontSize: 'var(--e-type-sm)', /* 16px */
              fontWeight: 600,
              height: '48px',
              borderRadius: 'var(--e-radius-lg)',
              backgroundColor: submitting ? 'var(--e-bg-subtle)' : 'var(--e-brand)',
              color: submitting ? 'var(--e-text-tertiary)' : '#FFFFFF',
              border: 'none',
              cursor: submitting ? 'not-allowed' : 'pointer',
              transition: 'all 0.2s ease',
              letterSpacing: '0.01em',
              marginTop: 'var(--e-space-1)', /* 4px */
              opacity: submitting ? 0.7 : 1,
            }}
            onMouseEnter={(e) => {
              if (!submitting) e.currentTarget.style.backgroundColor = 'var(--e-brand-hover)';
            }}
            onMouseLeave={(e) => {
              if (!submitting) e.currentTarget.style.backgroundColor = 'var(--e-brand)';
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
            gap: 'var(--e-space-2)', /* 8px */
            margin: 'var(--e-space-6) 0', /* 24px */
          }}
        >
          <div style={{ flex: 1, height: '1px', backgroundColor: 'var(--e-border-subtle)' }} />
          <span
            style={{
              fontFamily: 'var(--e-font-sans)',
              fontSize: 'var(--e-type-xs)', /* 12px */
              color: 'var(--e-text-muted)',
              fontWeight: 500,
              letterSpacing: '0.04em',
              textTransform: 'uppercase',
            }}
          >
            Or continue with
          </span>
          <div style={{ flex: 1, height: '1px', backgroundColor: 'var(--e-border-subtle)' }} />
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
            gap: 'var(--e-space-2)', /* 8px */
            fontFamily: 'var(--e-font-sans)',
            fontSize: 'var(--e-type-sm)', /* 16px */
            fontWeight: 500,
            color: 'var(--e-text-secondary)',
            backgroundColor: '#FFFFFF',
            border: '1px solid var(--e-border-subtle)',
            borderRadius: 'var(--e-radius-lg)',
            cursor: 'pointer',
            transition: 'all 0.2s ease',
          }}
          onMouseEnter={(e) => {
            e.currentTarget.style.backgroundColor = 'var(--e-bg-hover)';
            e.currentTarget.style.borderColor = 'var(--e-border)';
          }}
          onMouseLeave={(e) => {
            e.currentTarget.style.backgroundColor = '#FFFFFF';
            e.currentTarget.style.borderColor = 'var(--e-border-subtle)';
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
            fontSize: 'var(--e-type-xs)', /* 12px */
            color: 'var(--e-text-muted)',
            marginTop: 'var(--e-space-6)', /* 24px */
            marginBottom: 0,
          }}
        >
          {isSignIn ? "Don't have an account? " : 'Already have an account? '}
          <span
            style={{
              color: 'var(--e-brand)',
              cursor: 'pointer',
              fontWeight: 600,
              transition: 'opacity 0.2s ease',
            }}
            onClick={() => setActiveTab(isSignIn ? 'register' : 'signin')}
            onMouseEnter={(e) => (e.currentTarget.style.opacity = '0.7')}
            onMouseLeave={(e) => (e.currentTarget.style.opacity = '1')}>
            {isSignIn ? 'Create account' : 'Sign in'}
          </span>
        </p>
      </div>
    </div>
  );
}