/**
 * Shared FastAPI request client.
 *
 * Attaches the stored JWT (if any) as an Authorization header on every
 * request and centralizes session-expiry handling (a 401 clears the stored
 * session and bounces to /login). Previously every service reimplemented
 * its own bare `fetch()` with no Authorization header at all, so the backend
 * had no way to know who (if anyone) was calling it.
 *
 * Callers may pass an `AbortSignal` (cancellation) and/or `timeoutMs` (per-call
 * deadline). Both are opt-in: with neither set the request behaves exactly as
 * before, so long-running calls such as vision analysis and the copilot keep
 * their existing no-deadline behaviour.
 */
import { FASTAPI_BASE } from '../config/api';

/** Why a request failed, so callers can react without string-matching messages. */
export type ApiErrorKind = 'network' | 'http' | 'timeout' | 'aborted' | 'unauthorized';

export class ApiError extends Error {
  readonly kind: ApiErrorKind;
  readonly status?: number;
  readonly path?: string;

  constructor(message: string, kind: ApiErrorKind, options?: { status?: number; path?: string }) {
    super(message);
    this.name = 'ApiError';
    this.kind = kind;
    this.status = options?.status;
    this.path = options?.path;
  }
}

/** RequestInit plus an optional per-call deadline. */
export type ApiRequestInit = RequestInit & { timeoutMs?: number };

/**
 * True for both caller-initiated cancellation and our own timeout aborts.
 * Callers use this to drop a result silently instead of rendering an error.
 */
export function isAbortError(error: unknown): boolean {
  if (error instanceof ApiError) return error.kind === 'aborted';
  return error instanceof DOMException ? error.name === 'AbortError' : false;
}

export function isTimeoutError(error: unknown): boolean {
  return error instanceof ApiError && error.kind === 'timeout';
}

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

/**
 * Combine the caller's signal with an optional deadline into one signal.
 *
 * Not using `AbortSignal.any` / `AbortSignal.timeout`: both are still missing
 * from browsers this dashboard is expected to run on, and we need to abort with
 * a *typed reason* so a deadline can be told apart from a user cancellation.
 */
function resolveSignal(
  path: string,
  init?: ApiRequestInit
): { signal?: AbortSignal; dispose: () => void } {
  const parent = init?.signal ?? undefined;
  const timeoutMs = init?.timeoutMs;
  if (!timeoutMs || timeoutMs <= 0) {
    return { signal: parent, dispose: () => {} };
  }

  const controller = new AbortController();
  const timer = setTimeout(() => {
    controller.abort(
      new ApiError(`Request to ${path} timed out after ${timeoutMs}ms`, 'timeout', { path })
    );
  }, timeoutMs);

  const forwardParentAbort = () => controller.abort(parent?.reason);
  if (parent) {
    if (parent.aborted) forwardParentAbort();
    else parent.addEventListener('abort', forwardParentAbort, { once: true });
  }

  return {
    signal: controller.signal,
    dispose: () => {
      clearTimeout(timer);
      parent?.removeEventListener('abort', forwardParentAbort);
    },
  };
}

/** Turn a thrown fetch rejection into a typed ApiError. */
function toApiError(error: unknown, path: string, signal?: AbortSignal): ApiError {
  if (error instanceof ApiError) return error;
  const aborted = signal?.aborted || (error instanceof DOMException && error.name === 'AbortError');
  if (aborted) {
    const reason = signal?.reason;
    if (reason instanceof ApiError) return reason;
    return new ApiError(`Request to ${path} was cancelled`, 'aborted', { path });
  }
  return new ApiError(
    `Unable to reach AquaMind AI API at ${path}. Is the backend running?`,
    'network',
    { path }
  );
}

/** Low-level request helper. JSON in, JSON out, auth header attached, 401-aware. */
export async function apiRequest<T = unknown>(path: string, init?: ApiRequestInit): Promise<T> {
  const { signal, dispose } = resolveSignal(path, init);
  try {
    let response: Response;
    try {
      const { timeoutMs: _timeoutMs, ...requestInit } = init || {};
      response = await fetch(`${FASTAPI_BASE}${path}`, {
        ...requestInit,
        signal,
        headers: {
          'Content-Type': 'application/json',
          ...authHeaders(),
          ...(init?.headers || {}),
        },
      });
    } catch (error) {
      throw toApiError(error, path, signal);
    }

    if (response.status === 401) {
      clearSessionAndRedirect();
      throw new ApiError('Your session has expired. Please log in again.', 'unauthorized', {
        status: 401,
        path,
      });
    }

    let body: unknown = null;
    try {
      body = await response.json();
    } catch {
      body = null;
    }
    if (!response.ok) {
      throw new ApiError(extractErrorMessage(body, response.status), 'http', {
        status: response.status,
        path,
      });
    }
    return body as T;
  } finally {
    dispose();
  }
}

export function apiGet<T = unknown>(path: string, init?: ApiRequestInit): Promise<T> {
  return apiRequest<T>(path, init);
}

export function apiPost<T = unknown>(path: string, payload?: unknown, init?: ApiRequestInit): Promise<T> {
  return apiRequest<T>(path, {
    ...init,
    method: 'POST',
    body: payload !== undefined ? JSON.stringify(payload) : undefined,
  });
}

/** For multipart/form-data uploads (vision analysis, CSV imports). No JSON content-type override. */
export async function apiUpload<T = unknown>(
  path: string,
  formData: FormData,
  init?: ApiRequestInit
): Promise<T> {
  const { signal, dispose } = resolveSignal(path, init);
  try {
    let response: Response;
    try {
      response = await fetch(`${FASTAPI_BASE}${path}`, {
        method: 'POST',
        headers: { ...authHeaders() },
        body: formData,
        signal,
      });
    } catch (error) {
      throw toApiError(error, path, signal);
    }

    if (response.status === 401) {
      clearSessionAndRedirect();
      throw new ApiError('Your session has expired. Please log in again.', 'unauthorized', {
        status: 401,
        path,
      });
    }

    let body: unknown = null;
    try {
      body = await response.json();
    } catch {
      body = null;
    }
    if (!response.ok) {
      throw new ApiError(extractErrorMessage(body, response.status), 'http', {
        status: response.status,
        path,
      });
    }
    return body as T;
  } finally {
    dispose();
  }
}
