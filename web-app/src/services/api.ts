import { getSupabase, getAuthToken } from './supabase';
import type { StatusData, DashboardData } from '../types';

// ─── Auth (via Supabase SDK) ────────────────────────────────
export { getSupabase, getAuthToken };

export async function login(email: string, password: string) {
  const sb = await getSupabase();
  return sb.auth.signInWithPassword({ email, password });
}

export async function signup(email: string, password: string, displayName: string) {
  const sb = await getSupabase();
  return sb.auth.signUp({
    email,
    password,
    options: { data: { display_name: displayName } },
  });
}

export async function sendResetCode(email: string) {
  const sb = await getSupabase();
  return sb.auth.resetPasswordForEmail(email);
}

export async function verifyOtp(email: string, token: string, type: 'recovery' | 'signup') {
  const sb = await getSupabase();
  return sb.auth.verifyOtp({ email, token, type });
}

export async function updatePassword(password: string) {
  const sb = await getSupabase();
  return sb.auth.updateUser({ password });
}

export async function resendSignupOtp(email: string) {
  const sb = await getSupabase();
  return sb.auth.resend({ type: 'signup', email });
}

// ─── Backend API helpers ────────────────────────────────────
async function authFetch(path: string, options?: RequestInit): Promise<Response | null> {
  const token = await getAuthToken();
  if (!token) return null;
  return fetch(path, {
    ...options,
    headers: {
      Authorization: `Bearer ${token}`,
      'Content-Type': 'application/json',
      ...(options?.headers as Record<string, string> || {}),
    },
  });
}

// ─── Dashboard ──────────────────────────────────────────────
export async function fetchStatus(): Promise<StatusData | null> {
  try {
    const res = await authFetch('/api/status');
    if (!res || !res.ok) return null;
    return res.json();
  } catch { return null; }
}

export async function fetchDashboard(): Promise<DashboardData | null> {
  try {
    const res = await authFetch('/api/dashboard');
    if (!res || !res.ok) return null;
    return res.json();
  } catch { return null; }
}

// ─── Bot Control ────────────────────────────────────────────
export async function startBot(mode: string, tradeCount: number, riskPercent: number) {
  const token = await getAuthToken();
  if (!token) throw new Error('Not authenticated');
  const res = await fetch('/api/user/start', {
    method: 'POST',
    headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
    body: JSON.stringify({ mode, trade_count: tradeCount, risk_percent: riskPercent }),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error((err as { detail?: string }).detail || 'Failed to start bot');
  }
}

export async function stopBot() {
  const token = await getAuthToken();
  if (!token) throw new Error('Not authenticated');
  const res = await fetch('/api/user/stop', {
    method: 'POST',
    headers: { Authorization: `Bearer ${token}` },
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error((err as { detail?: string }).detail || 'Failed to stop bot');
  }
}

// ─── MT5 ────────────────────────────────────────────────────
export async function saveMt5Credentials(login: string, password: string, server: string) {
  const token = await getAuthToken();
  if (!token) throw new Error('Not authenticated');
  const res = await fetch('/api/mt5/credentials', {
    method: 'POST',
    headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
    body: JSON.stringify({ login, password, server }),
  });
  return res.json() as Promise<{ error?: string }>;
}

export async function testMt5Connection(login: string, password: string, server: string) {
  const token = await getAuthToken();
  if (!token) throw new Error('Not authenticated');
  const res = await fetch('/api/mt5/connect', {
    method: 'POST',
    headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' },
    body: JSON.stringify({ login, password, server }),
  });
  return res.json() as Promise<{
    connected: boolean;
    error?: string;
    automated_trading_enabled?: boolean;
    account?: { login: string; server: string; balance: number; equity: number; leverage: number; currency: string };
    terminal?: { name: string; build: string };
  }>;
}

export async function loadMt5Credentials() {
  const token = await getAuthToken();
  if (!token) return null;
  try {
    const res = await fetch('/api/mt5/credentials', {
      headers: { Authorization: `Bearer ${token}` },
    });
    const data = await res.json() as { login?: string; server?: string; connected?: boolean };
    return data.login ? data : null;
  } catch { return null; }
}

// ─── Settings ───────────────────────────────────────────────
export async function loadSettings(): Promise<Record<string, unknown> | null> {
  try {
    const res = await authFetch('/api/settings');
    if (!res || !res.ok) return null;
    return res.json();
  } catch { return null; }
}

export async function saveSettings(updates: Record<string, unknown>): Promise<boolean> {
  try {
    const res = await authFetch('/api/settings', {
      method: 'POST',
      body: JSON.stringify(updates),
    });
    return res?.ok ?? false;
  } catch { return false; }
}
