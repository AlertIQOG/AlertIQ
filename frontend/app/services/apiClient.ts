/**
 * Shared API client.
 *
 * Single source of truth for the backend base URL, the stored auth token,
 * and fetch calls. Every service module goes through `apiFetch`, which
 * injects the `Authorization` header and redirects to /login when the
 * backend answers 401 (missing/expired/invalid token).
 */

export const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api/v1';

const TOKEN_KEY = 'alertiq-auth-token';
const USER_KEY = 'alertiq-auth-user';

export interface AuthUser {
  id: string;
  username: string;
  full_name?: string | null;
  role: 'Admin' | 'Operator' | 'Viewer';
}

export function getToken(): string | null {
  if (typeof window === 'undefined') return null;
  return localStorage.getItem(TOKEN_KEY);
}

export function setSession(token: string, user: AuthUser): void {
  localStorage.setItem(TOKEN_KEY, token);
  localStorage.setItem(USER_KEY, JSON.stringify(user));
}

export function clearSession(): void {
  localStorage.removeItem(TOKEN_KEY);
  localStorage.removeItem(USER_KEY);
}

export function getStoredUser(): AuthUser | null {
  if (typeof window === 'undefined') return null;
  const raw = localStorage.getItem(USER_KEY);
  if (!raw) return null;
  try {
    return JSON.parse(raw) as AuthUser;
  } catch {
    return null;
  }
}

/** Raw JSON string of the stored user — stable snapshot for useSyncExternalStore. */
export function getStoredUserRaw(): string | null {
  if (typeof window === 'undefined') return null;
  return localStorage.getItem(USER_KEY);
}

/** Subscribe to session changes (other tabs / logout). */
export function subscribeToSession(callback: () => void): () => void {
  window.addEventListener('storage', callback);
  return () => window.removeEventListener('storage', callback);
}

/**
 * fetch wrapper: prepends the API base URL, adds the bearer token, and
 * handles 401 by clearing the session and sending the user to /login.
 */
export async function apiFetch(path: string, init: RequestInit = {}): Promise<Response> {
  const headers = new Headers(init.headers);
  if (!headers.has('Content-Type') && init.body) {
    headers.set('Content-Type', 'application/json');
  }
  const token = getToken();
  if (token) {
    headers.set('Authorization', `Bearer ${token}`);
  }

  const response = await fetch(`${API_BASE_URL}${path}`, { ...init, headers });

  if (response.status === 401 && typeof window !== 'undefined') {
    clearSession();
    if (window.location.pathname !== '/login') {
      window.location.href = '/login';
    }
  }
  return response;
}