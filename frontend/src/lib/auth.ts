/**
 * auth.ts — Authentication context, hook, and API client for E.sapiens
 *
 * Provides:
 *   - AuthProvider / AuthContext / useAuth
 *   - API functions: login, register, getMe
 *   - JWT stored in localStorage under key 'esapiens_token'
 *   - Automatic redirect to login on 401
 */

import {
  createContext,
  useContext,
  useState,
  useEffect,
  useCallback,
  type ReactNode,
} from 'react';

/* ─── Types ─── */

export interface User {
  id: string;
  email: string;
  full_name: string;
  created_at: string;
}

export interface AuthResponse {
  access_token: string;
  token_type: string;
  user: User;
}

export interface AuthState {
  user: User | null;
  token: string | null;
  loading: boolean;   // true while checking stored token on mount
  authenticated: boolean;
}

/* ─── Token helpers ─── */

const TOKEN_KEY = 'esapiens_token';

function getStoredToken(): string | null {
  try {
    return localStorage.getItem(TOKEN_KEY);
  } catch {
    return null;
  }
}

function setStoredToken(token: string): void {
  try {
    localStorage.setItem(TOKEN_KEY, token);
  } catch {
    // localStorage may be unavailable in some environments
  }
}

function removeStoredToken(): void {
  try {
    localStorage.removeItem(TOKEN_KEY);
  } catch {
    // noop
  }
}

/* ─── Auth API client ─── */

const AUTH_BASE = '';

export async function login(email: string, password: string): Promise<AuthResponse> {
  const res = await fetch(`${AUTH_BASE}/auth/login`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email, password }),
  });

  if (!res.ok) {
    const body = await res.text().catch(() => '');
    throw new Error(
      `Login failed: ${res.status}${body ? ` — ${body.slice(0, 200)}` : ''}`,
    );
  }

  return res.json();
}

export async function register(
  email: string,
  password: string,
  full_name?: string,
): Promise<AuthResponse> {
  const payload: Record<string, string> = { email, password };
  if (full_name) payload.full_name = full_name;

  const res = await fetch(`${AUTH_BASE}/auth/register`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });

  if (!res.ok) {
    const body = await res.text().catch(() => '');
    throw new Error(
      `Registration failed: ${res.status}${body ? ` — ${body.slice(0, 200)}` : ''}`,
    );
  }

  return res.json();
}

export async function getMe(token: string): Promise<User> {
  const res = await fetch(`${AUTH_BASE}/auth/me`, {
    headers: {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${token}`,
    },
  });

  if (!res.ok) {
    if (res.status === 401) {
      throw new Error('Unauthorized');
    }
    const body = await res.text().catch(() => '');
    throw new Error(
      `Failed to fetch user: ${res.status}${body ? ` — ${body.slice(0, 200)}` : ''}`,
    );
  }

  return res.json();
}

/* ─── Context ─── */

interface AuthContextValue extends AuthState {
  login: (email: string, password: string) => Promise<void>;
  register: (email: string, password: string, fullName?: string) => Promise<void>;
  logout: () => void;
}

const AuthContext = createContext<AuthContextValue | null>(null);

/* ─── Provider ─── */

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [token, setToken] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  /* Check stored token on mount */
  useEffect(() => {
    const stored = getStoredToken();
    if (!stored) {
      setLoading(false);
      return;
    }

    getMe(stored)
      .then((u) => {
        setUser(u);
        setToken(stored);
      })
      .catch(() => {
        // Token is invalid or expired — clear it
        removeStoredToken();
        setUser(null);
        setToken(null);
      })
      .finally(() => {
        setLoading(false);
      });
  }, []);

  const handleLogin = useCallback(async (email: string, password: string) => {
    const data = await login(email, password);
    setStoredToken(data.access_token);
    setToken(data.access_token);
    setUser(data.user);
  }, []);

  const handleRegister = useCallback(
    async (email: string, password: string, fullName?: string) => {
      const data = await register(email, password, fullName);
      setStoredToken(data.access_token);
      setToken(data.access_token);
      setUser(data.user);
    },
    [],
  );

  const handleLogout = useCallback(() => {
    removeStoredToken();
    setToken(null);
    setUser(null);
  }, []);

  const value: AuthContextValue = {
    user,
    token,
    loading,
    authenticated: !!user && !!token,
    login: handleLogin,
    register: handleRegister,
    logout: handleLogout,
  };

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

/* ─── Hook ─── */

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return ctx;
}

/* ─── Utility: get current token (for api.ts) ─── */

export function getToken(): string | null {
  return getStoredToken();
}

export function clearToken(): void {
  removeStoredToken();
}