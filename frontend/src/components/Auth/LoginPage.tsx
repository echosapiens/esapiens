/**
 * LoginPage.tsx — Authentication page for E.sapiens
 *
 * Two-tab layout: Sign In / Register
 * Matches E.sapiens design system using CSS custom properties.
 * Uses Mantine TextInput, PasswordInput, Button, Paper, Tabs.
 */

import { useState, useCallback } from 'react';
import {
  TextInput,
  PasswordInput,
  Button,
  Paper,
  Tabs,
  Stack,
  Text,
  Divider,
  Alert,
  LoadingOverlay,
} from '@mantine/core';
import { useAuth } from '../../lib/auth';

export function LoginPage() {
  const { login, register, loading: authLoading } = useAuth();

  const [activeTab, setActiveTab] = useState<string | null>('signin');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [fullName, setFullName] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = useCallback(
    async (e: React.FormEvent) => {
      e.preventDefault();
      setError(null);
      setSubmitting(true);

      try {
        if (activeTab === 'signin') {
          await login(email, password);
        } else {
          await register(email, password, fullName || undefined);
        }
        // On success, auth context updates – App will re-render to main UI
      } catch (err: unknown) {
        const message =
          err instanceof Error ? err.message : 'An unexpected error occurred';
        // Clean up common error messages for display
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
    [activeTab, email, password, fullName, login, register],
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
        backgroundColor: 'var(--e-bg-default)',
      }}
    >
      <Paper
        shadow="md"
        radius="xl"
        style={{
          width: '100%',
          maxWidth: 420,
          padding: 'var(--e-space-8) var(--e-space-10)',
          position: 'relative',
          backgroundColor: 'var(--e-bg-surface)',
          border: '1px solid var(--e-border-subtle)',
          boxShadow: 'var(--e-shadow-lg)',
        }}
      >
        <LoadingOverlay visible={authLoading} overlayBlur={2} />

        {/* ─── Logo & Branding ─── */}
        <Stack gap={4} align="center" mb="lg">
          <Text
            style={{
              fontFamily: 'var(--e-font-display)',
              fontSize: 'var(--e-type-3xl)',
              fontWeight: 700,
              color: 'var(--e-text-primary)',
              letterSpacing: '-0.03em',
              lineHeight: 1,
            }}
          >
            E.sapiens
          </Text>
          <Text
            style={{
              fontFamily: 'var(--e-font-sans)',
              fontSize: 'var(--e-type-sm)',
              color: 'var(--e-text-tertiary)',
              letterSpacing: '0.02em',
            }}
          >
            Computational Biology Platform
          </Text>
        </Stack>

        <Divider
          style={{
            borderColor: 'var(--e-border-subtle)',
            marginBottom: 'var(--e-space-5)',
          }}
        />

        {/* ─── Tabs ─── */}
        <Tabs
          value={activeTab}
          onChange={setActiveTab}
          variant="default"
          styles={{
            tab: {
              fontFamily: 'var(--e-font-sans)',
              fontSize: 'var(--e-type-sm)',
              fontWeight: 500,
              color: 'var(--e-text-tertiary)',
              borderBottom: '2px solid transparent',
              padding: '8px 16px',
              '&[data-active]': {
                color: 'var(--e-text-primary)',
                borderBottomColor: 'var(--e-brand)',
              },
              '&:hover': {
                color: 'var(--e-text-primary)',
              },
            },
            tabLabel: {
              color: 'inherit',
            },
            tabsList: {
              borderBottom: '1px solid var(--e-border-subtle)',
              marginBottom: 'var(--e-space-5)',
            },
          }}
        >
          <Tabs.Tab value="signin">Sign In</Tabs.Tab>
          <Tabs.Tab value="register">Register</Tabs.Tab>
        </Tabs>

        {/* ─── Error Alert ─── */}
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
              },
              label: {
                fontFamily: 'var(--e-font-sans)',
                fontWeight: 600,
                color: '#991B1B',
              },
              body: {
                fontFamily: 'var(--e-font-sans)',
                fontSize: 'var(--e-type-sm)',
                color: '#991B1B',
              },
            }}
          >
            {error}
          </Alert>
        )}

        {/* ─── Form ─── */}
        <form onSubmit={handleSubmit}>
          <Stack gap="md">
            {!isSignIn && (
              <TextInput
                label="Full Name"
                placeholder="Jane Doe"
                value={fullName}
                onChange={(e) => setFullName(e.currentTarget.value)}
                styles={{
                  label: {
                    fontFamily: 'var(--e-font-sans)',
                    fontSize: 'var(--e-type-sm)',
                    fontWeight: 500,
                    color: 'var(--e-text-secondary)',
                    marginBottom: '4px',
                  },
                  input: {
                    fontFamily: 'var(--e-font-sans)',
                    fontSize: 'var(--e-type-sm)',
                    backgroundColor: 'var(--e-bg-subtle)',
                    border: '1px solid var(--e-border)',
                    borderRadius: 'var(--e-radius-md)',
                    color: 'var(--e-text-primary)',
                    padding: '10px 12px',
                    height: '40px',
                    '&:focus': {
                      borderColor: 'var(--e-brand)',
                      boxShadow: '0 0 0 3px rgba(9, 36, 38, 0.08)',
                    },
                  },
                }}
              />
            )}

            <TextInput
              label="Email"
              placeholder="you@example.com"
              type="email"
              required
              value={email}
              onChange={(e) => setEmail(e.currentTarget.value)}
              styles={{
                label: {
                  fontFamily: 'var(--e-font-sans)',
                  fontSize: 'var(--e-type-sm)',
                  fontWeight: 500,
                  color: 'var(--e-text-secondary)',
                  marginBottom: '4px',
                },
                input: {
                  fontFamily: 'var(--e-font-sans)',
                  fontSize: 'var(--e-type-sm)',
                  backgroundColor: 'var(--e-bg-subtle)',
                  border: '1px solid var(--e-border)',
                  borderRadius: 'var(--e-radius-md)',
                  color: 'var(--e-text-primary)',
                  padding: '10px 12px',
                  height: '40px',
                  '&:focus': {
                    borderColor: 'var(--e-brand)',
                    boxShadow: '0 0 0 3px rgba(9, 36, 38, 0.08)',
                  },
                },
              }}
            />

            <PasswordInput
              label="Password"
              placeholder="Your password"
              required
              value={password}
              onChange={(e) => setPassword(e.currentTarget.value)}
              styles={{
                label: {
                  fontFamily: 'var(--e-font-sans)',
                  fontSize: 'var(--e-type-sm)',
                  fontWeight: 500,
                  color: 'var(--e-text-secondary)',
                  marginBottom: '4px',
                },
                input: {
                  fontFamily: 'var(--e-font-sans)',
                  fontSize: 'var(--e-type-sm)',
                  backgroundColor: 'var(--e-bg-subtle)',
                  border: '1px solid var(--e-border)',
                  borderRadius: 'var(--e-radius-md)',
                  color: 'var(--e-text-primary)',
                  padding: '10px 12px',
                  height: '40px',
                  '&:focus': {
                    borderColor: 'var(--e-brand)',
                    boxShadow: '0 0 0 3px rgba(9, 36, 38, 0.08)',
                  },
                },
                innerInput: {
                  fontFamily: 'var(--e-font-sans)',
                  fontSize: 'var(--e-type-sm)',
                  color: 'var(--e-text-primary)',
                  padding: '10px 12px',
                },
                visibilityToggle: {
                  color: 'var(--e-text-muted)',
                  '&:hover': {
                    color: 'var(--e-text-secondary)',
                  },
                },
              }}
            />

            <Button
              type="submit"
              fullWidth
              loading={submitting}
              disabled={submitting}
              styles={{
                root: {
                  fontFamily: 'var(--e-font-sans)',
                  fontSize: 'var(--e-type-sm)',
                  fontWeight: 600,
                  height: '42px',
                  borderRadius: 'var(--e-radius-md)',
                  backgroundColor: 'var(--e-brand)',
                  color: '#FFFFFF',
                  marginTop: 'var(--e-space-2)',
                  transition: 'all 0.15s ease',
                  '&:hover': {
                    backgroundColor: '#0D3537',
                  },
                  '&[data-disabled]': {
                    opacity: 0.6,
                  },
                },
              }}
            >
              {isSignIn ? 'Sign In' : 'Create Account'}
            </Button>
          </Stack>
        </form>

        {/* ─── Footer ─── */}
        <Text
          ta="center"
          mt="lg"
          style={{
            fontFamily: 'var(--e-font-sans)',
            fontSize: 'var(--e-type-xs)',
            color: 'var(--e-text-muted)',
          }}
        >
          {isSignIn ? "Don't have an account? " : 'Already have an account? '}
          <Text
            component="span"
            c="var(--e-brand)"
            style={{
              cursor: 'pointer',
              fontWeight: 600,
              textDecoration: 'underline',
              textUnderlineOffset: '2px',
            }}
            onClick={() => setActiveTab(isSignIn ? 'register' : 'signin')}
          >
            {isSignIn ? 'Register' : 'Sign In'}
          </Text>
        </Text>
      </Paper>
    </div>
  );
}