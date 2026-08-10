/**
 * Dashboard data loading.
 *
 * Three tiers, so the command center paints as soon as the decision-critical
 * numbers land instead of waiting on the slowest endpoint:
 *
 *   1. essential  — water stress, reservoirs, leak alerts (gate the first paint)
 *   2. deferred   — weather, groundwater, sensors (enrich the view afterwards)
 *   3. on demand  — recommendations (Gemini-backed; only when actually needed)
 *
 * Every request carries a deadline and a shared AbortSignal, and every result
 * is stamped with the fetch cycle that produced it, so a slow earlier response
 * can never overwrite a newer one.
 */
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { ApiError, isAbortError, type ApiRequestInit } from '../services/apiClient';
import { readDashboardCache, writeDashboardCache } from '../services/dashboardCache';
import {
  fetchWaterStress,
  loadAlerts,
  loadGroundwater,
  loadRecommendations,
  loadSensors,
  loadShortageRisks,
  loadWeather,
  type ApiAlert,
  type ApiAquifer,
  type ApiSensor,
  type ApiShortageRisk,
  type ApiWeather,
  type WaterIntelligencePayload,
} from '../services/telemetry';
import {
  cachedPanel,
  dashboardPhase,
  DEFERRED_PANELS,
  errorPanel,
  ESSENTIAL_PANELS,
  failedPanelLabels,
  idlePanel,
  latestUpdatedAt,
  loadingPanel,
  successPanel,
  type Panel,
  type PanelStatus,
} from './dashboardState';

/**
 * Warm, every dashboard endpoint answers in well under a second; the water-stress
 * fusion is the outlier because a cold call reloads four models and may refetch
 * the weather provider. 20s covers a cold fusion without leaving a panel spinning
 * forever (12s was too tight against measured ~11s cold starts).
 */
export const DASHBOARD_TIMEOUT_MS = 20_000;

export type DashboardRecommendation = {
  id?: string;
  title?: string;
  description?: string;
  action_description?: string;
  priority?: string;
};

export type DashboardPanels = {
  waterStress: Panel<WaterIntelligencePayload>;
  shortageRisks: Panel<ApiShortageRisk[]>;
  alerts: Panel<ApiAlert[]>;
  weather: Panel<ApiWeather | null>;
  aquifers: Panel<ApiAquifer[]>;
  sensors: Panel<ApiSensor[]>;
  recommendations: Panel<DashboardRecommendation[]>;
};

export type DashboardPanelKey = keyof DashboardPanels;

/** One request per panel, so the tier lists below fully describe the load plan. */
export const PANEL_LOADERS: {
  [K in DashboardPanelKey]: (init: ApiRequestInit) => Promise<NonNullable<DashboardPanels[K]['data']>>;
} = {
  waterStress: (init) => fetchWaterStress(init),
  shortageRisks: (init) => loadShortageRisks(init),
  alerts: (init) => loadAlerts(init),
  weather: (init) => loadWeather(init) as Promise<ApiWeather>,
  aquifers: (init) => loadGroundwater(init),
  sensors: (init) => loadSensors(init),
  recommendations: (init) =>
    loadRecommendations('REG-1', false, init).then(
      (result) => (result?.recommendations || []) as DashboardRecommendation[]
    ),
};

/** Recommendations are excluded: an opt-in feed should not resurrect itself from cache. */
const CACHED_KEYS = ['waterStress', 'shortageRisks', 'alerts', 'weather', 'aquifers', 'sensors'] as const;
type CachedKey = (typeof CACHED_KEYS)[number];

function isCachedKey(key: DashboardPanelKey): key is CachedKey {
  return (CACHED_KEYS as readonly string[]).includes(key);
}

function restore<K extends CachedKey>(key: K, fallback: Panel<never>): DashboardPanels[K] {
  const entry = readDashboardCache<DashboardPanels[K]['data']>(key);
  return (entry ? cachedPanel(entry.data, entry.updatedAt) : fallback) as DashboardPanels[K];
}

function initialPanels(): DashboardPanels {
  // Revisiting the dashboard in the same session shows the previous payload
  // immediately while a fresh fetch runs underneath.
  const empty = idlePanel<never>();
  return {
    waterStress: restore('waterStress', empty),
    shortageRisks: restore('shortageRisks', empty),
    alerts: restore('alerts', empty),
    weather: restore('weather', empty),
    aquifers: restore('aquifers', empty),
    sensors: restore('sensors', empty),
    recommendations: idlePanel(),
  };
}

function messageFor(error: unknown): string {
  if (error instanceof ApiError && error.kind === 'timeout') {
    return 'Timed out while loading this panel.';
  }
  return error instanceof Error ? error.message : 'Request failed';
}

export type DashboardData = {
  panels: DashboardPanels;
  panelStatus: Record<DashboardPanelKey, PanelStatus>;
  /** Nothing usable on screen yet — render the skeleton shell. */
  isInitialLoading: boolean;
  /** Every essential request failed with no cached fallback. */
  apiUnavailable: boolean;
  /** Labels of panels that failed, for a subtle notice. Empty when all loaded. */
  failedPanels: string[];
  lastUpdatedAt: string | null;
  refresh: () => void;
  /** Loads the Gemini-backed recommendation feed only when something needs it. */
  requestRecommendations: () => void;
};

export function useDashboardData(): DashboardData {
  const [panels, setPanels] = useState<DashboardPanels>(initialPanels);

  const controllerRef = useRef<AbortController | null>(null);
  const cycleRef = useRef(0);
  const mountedRef = useRef(true);
  const deferredTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const recommendationsRequestedRef = useRef(false);

  const setPanel = useCallback(<K extends DashboardPanelKey>(key: K, next: DashboardPanels[K]) => {
    setPanels((prev) => ({ ...prev, [key]: next }) as DashboardPanels);
  }, []);

  const load = useCallback(() => {
    // A new refresh supersedes whatever is still in flight.
    controllerRef.current?.abort(new ApiError('Superseded by a newer dashboard refresh', 'aborted'));
    if (deferredTimerRef.current) clearTimeout(deferredTimerRef.current);

    const controller = new AbortController();
    controllerRef.current = controller;
    const cycle = cycleRef.current + 1;
    cycleRef.current = cycle;

    const init = { signal: controller.signal, timeoutMs: DASHBOARD_TIMEOUT_MS };
    const isCurrent = () => mountedRef.current && cycleRef.current === cycle;

    const settle = <K extends DashboardPanelKey>(key: K) => {
      PANEL_LOADERS[key](init).then(
        (data) => {
          if (!isCurrent()) return;
          const updatedAt = new Date().toISOString();
          if (isCachedKey(key)) writeDashboardCache(key, data, updatedAt);
          setPanel(key, successPanel(data, updatedAt) as DashboardPanels[K]);
        },
        (error) => {
          // A cancelled request is not a failure the operator needs to see.
          if (!isCurrent() || isAbortError(error)) return;
          setPanels((prev) => ({
            ...prev,
            [key]: errorPanel(messageFor(error), prev[key]),
          }) as DashboardPanels);
        }
      );
    };

    setPanels((prev) => {
      const next = { ...prev } as Record<string, Panel<unknown>>;
      for (const key of [...ESSENTIAL_PANELS, ...DEFERRED_PANELS]) {
        next[key] = loadingPanel(prev[key]);
      }
      return next as DashboardPanels;
    });

    ESSENTIAL_PANELS.forEach(settle);

    // Yield once so the browser paints the shell and the essential requests get
    // the connection budget first.
    deferredTimerRef.current = setTimeout(() => {
      if (!isCurrent()) return;
      DEFERRED_PANELS.forEach(settle);
    }, 0);

    // Keep an already-opened recommendation feed fresh, but never start one the
    // user has not asked for.
    if (recommendationsRequestedRef.current) {
      setPanels((prev) => ({ ...prev, recommendations: loadingPanel(prev.recommendations) }));
      settle('recommendations');
    }
  }, [setPanel]);

  useEffect(() => {
    mountedRef.current = true;
    load();
    return () => {
      mountedRef.current = false;
      if (deferredTimerRef.current) clearTimeout(deferredTimerRef.current);
      controllerRef.current?.abort(new ApiError('Dashboard unmounted', 'aborted'));
    };
  }, [load]);

  const requestRecommendations = useCallback(() => {
    if (recommendationsRequestedRef.current) return;
    recommendationsRequestedRef.current = true;

    const cycle = cycleRef.current;
    setPanels((prev) => ({ ...prev, recommendations: loadingPanel(prev.recommendations) }));

    PANEL_LOADERS.recommendations({
      signal: controllerRef.current?.signal,
      timeoutMs: DASHBOARD_TIMEOUT_MS,
    }).then(
      (data) => {
        if (!mountedRef.current || cycleRef.current !== cycle) return;
        setPanel('recommendations', successPanel(data));
      },
      (error) => {
        if (!mountedRef.current || cycleRef.current !== cycle || isAbortError(error)) return;
        // Allow a retry later rather than latching the failure forever.
        recommendationsRequestedRef.current = false;
        setPanels((prev) => ({
          ...prev,
          recommendations: errorPanel(messageFor(error), prev.recommendations),
        }));
      }
    );
  }, [setPanel]);

  const phase = dashboardPhase(panels);

  // Stable identity so consumers can memoize on it instead of re-deriving KPIs
  // on every render.
  const panelStatus = useMemo(
    () => ({
      waterStress: panels.waterStress.status,
      shortageRisks: panels.shortageRisks.status,
      alerts: panels.alerts.status,
      weather: panels.weather.status,
      aquifers: panels.aquifers.status,
      sensors: panels.sensors.status,
      recommendations: panels.recommendations.status,
    }),
    [panels]
  );

  return {
    panels,
    panelStatus,
    isInitialLoading: phase === 'initial',
    apiUnavailable: phase === 'unavailable',
    failedPanels: failedPanelLabels(panels),
    lastUpdatedAt: latestUpdatedAt(panels),
    refresh: load,
    requestRecommendations,
  };
}
