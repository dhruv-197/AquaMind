/**
 * Session-lifetime cache for dashboard payloads.
 *
 * Held in module memory only — never localStorage/sessionStorage. Dashboard
 * responses are operational data, not secrets, but persisting them would
 * outlive the session and survive a sign-out, so they stay in memory where a
 * page reload clears them. No tokens or credentials are ever stored here.
 *
 * Entries are namespaced by the signed-in account so a second user on the same
 * tab cannot be shown the previous user's operational picture.
 */

export type CacheEntry<T> = {
  data: T;
  updatedAt: string;
};

const store = new Map<string, CacheEntry<unknown>>();
let namespace = '';

function currentNamespace(): string {
  try {
    return localStorage.getItem('user_email') || 'anonymous';
  } catch {
    return 'anonymous';
  }
}

/** Drop everything if the signed-in account changed since the last access. */
function syncNamespace() {
  const active = currentNamespace();
  if (active !== namespace) {
    store.clear();
    namespace = active;
  }
}

export function readDashboardCache<T>(key: string): CacheEntry<T> | null {
  syncNamespace();
  return (store.get(key) as CacheEntry<T> | undefined) ?? null;
}

export function writeDashboardCache<T>(key: string, data: T, updatedAt = new Date().toISOString()) {
  syncNamespace();
  store.set(key, { data, updatedAt });
}

export function clearDashboardCache() {
  store.clear();
}

/** Test seam: cache contents without touching the namespace guard. */
export function dashboardCacheKeys(): string[] {
  return [...store.keys()];
}
