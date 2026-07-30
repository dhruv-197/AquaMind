/**
 * Client-side JWT expiry check (display/UX only. The signature is never
 * verified client-side; the backend is the actual authority on validity).
 * Previously ProtectedRoute only checked whether a token string was
 * *present*, so a stale/expired 24h-old token still rendered protected
 * pages until an API call happened to fail.
 */
export function decodeJwtPayload(token: string): Record<string, unknown> | null {
  try {
    const [, payload] = token.split('.');
    if (!payload) return null;
    const base64 = payload.replace(/-/g, '+').replace(/_/g, '/');
    const padded = base64 + '='.repeat((4 - (base64.length % 4)) % 4);
    return JSON.parse(atob(padded));
  } catch {
    return null;
  }
}

export function isTokenExpired(token: string | null): boolean {
  if (!token) return true;
  const payload = decodeJwtPayload(token);
  const exp = typeof payload?.exp === 'number' ? payload.exp : null;
  if (exp == null) return false; // no exp claim. Treat as non-expiring rather than locking the user out
  return Date.now() >= exp * 1000;
}
