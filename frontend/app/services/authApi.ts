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

export async function loginWithGoogle(
  credential: string,
): Promise<AuthUser | null> {
  try {
    const response = await fetch(`${API_BASE_URL}/auth/google`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ credential }),
    });

    if (!response.ok) {
      console.error('Google login failed:', response.status);
      return null;
    }

    const data = await response.json();

    setSession(data.access_token as string, data.user as AuthUser);

    return data.user as AuthUser;
  } catch (error) {
    console.error('Google login failed:', error);
    return null;
  }
}

/**
 * Register a new account and auto-login on success.
 * Returns the created user, or an error message string on failure.
 * Uses raw fetch (not apiFetch) — same reason as login.
 */
export async function register(
  username: string,
  password: string,
  fullName?: string,
): Promise<AuthUser | string> {
  try {
    const response = await fetch(`${API_BASE_URL}/auth/register`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ username, password, full_name: fullName || null }),
    });
    if (!response.ok) {
      if (response.status === 409) return 'Username already taken';
      return 'Registration failed. Please try again.';
    }
    const data = await response.json();
    setSession(data.access_token as string, data.user as AuthUser);
    return data.user as AuthUser;
  } catch {
    return 'Registration failed. Please try again.';
  }
}

export function logout(): void {
  clearSession();
  window.location.href = '/login';
}
