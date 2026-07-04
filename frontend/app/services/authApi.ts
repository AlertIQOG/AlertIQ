import { API_BASE_URL, AuthUser, clearSession, setSession } from './apiClient';

/**
 * Exchange username + password for a bearer token.
 * Returns the logged-in user, or null on bad credentials / network error.
 * Uses a raw fetch (not apiFetch) — login itself must not trigger the
 * 401-redirect handling.
 */
export async function login(username: string, password: string): Promise<AuthUser | null> {
  try {
    const response = await fetch(`${API_BASE_URL}/auth/login`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
      body: new URLSearchParams({ username, password }),
    });
    if (!response.ok) return null;
    const data = await response.json();
    setSession(data.access_token as string, data.user as AuthUser);
    return data.user as AuthUser;
  } catch (error) {
    console.error('Login failed:', error);
    return null;
  }
}

export function logout(): void {
  clearSession();
  window.location.href = '/login';
}
