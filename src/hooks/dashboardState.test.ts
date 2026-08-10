/**
 * Tests for the dashboard loading contract.
 *
 * Run with: npm run test:dashboard  (node's test runner via tsx)
 *
 * These cover the logic that decides *what the operator sees* — which panels
 * gate the first paint, what a failure does to a panel that already had data,
 * and which responses are allowed to win a race. The React glue in
 * useDashboardData is deliberately thin so all of it is exercised here.
 */
import assert from 'node:assert/strict';
import test, { describe } from 'node:test';

import { ApiError, isAbortError, isTimeoutError } from '../services/apiClient';
import {
  clearDashboardCache,
  readDashboardCache,
  writeDashboardCache,
} from '../services/dashboardCache';
import {
  cachedPanel,
  dashboardPhase,
  DEFERRED_PANELS,
  ESSENTIAL_PANELS,
  FIRST_PAINT_PANELS,
  errorPanel,
  failedPanelLabels,
  idlePanel,
  isCurrentCycle,
  isEmptyResult,
  isShowingStale,
  latestUpdatedAt,
  loadingPanel,
  ON_DEMAND_PANELS,
  successPanel,
  type Panel,
} from './dashboardState';

/** Panel map with every essential and deferred panel in the same state. */
function panelsWith(overrides: Record<string, Panel<unknown>>): Record<string, Panel<unknown>> {
  const base: Record<string, Panel<unknown>> = {};
  for (const key of [...ESSENTIAL_PANELS, ...DEFERRED_PANELS, ...ON_DEMAND_PANELS]) {
    base[key] = idlePanel();
  }
  return { ...base, ...overrides };
}

describe('progressive rendering', () => {
  test('the shell keeps showing while the essential feeds are in flight', () => {
    const panels = panelsWith({
      waterStress: loadingPanel(),
      shortageRisks: loadingPanel(),
      alerts: loadingPanel(),
    });
    assert.equal(dashboardPhase(panels), 'initial');
  });

  test('the command center renders once the essentials settle, before slow panels finish', () => {
    const panels = panelsWith({
      waterStress: successPanel({ water_stress_index: 62 }),
      shortageRisks: successPanel([]),
      alerts: successPanel([]),
      // Deferred tier still running — it must not hold back the first paint.
      weather: loadingPanel(),
      aquifers: loadingPanel(),
      sensors: loadingPanel(),
    });
    assert.equal(dashboardPhase(panels), 'ready');
  });

  test('the slow water-stress fusion does not hold back the first paint', () => {
    const panels = panelsWith({
      waterStress: loadingPanel(),
      shortageRisks: successPanel([]),
      alerts: successPanel([]),
    });
    assert.equal(dashboardPhase(panels), 'ready');
  });

  test('water stress is still requested in the first tier, just not painted-on', () => {
    assert.ok((ESSENTIAL_PANELS as readonly string[]).includes('waterStress'));
    assert.ok(!(FIRST_PAINT_PANELS as readonly string[]).includes('waterStress'));
    for (const key of FIRST_PAINT_PANELS) {
      assert.ok((ESSENTIAL_PANELS as readonly string[]).includes(key));
    }
  });

  test('a first-paint feed still in flight keeps the skeleton up', () => {
    const panels = panelsWith({
      waterStress: successPanel({ water_stress_index: 62 }),
      shortageRisks: loadingPanel(),
      alerts: successPanel([]),
    });
    assert.equal(dashboardPhase(panels), 'initial');
  });

  test('recommendations and the AI briefing are never part of page load', () => {
    const loadedOnMount = [...ESSENTIAL_PANELS, ...DEFERRED_PANELS] as string[];
    assert.ok(!loadedOnMount.includes('recommendations'));
    assert.deepEqual([...ON_DEMAND_PANELS], ['recommendations']);
  });
});

describe('independent panel states', () => {
  test('one failed panel does not blank the panels that succeeded', () => {
    const panels = panelsWith({
      waterStress: successPanel({ water_stress_index: 62 }),
      shortageRisks: errorPanel('Request failed (500)'),
      alerts: successPanel([{ id: 'AL-1' }]),
    });

    assert.equal(dashboardPhase(panels), 'ready');
    assert.deepEqual(panels.alerts.data, [{ id: 'AL-1' }]);
    assert.deepEqual(failedPanelLabels(panels), ['reservoirs']);
  });

  test('a failure is not reported as a successful empty result', () => {
    const failed = errorPanel<unknown[]>('Timed out while loading this panel.');
    assert.equal(failed.status, 'error');
    assert.equal(failed.data, null);
    assert.equal(isEmptyResult(failed), false);
  });

  test('an endpoint that genuinely returned nothing is distinguishable from a failure', () => {
    const empty = successPanel<unknown[]>([]);
    assert.equal(empty.status, 'success');
    assert.equal(isEmptyResult(empty), true);
  });

  test('a failed refresh keeps the last good value and flags it as stale', () => {
    const loaded = successPanel([{ id: 'RES-1' }], '2026-08-10T06:00:00.000Z');
    const failed = errorPanel('Network error', loaded);

    assert.equal(failed.status, 'error');
    assert.deepEqual(failed.data, [{ id: 'RES-1' }]);
    assert.equal(isShowingStale(failed), true);
    assert.equal(failed.updatedAt, '2026-08-10T06:00:00.000Z');
  });

  test('a timed-out water-stress panel does not blank the dashboard', () => {
    const panels = panelsWith({
      waterStress: errorPanel('Timed out while loading this panel.'),
      shortageRisks: successPanel([{ id: 'RES-1' }]),
      alerts: successPanel([]),
    });
    assert.equal(dashboardPhase(panels), 'ready');
    assert.deepEqual(panels.shortageRisks.data, [{ id: 'RES-1' }]);
  });

  test('the full-unavailable screen appears only when first-paint feeds fail', () => {
    // Water-stress alone must never blank the command center.
    const slowFusion = panelsWith({
      waterStress: errorPanel('Timed out while loading this panel.'),
      shortageRisks: successPanel([]),
      alerts: successPanel([]),
    });
    assert.equal(dashboardPhase(slowFusion), 'ready');

    const oneUp = panelsWith({
      waterStress: errorPanel('down'),
      shortageRisks: errorPanel('down'),
      alerts: successPanel([]),
    });
    assert.equal(dashboardPhase(oneUp), 'ready');

    const firstPaintDown = panelsWith({
      waterStress: successPanel({ water_stress: { water_stress_index: 40 } }),
      shortageRisks: errorPanel('down'),
      alerts: errorPanel('down'),
    });
    assert.equal(dashboardPhase(firstPaintDown), 'unavailable');

    const allDown = panelsWith({
      waterStress: errorPanel('down'),
      shortageRisks: errorPanel('down'),
      alerts: errorPanel('down'),
    });
    assert.equal(dashboardPhase(allDown), 'unavailable');
  });

  test('cached data keeps the dashboard usable even when every refresh fails', () => {
    const cached = cachedPanel([{ id: 'RES-1' }], '2026-08-10T06:00:00.000Z');
    const panels = panelsWith({
      waterStress: errorPanel('down', cached),
      shortageRisks: errorPanel('down', cached),
      alerts: errorPanel('down', cached),
    });
    assert.equal(dashboardPhase(panels), 'ready');
  });
});

describe('cancellation and races', () => {
  test('an aborted request is not a user-visible failure', () => {
    assert.equal(isAbortError(new ApiError('Dashboard unmounted', 'aborted')), true);
    assert.equal(isAbortError(new DOMException('The operation was aborted.', 'AbortError')), true);
  });

  test('a real failure is not mistaken for a cancellation', () => {
    assert.equal(isAbortError(new ApiError('Request failed (500)', 'http', { status: 500 })), false);
    assert.equal(isAbortError(new Error('boom')), false);
  });

  test('a timeout is typed distinctly so the panel can say so', () => {
    const timeout = new ApiError('Request to /weather timed out after 10000ms', 'timeout');
    assert.equal(isTimeoutError(timeout), true);
    assert.equal(isAbortError(timeout), false);
  });

  test('a slow earlier response cannot overwrite a newer one', () => {
    const currentCycle = 2;
    assert.equal(isCurrentCycle(1, currentCycle), false, 'stale cycle must be dropped');
    assert.equal(isCurrentCycle(2, currentCycle), true);
  });
});

describe('session cache', () => {
  test('a refresh keeps cached data on screen instead of flashing skeletons', () => {
    const cached = cachedPanel([{ id: 'RES-1' }], '2026-08-10T06:00:00.000Z');
    assert.equal(isShowingStale(cached), true);

    const refreshing = loadingPanel(cached);
    assert.equal(refreshing.status, 'loading');
    assert.deepEqual(refreshing.data, [{ id: 'RES-1' }]);
    assert.equal(dashboardPhase(panelsWith({
      waterStress: refreshing,
      shortageRisks: refreshing,
      alerts: refreshing,
    })), 'ready');
  });

  test('an empty panel with no cache falls back to a real loading state', () => {
    const first = loadingPanel(idlePanel());
    assert.equal(first.status, 'loading');
    assert.equal(first.data, null);
    assert.equal(isShowingStale(first), false);
  });

  test('a failed panel keeps prior data and does not look like empty success', () => {
    const prior = successPanel([{ id: 'AL-1' }], '2026-08-10T06:00:00.000Z');
    const failed = errorPanel('upstream down', prior);
    assert.equal(failed.status, 'error');
    assert.deepEqual(failed.data, [{ id: 'AL-1' }]);
    assert.equal(isEmptyResult(failed), false);
    assert.equal(isShowingStale(failed), true);
  });

  test('cached payloads round-trip with their timestamp', () => {
    clearDashboardCache();
    writeDashboardCache('alerts', [{ id: 'AL-1' }], '2026-08-10T06:00:00.000Z');

    const entry = readDashboardCache<Array<{ id: string }>>('alerts');
    assert.ok(entry);
    assert.deepEqual(entry.data, [{ id: 'AL-1' }]);
    assert.equal(entry.updatedAt, '2026-08-10T06:00:00.000Z');
    assert.equal(readDashboardCache('waterStress'), null);
  });

  test('the cache never holds credentials', () => {
    clearDashboardCache();
    writeDashboardCache('alerts', [{ id: 'AL-1' }]);
    const serialized = JSON.stringify(readDashboardCache('alerts'));
    assert.ok(!serialized.includes('access_token'));
    assert.ok(!serialized.includes('Bearer'));
  });
});

describe('last updated', () => {
  test('reports the newest payload timestamp across panels', () => {
    const panels = panelsWith({
      waterStress: successPanel({}, '2026-08-10T06:00:00.000Z'),
      shortageRisks: successPanel([], '2026-08-10T07:30:00.000Z'),
      alerts: successPanel([], '2026-08-10T07:00:00.000Z'),
    });
    assert.equal(latestUpdatedAt(panels), '2026-08-10T07:30:00.000Z');
  });

  test('is null before anything has loaded', () => {
    assert.equal(latestUpdatedAt(panelsWith({})), null);
  });
});
