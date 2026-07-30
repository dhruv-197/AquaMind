/**
 * Shared FastAPI request client.
 *
 * Attaches the stored JWT (if any) as an Authorization header on every
 * request and centralizes session-expiry handling (a 401 clears the stored
 * session and bounces to /login). Previously every service reimplemented
 * its own bare `fetch()` with no Authorization header at all, so the backend
 * had no way to know who (if anyone) was calling it.
 */
import { FASTAPI_BASE } from '../config/api';

function authHeaders(): Record<string, string> {
  const token = localStorage.getItem('access_token');
  return token ? { Authorization: `Bearer ${token}` } : {};
}

function clearSessionAndRedirect() {
  localStorage.removeItem('access_token');
  localStorage.removeItem('user_role');
  localStorage.removeItem('username');
  localStorage.removeItem('user_email');
  if (typeof window !== 'undefined' && window.location.pathname !== '/login') {
    window.location.assign('/login');
  }
}

function extractErrorMessage(body: unknown, status: number): string {
  const detail = (body as { detail?: string | { msg?: string }[] } | null)?.detail
    ?? (body as { message?: string } | null)?.message;
  if (typeof detail === 'string') return detail;
  if (Array.isArray(detail)) {
    return detail.map((d) => d.msg || JSON.stringify(d)).join('; ');
  }
  return `Request failed (${status})`;
}

/** Low-level request helper. JSON in, JSON out, auth header attached, 401-aware. */
export async function apiRequest<T = any>(path: string, init?: RequestInit): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${FASTAPI_BASE}${path}`, {
      ...init,
      headers: {
        'Content-Type': 'application/json',
        ...authHeaders(),
        ...(init?.headers || {}),
      },
    });
  } catch {
    throw new Error(`Unable to reach AquaMind API at ${path}. Is the backend running?`);
  }

  if (response.status === 401) {
    clearSessionAndRedirect();
    throw new Error('Your session has expired. Please log in again.');
  }

  const body = await response.json().catch(() => null);
  if (!response.ok) {
    throw new Error(extractErrorMessage(body, response.status));
  }
  return body as T;
}

export function apiGet<T = any>(path: string): Promise<T> {
  return apiRequest<T>(path);
}

export function apiPost<T = any>(path: string, payload?: unknown, init?: RequestInit): Promise<T> {
  return apiRequest<T>(path, {
    ...init,
    method: 'POST',
    body: payload !== undefined ? JSON.stringify(payload) : undefined,
  });
}

/** For multipart/form-data uploads (vision analysis, CSV imports). No JSON content-type override. */
export async function apiUpload<T = any>(path: string, formData: FormData): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${FASTAPI_BASE}${path}`, {
      method: 'POST',
      headers: { ...authHeaders() },
      body: formData,
    });
  } catch {
    throw new Error(`Unable to reach AquaMind API at ${path}. Is the backend running?`);
  }

  if (response.status === 401) {
    clearSessionAndRedirect();
    throw new Error('Your session has expired. Please log in again.');
  }

  const body = await response.json().catch(() => null);
  if (!response.ok) {
    throw new Error(extractErrorMessage(body, response.status));
  }
  return body as T;
}
