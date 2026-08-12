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
const RETURN_URL_KEY = 'alertiq-return-url';

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

export function saveReturnUrl(): void {
  if (typeof window === 'undefined') {
    return;
  }

  const returnUrl =
    `${window.location.pathname}${window.location.search}`;

  if (
    returnUrl &&
    returnUrl !== '/login'
  ) {
    sessionStorage.setItem(
      RETURN_URL_KEY,
      returnUrl,
    );
  }
}

export function consumeReturnUrl(): string | null {
  if (typeof window === 'undefined') {
    return null;
  }

  const returnUrl =
    sessionStorage.getItem(RETURN_URL_KEY);

  sessionStorage.removeItem(
    RETURN_URL_KEY,
  );

  return returnUrl;
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

  if (
    response.status === 401 &&
    typeof window !== 'undefined'
  ) {
    if (window.location.pathname !== '/login') {
      saveReturnUrl();
    }

    clearSession();

    if (window.location.pathname !== '/login') {
      window.location.href = '/login';
    }
  }
  return response;
}

export class ApiRequestError extends Error {
  status: number;
  path: string;
  detail?: string;

  constructor(
    message: string,
    status: number,
    path: string,
    detail?: string,
  ) {
    super(message);
    this.name = 'ApiRequestError';
    this.status = status;
    this.path = path;
    this.detail = detail;
  }
}

async function extractApiError(response: Response): Promise<string | undefined> {
  try {
    const contentType = response.headers.get('content-type') ?? '';

    if (contentType.includes('application/json')) {
      const payload = await response.clone().json();

      if (typeof payload?.detail === 'string') {
        return payload.detail;
      }

      if (typeof payload?.message === 'string') {
        return payload.message;
      }

      return JSON.stringify(payload);
    }

    const text = await response.clone().text();
    return text || undefined;
  } catch {
    return undefined;
  }
}

export async function assertApiResponse(
  response: Response,
  path: string,
): Promise<void> {
  if (response.ok) {
    return;
  }

  const detail = await extractApiError(response);

  throw new ApiRequestError(
    detail
      ? `API request failed: ${detail}`
      : `API request failed with status ${response.status}`,
    response.status,
    path,
    detail,
  );
}

export function getApiErrorMessage(
  error: unknown,
  fallback = 'Something went wrong while communicating with the server.',
): string {
  if (error instanceof ApiRequestError) {
    if (error.status >= 500) {
      return 'AlertIQ backend is currently unavailable. Existing alert data may be temporarily inaccessible.';
    }

    if (error.status === 403) {
      return 'You do not have permission to perform this action.';
    }

    if (error.status === 404) {
      return 'The requested resource could not be found.';
    }

    return error.detail || error.message;
  }

  if (error instanceof TypeError) {
    return 'Unable to connect to the AlertIQ backend. Check the server or network connection.';
  }

  if (error instanceof Error && error.message) {
    return error.message;
  }

  return fallback;
}