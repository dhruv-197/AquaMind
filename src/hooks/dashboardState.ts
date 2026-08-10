/**
 * Per-panel loading state for the operations dashboard.
 *
 * The dashboard used to collapse seven requests into one boolean, so a single
 * slow endpoint blocked the whole page and a failed one was indistinguishable
 * from an endpoint that legitimately returned nothing. Each panel now carries
 * its own status, and the transitions below are pure so they can be tested
 * without React or a network.
 */

export type PanelStatus = 'idle' | 'loading' | 'success' | 'error';

export type Panel<T> = {
  status: PanelStatus;
  data: T | null;
  error?: string;
  /** ISO time the `data` currently held was fetched. */
  updatedAt?: string;
  /** `data` predates the current fetch cycle (session cache, or a failed refresh). */
  stale?: boolean;
};

export function idlePanel<T>(): Panel<T> {
  return { status: 'idle', data: null };
}

/**
 * Enter the loading state. Any value we are already showing stays on screen and
 * is marked stale, so a refresh never flashes the layout back to skeletons.
 */
export function loadingPanel<T>(previous?: Panel<T>): Panel<T> {
  if (previous && previous.data !== null) {
    return { ...previous, status: 'loading', stale: true, error: undefined };
  }
  return { status: 'loading', data: null };
}

export function successPanel<T>(data: T, updatedAt: string = new Date().toISOString()): Panel<T> {
  return { status: 'success', data, updatedAt };
}

/** Data restored from the session cache: usable, but not from this cycle. */
export function cachedPanel<T>(data: T, updatedAt: string): Panel<T> {
  return { status: 'success', data, updatedAt, stale: true };
}

/**
 * A failure keeps the last known-good value visible rather than replacing it
 * with an empty array that would read as a real "nothing to report".
 */
export function errorPanel<T>(error: string, previous?: Panel<T>): Panel<T> {
  const retained = previous?.data ?? null;
  return {
    status: 'error',
    data: retained,
    error,
    updatedAt: previous?.updatedAt,
    stale: retained !== null ? true : undefined,
  };
}

export function hasData<T>(panel: Panel<T>): boolean {
  return panel.data !== null && panel.data !== undefined;
}

/** Loaded successfully and genuinely contains nothing — not the same as failed. */
export function isEmptyResult<T>(panel: Panel<T>): boolean {
  if (panel.status !== 'success' || panel.data == null) return false;
  return Array.isArray(panel.data) ? panel.data.length === 0 : false;
}

/** Showing data that did not come from the current fetch cycle. */
export function isShowingStale<T>(panel: Panel<T>): boolean {
  return panel.stale === true && hasData(panel);
}

export function isSettled<T>(panel: Panel<T>): boolean {
  return panel.status === 'success' || panel.status === 'error';
}

// ----------------------------------------------------------------------
// Dashboard-level derivations
// ----------------------------------------------------------------------

/**
 * First-view feeds: requested immediately and, between them, they decide
 * whether the backend is reachable at all.
 */
export const ESSENTIAL_PANELS = ['waterStress', 'shortageRisks', 'alerts'] as const;
export type EssentialPanelKey = (typeof ESSENTIAL_PANELS)[number];

/**
 * The subset the first paint actually waits for.
 *
 * Water stress is requested in the same breath but is deliberately excluded:
 * the fusion endpoint reloads four models and can take ten seconds cold, while
 * reservoirs and leak alerts are plain queries that return in tens of
 * milliseconds. Blocking on the slowest of the three is what made the old
 * dashboard feel broken. Water stress streams into its own KPI instead.
 */
export const FIRST_PAINT_PANELS = ['shortageRisks', 'alerts'] as const;

/** Fetched right after the shell paints; they enrich a view that already works. */
export const DEFERRED_PANELS = ['weather', 'aquifers', 'sensors'] as const;

/**
 * Never fetched by page load. `/recommendation` is Gemini-backed and re-runs the
 * whole fusion pipeline, so it waits until a panel actually needs it.
 */
export const ON_DEMAND_PANELS = ['recommendations'] as const;

export type PanelRecord = Record<string, Panel<unknown>>;

export const PANEL_LABELS: Record<string, string> = {
  waterStress: 'water stress',
  shortageRisks: 'reservoirs',
  alerts: 'leak alerts',
  weather: 'weather',
  aquifers: 'groundwater',
  sensors: 'sensors',
  recommendations: 'recommendations',
};

/**
 * `initial`  — nothing usable on screen yet, show the skeleton shell.
 * `unavailable` — both first-paint feeds failed with nothing cached (reservoirs
 *                 + leak alerts). Water-stress is deliberately excluded: a slow
 *                 or timed-out fusion must not blank the whole command center.
 * `ready` — render the command center, even if some panels are still arriving.
 */
export function dashboardPhase(panels: PanelRecord): 'initial' | 'unavailable' | 'ready' {
  const firstPaint = FIRST_PAINT_PANELS.map((key) => panels[key]).filter(Boolean);
  if (firstPaint.length === 0) return 'initial';

  if (firstPaint.every((panel) => panel.status === 'error' && !hasData(panel))) {
    return 'unavailable';
  }

  if (firstPaint.every((panel) => isSettled(panel) || hasData(panel))) {
    return 'ready';
  }
  return 'initial';
}

/** Human labels for panels that failed and have nothing to fall back on. */
export function failedPanelLabels(panels: PanelRecord): string[] {
  return Object.entries(panels)
    .filter(([, panel]) => panel.status === 'error')
    .map(([key]) => PANEL_LABELS[key] || key);
}

/** Newest `updatedAt` across panels, for the "last updated" indicator. */
export function latestUpdatedAt(panels: PanelRecord): string | null {
  const stamps = Object.values(panels)
    .map((panel) => panel.updatedAt)
    .filter((value): value is string => typeof value === 'string');
  return stamps.length ? stamps.sort().at(-1)! : null;
}

/**
 * Guard against a slow earlier request landing after a newer one.
 * Cycles are monotonic, so anything but the newest cycle is discarded.
 */
export function isCurrentCycle(cycle: number, currentCycle: number): boolean {
  return cycle === currentCycle;
}
