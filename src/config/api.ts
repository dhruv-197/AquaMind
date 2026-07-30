/**
 * FastAPI base URL.
 *
 * Resolution order:
 *   1. VITE_API_BASE_URL (build-time env. Set this for any non-localhost
 *      deployment, e.g. A hosted demo, staging, or production build).
 *   2. Same-origin `/api`. Works when a reverse proxy (or this repo's
 *      server.ts) forwards `/api/*` to FastAPI, so no backend host needs
 *      to be baked into the client bundle at all.
 *   3. Http://127.0.0.1:8000. Local-dev fallback only. Use 127.0.0.1, not
 *      localhost, because uvicorn often binds IPv4 only while Windows
 *      resolves "localhost" to ::1 first.
 */
const envBase = (import.meta as any).env?.VITE_API_BASE_URL as string | undefined;

export const FASTAPI_BASE =
  envBase && envBase.trim().length > 0
    ? envBase.trim().replace(/\/+$/, '')
    : (typeof window !== 'undefined' && window.location.hostname !== 'localhost' && window.location.hostname !== '127.0.0.1')
      ? `${window.location.origin}/api`
      : 'http://127.0.0.1:8000';
