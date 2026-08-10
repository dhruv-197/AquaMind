import type {
  ApiAlert,
  ApiAquifer,
  ApiSensor,
  ApiShortageRisk,
  ApiWeather,
  WaterIntelligencePayload,
} from '../../../services/telemetry';
import type { DecisionAction, DecisionWorkspaceData } from '../../decision/types';
import type { RiskTone } from '../../../design-system/tokens';
import { riskTone } from '../../../design-system/tokens';

export type MapLayer =
  | 'reservoirs'
  | 'stress'
  | 'leakage'
  | 'demand'
  | 'climate'
  | 'decisions';

export type SelectedRegion = {
  id: string;
  name: string;
  type: string;
  severity?: string;
  meta?: string;
  lat: number;
  lng: number;
} | null;

export type ScenarioState = {
  rainfallDeltaPct: number;
  temperatureDeltaC: number;
  demandIncreasePct: number;
  populationGrowthPct: number;
  reservoirFailure: boolean;
};

export type ExecutiveKpi = {
  id: string;
  label: string;
  value: string;
  forecast?: string;
  tooltip?: string;
  /** Omitted when no measured comparison exists — never a placeholder direction. */
  trend?: { direction: 'up' | 'down' | 'flat'; label: string };
  status: { label: string; tone: RiskTone };
  sparkline: number[];
};

export type TimelineItem = {
  id: string;
  when: 'today' | '7d' | '30d';
  title: string;
  detail: string;
  severity: RiskTone;
  category: string;
};

export type PredictionCard = {
  id: string;
  title: string;
  current: string;
  confidence: string;
  trend: string;
  href: string;
  tone: RiskTone;
};

export type ModelHealthRow = {
  id: string;
  name: string;
  status: string;
  accuracy: string;
  lastTrained: string;
  confidence: string;
  health: RiskTone;
  version: string;
};

function asNum(v: unknown): number | null {
  if (typeof v === 'number' && Number.isFinite(v)) return v;
  if (typeof v === 'string' && v.trim() !== '' && Number.isFinite(Number(v))) return Number(v);
  return null;
}

/**
 * Format holdout metrics for the Supporting AI Models table.
 * Prefer MAPE / MAE (operational accuracy). Only show R² when ≥ 0.
 * negative R² is mathematically valid but misleading as an "accuracy" headline.
 */
export function formatForecastAccuracy(
  metrics: Record<string, unknown> | null | undefined,
  unitLabel = '',
): string {
  if (!metrics || Object.keys(metrics).length === 0) return '-';
  const mape = asNum(metrics.mape);
  const mae = asNum(metrics.mae);
  const rmse = asNum(metrics.rmse);
  const r2 = asNum(metrics.r2);
  const parts: string[] = [];
  if (mape != null) parts.push(`MAPE ${mape.toFixed(2)}%`);
  if (mae != null) parts.push(`MAE ${mae.toFixed(2)}${unitLabel ? ` ${unitLabel}` : ''}`);
  if (r2 != null && r2 >= 0) parts.push(`R² ${r2.toFixed(3)}`);
  else if (rmse != null && parts.length < 2) parts.push(`RMSE ${rmse.toFixed(2)}${unitLabel ? ` ${unitLabel}` : ''}`);
  return parts.length ? parts.join(' · ') : '-';
}

export function confidenceFromMetrics(
  metrics: Record<string, unknown> | null | undefined,
  trained: boolean,
): string {
  const conf = asNum(metrics?.confidence_estimate);
  if (conf != null) return `${Math.round(Math.min(1, Math.max(0, conf)) * 100)}%`;
  const mape = asNum(metrics?.mape);
  if (mape != null) {
    if (mape <= 5) return 'High';
    if (mape <= 15) return 'Moderate';
    return 'Low';
  }
  return trained ? 'Ready' : 'Low';
}

export function healthFromMetrics(
  metrics: Record<string, unknown> | null | undefined,
  trained: boolean,
): RiskTone {
  if (!trained) return 'warning';
  const mape = asNum(metrics?.mape);
  if (mape != null) {
    if (mape <= 8) return 'success';
    if (mape <= 20) return 'warning';
    return 'danger';
  }
  const r2 = asNum(metrics?.r2);
  if (r2 != null && r2 >= 0.5) return 'success';
  if (r2 != null && r2 >= 0) return 'warning';
  // Trained with available MAE even if R² is negative (low-variance holdout)
  if (asNum(metrics?.mae) != null) return 'success';
  return 'accent';
}

/** Deterministic mini series around a value for sparkline visuals. */
export function sparkAround(base: number, seed = 1, points = 8): number[] {
  const out: number[] = [];
  let x = Math.abs(seed) % 97 || 1;
  for (let i = 0; i < points; i++) {
    x = (x * 17 + 23) % 100;
    const wobble = ((x / 100) - 0.5) * 0.12;
    out.push(Math.max(0, base * (1 + wobble + (i / points) * 0.04)));
  }
  return out;
}

export function securityScoreFrom(
  wsi?: number | null,
  avgStorage?: number | null,
  criticalAlerts = 0
): number {
  // Callers must pass measured values; missing inputs use neutral mid-band only
  // when the feed itself succeeded with sparse data — not on transport failure.
  const stress = wsi ?? 50;
  const storagePart = Math.min(100, Math.max(0, avgStorage ?? 50));
  const alertPenalty = Math.min(25, criticalAlerts * 5);
  const raw = 100 - stress * 0.55 + storagePart * 0.35 - alertPenalty;
  return Math.round(Math.min(100, Math.max(0, raw)));
}

export function municipalStatus(score: number): { label: string; tone: RiskTone } {
  if (score >= 75) return { label: 'Stable', tone: 'success' };
  if (score >= 55) return { label: 'Watch', tone: 'warning' };
  if (score >= 35) return { label: 'Stressed', tone: 'danger' };
  return { label: 'Critical', tone: 'danger' };
}

/** Which upstream feed each KPI reads, so a failed feed shows "-" not a zero. */
const KPI_SOURCE: Record<string, KpiFeed> = {
  demand: 'waterStress',
  'forecast-demand': 'waterStress',
  wsi: 'waterStress',
  reservoir: 'shortageRisks',
  'critical-res': 'shortageRisks',
  leak: 'alerts',
  gw: 'aquifers',
  weather: 'weather',
  // Population blends stress context with reservoir/alert severity — gate on stress.
  population: 'waterStress',
};

export type KpiFeed = 'shortageRisks' | 'alerts' | 'aquifers' | 'weather' | 'waterStress';

/** Feeds that have not resolved yet, and why. Absent entries are treated as loaded. */
export type UnavailableSources = Partial<Record<KpiFeed, 'loading' | 'error' | undefined>>;

/**
 * Replace the value of any KPI whose feed has not delivered.
 *
 * An unreachable reservoir endpoint must not render as "0.0% storage" — that
 * reads as a measured emergency — and a feed still in flight must not look like
 * a settled reading either.
 */
function applyFeedState(kpis: ExecutiveKpi[], feeds?: UnavailableSources): ExecutiveKpi[] {
  if (!feeds) return kpis;
  return kpis.map((kpi) => {
    const state = feeds[KPI_SOURCE[kpi.id]];
    if (!state) return kpi;
    const loading = state === 'loading';
    return {
      ...kpi,
      value: loading ? '—' : '-',
      forecast: loading ? 'Loading...' : 'Unavailable',
      trend: { direction: 'flat', label: loading ? 'Updating' : 'No data' },
      status: { label: loading ? 'Loading' : 'Unavailable', tone: 'neutral' },
      sparkline: [],
    };
  });
}

export function deriveExecutiveKpis(input: {
  shortageRisks: ApiShortageRisk[];
  alerts: ApiAlert[];
  aquifers: ApiAquifer[];
  weather: ApiWeather | null;
  waterStress: WaterIntelligencePayload | null;
  demandMgd?: number | null;
  forecastDemandMgd?: number | null;
  populationAtRisk?: number | null;
  /** Real demand series (historical + forecast) backing the demand sparklines. */
  demandSeries?: Array<{ label: string; value: number }>;
  unavailable?: UnavailableSources;
}): ExecutiveKpi[] {
  const { shortageRisks, alerts, aquifers, weather, waterStress } = input;
  const avgStorage =
    shortageRisks.length > 0
      ? shortageRisks.reduce((s, r) => s + r.currentLevel, 0) / shortageRisks.length
      : null;
  const criticalRes = shortageRisks.filter((r) => r.severity === 'critical').length;
  const wsi = waterStress?.water_stress?.water_stress_index ?? null;
  const stage = waterStress?.water_stress?.stage || 'n/a';
  const avgGw =
    aquifers.length > 0
      ? aquifers.reduce((s, a) => s + a.depthToWaterM, 0) / aquifers.length
      : null;
  const activeLeaks = alerts.filter((a) => a.status === 'active' || !a.status).length;
  // The live /analytics/water-stress payload's demand component actually
  // carries `forecasted_demand_mgd` (see model_service.py::_live_demand).
  // this previously checked predicted_demand_mgd/daily_demand_mgd, neither
  // of which the API ever returns, so Current/Forecast Demand silently
  // showed "-" on every dashboard load regardless of live data.
  const demand =
    input.demandMgd ??
    (typeof waterStress?.demand?.forecasted_demand_mgd === 'number'
      ? (waterStress.demand.forecasted_demand_mgd as number)
      : typeof waterStress?.demand?.predicted_demand_mgd === 'number'
        ? (waterStress.demand.predicted_demand_mgd as number)
        : typeof waterStress?.demand?.daily_demand_mgd === 'number'
          ? (waterStress.demand.daily_demand_mgd as number)
          : typeof waterStress?.demand?.baseline_consumption_mgd === 'number'
            ? (waterStress.demand.baseline_consumption_mgd as number)
            : null);
  // Only a real forecast feed populates this. The previous `demand * 1.04`
  // fallback rendered an invented 4% rise as a "Predicted Demand" reading.
  const forecastDemand = input.forecastDemandMgd ?? null;
  // Percentage move from the current reading to the forecast, when we hold both.
  const demandDeltaPct =
    demand != null && forecastDemand != null && demand !== 0
      ? ((forecastDemand - demand) / demand) * 100
      : null;
  const demandTrend: ExecutiveKpi['trend'] =
    demandDeltaPct == null
      ? undefined
      : {
          direction: demandDeltaPct > 0.5 ? 'up' : demandDeltaPct < -0.5 ? 'down' : 'flat',
          label: `${demandDeltaPct >= 0 ? '+' : ''}${demandDeltaPct.toFixed(1)}% current to forecast`,
        };
  // A KPI sparkline is a claim about history, so it is drawn from the demand
  // series when one arrived and left empty otherwise.
  const demandSpark = (input.demandSeries ?? [])
    .map((p) => p.value)
    .filter((v) => typeof v === 'number' && Number.isFinite(v));
  const demandSparkline = demandSpark.length >= 2 ? demandSpark : [];
  const hasPopulationContext =
    typeof waterStress?.context?.population_at_risk === 'number' ||
    shortageRisks.length > 0 ||
    alerts.length > 0;
  const popAtRisk =
    input.populationAtRisk ??
    (typeof waterStress?.context?.population_at_risk === 'number'
      ? (waterStress.context.population_at_risk as number)
      : hasPopulationContext
        ? criticalRes * 120_000 + activeLeaks * 8_000
        : null);

  const resHealth =
    avgStorage == null ? 'Unavailable' : avgStorage >= 60 ? 'Healthy' : avgStorage >= 40 ? 'Moderate' : 'Critical';

  return applyFeedState([
    {
      id: 'demand',
      label: 'Current Demand',
      value: demand == null ? '-' : `${Number(demand).toFixed(1)} MGD`,
      forecast: forecastDemand == null ? undefined : `${Number(forecastDemand).toFixed(1)} MGD`,
      tooltip: 'Water demand right now across the monitored system.',
      trend: demandTrend,
      status: { label: demand && demand > 90 ? 'High' : 'Normal', tone: demand && demand > 90 ? 'warning' : 'success' },
      sparkline: demandSparkline,
    },
    {
      id: 'forecast-demand',
      label: 'Predicted Demand',
      value: forecastDemand == null ? '-' : `${Number(forecastDemand).toFixed(1)} MGD`,
      forecast: forecastDemand == null ? 'Awaiting forecast feed' : 'End of forecast range',
      tooltip: 'Expected water demand at the end of the forecast range returned by the demand model.',
      trend: demandTrend,
      status: { label: forecastDemand == null ? 'Unavailable' : 'Projected', tone: 'accent' },
      sparkline: demandSparkline,
    },
    {
      id: 'reservoir',
      label: 'Reservoir Health',
      value: avgStorage == null ? '-' : `${avgStorage.toFixed(1)}%`,
      forecast: `${criticalRes} critical`,
      tooltip: 'Average storage across monitored reservoirs.',
      trend: {
        direction: avgStorage != null && avgStorage < 45 ? 'down' : 'flat',
        label: avgStorage != null && avgStorage < 45 ? 'Declining' : 'Stable',
      },
      status: { label: resHealth, tone: riskTone(resHealth) },
      sparkline: [],
    },
    {
      id: 'wsi',
      label: 'Water Stress Index',
      value: wsi == null ? '-' : wsi.toFixed(1),
      forecast: stage,
      tooltip: 'Overall pressure on the water system using demand, climate, and storage conditions.',
      trend: { direction: (wsi ?? 0) > 50 ? 'up' : 'down', label: (wsi ?? 0) > 50 ? 'Elevated' : 'Easing' },
      status: { label: String(stage).toUpperCase(), tone: riskTone(stage) },
      sparkline: [],
    },
    {
      id: 'population',
      label: 'Population at Risk',
      value: popAtRisk == null ? '-' : Math.round(popAtRisk).toLocaleString(),
      forecast:
        input.populationAtRisk != null ||
        typeof waterStress?.context?.population_at_risk === 'number'
          ? 'From fusion context'
          : 'Planning heuristic',
      tooltip:
        input.populationAtRisk != null ||
        typeof waterStress?.context?.population_at_risk === 'number'
          ? 'Population exposed to elevated water stress, as reported by the fusion context.'
          : 'No population figure was returned this cycle, so this is a disclosed planning heuristic scaled from critical reservoirs and active alerts — not a measured count.',
      trend: {
        direction: (popAtRisk ?? 0) > 100_000 ? 'up' : 'flat',
        label: (popAtRisk ?? 0) > 100_000 ? 'Elevated' : 'Contained',
      },
      status: {
        label:
          popAtRisk == null
            ? 'Unavailable'
            : popAtRisk > 200_000
              ? 'High'
              : popAtRisk > 50_000
                ? 'Watch'
                : 'Low',
        tone:
          popAtRisk == null
            ? 'neutral'
            : popAtRisk > 200_000
              ? 'danger'
              : popAtRisk > 50_000
                ? 'warning'
                : 'success',
      },
      sparkline: [],
    },
    {
      id: 'critical-res',
      label: 'Critical Reservoirs',
      value: String(criticalRes),
      forecast: `of ${shortageRisks.length}`,
      tooltip: 'Reservoirs currently in a critical storage state.',
      trend: { direction: criticalRes > 0 ? 'up' : 'flat', label: criticalRes > 0 ? 'Action needed' : 'Clear' },
      status: { label: criticalRes > 0 ? 'Critical' : 'Clear', tone: criticalRes > 0 ? 'danger' : 'success' },
      sparkline: [],
    },
    {
      id: 'leak',
      label: 'Areas Requiring Inspection',
      value: String(activeLeaks),
      forecast: 'Active alerts',
      tooltip: 'Active leak or network alerts that need field inspection.',
      trend: { direction: activeLeaks > 3 ? 'up' : 'flat', label: activeLeaks > 3 ? 'Rising' : 'Managed' },
      status: {
        label: activeLeaks > 5 ? 'High' : activeLeaks > 0 ? 'Watch' : 'Low',
        tone: activeLeaks > 5 ? 'danger' : activeLeaks > 0 ? 'warning' : 'success',
      },
      sparkline: [],
    },
    {
      id: 'gw',
      label: 'Groundwater Level',
      value: avgGw == null ? '-' : `${avgGw.toFixed(1)} m`,
      forecast: `${aquifers.length} aquifers`,
      tooltip: 'Average depth to groundwater across monitored aquifers.',
      trend:
        avgGw == null
          ? undefined
          : {
              direction: avgGw > 25 ? 'up' : 'flat',
              label: avgGw > 25 ? 'Deep water table' : 'Within normal depth',
            },
      status: {
        label: avgGw != null && avgGw > 25 ? 'Deep' : 'OK',
        tone: avgGw != null && avgGw > 25 ? 'warning' : 'success',
      },
      sparkline: [],
    },
    {
      id: 'weather',
      label: 'Weather Outlook',
      value: weather ? `${weather.temperature_c}°C` : '-',
      forecast: weather
        ? `Deficit ${weather.rainfall_deficit_pct}%${weather.heatwave_warning ? ' · heatwave' : ''}`
        : 'No feed',
      tooltip: 'Current temperature and rainfall deficit affecting water operations.',
      trend: {
        direction: weather?.heatwave_warning || (weather?.rainfall_deficit_pct ?? 0) < -15 ? 'up' : 'flat',
        label: weather?.heatwave_warning ? 'Heat risk' : 'Seasonal',
      },
      status: {
        label: weather?.heatwave_warning ? 'Heatwave' : 'Nominal',
        tone: weather?.heatwave_warning ? 'warning' : 'success',
      },
      sparkline: [],
    },
  ], input.unavailable);
}

export function deriveTimeline(input: {
  shortageRisks: ApiShortageRisk[];
  alerts: ApiAlert[];
  aquifers: ApiAquifer[];
  decisions?: DecisionAction[];
}): TimelineItem[] {
  const items: TimelineItem[] = [];
  const today = new Date().toISOString().slice(0, 10);

  input.alerts
    .filter((a) => a.status === 'active' || !a.status)
    .slice(0, 4)
    .forEach((a) => {
      items.push({
        id: `alert-${a.id}`,
        when: 'today',
        title: `Leak alert · ${a.locationName}`,
        detail: a.aiDiagnostics || `${a.severity} severity in ${a.zone}`,
        severity: riskTone(a.severity),
        category: 'Leakage',
      });
    });

  input.shortageRisks
    .filter((r) => r.estimatedDaysRemaining <= 7)
    .slice(0, 4)
    .forEach((r) => {
      items.push({
        id: `short-7-${r.id}`,
        when: '7d',
        title: `Shortage risk · ${r.name}`,
        detail: `${r.currentLevel.toFixed(0)}% storage · ~${r.estimatedDaysRemaining}d remaining`,
        severity: riskTone(r.severity),
        category: 'Shortage',
      });
    });

  input.shortageRisks
    .filter((r) => r.estimatedDaysRemaining > 7 && r.estimatedDaysRemaining <= 30)
    .slice(0, 4)
    .forEach((r) => {
      items.push({
        id: `short-30-${r.id}`,
        when: '30d',
        title: `Depletion watch · ${r.name}`,
        detail: `Projected critical within ${r.estimatedDaysRemaining} days`,
        severity: riskTone(r.severity),
        category: 'Reservoir',
      });
    });

  input.aquifers
    .filter((a) => a.depletionRateMYear >= 2)
    .slice(0, 3)
    .forEach((a) => {
      items.push({
        id: `gw-${a.id}`,
        when: '30d',
        title: `Aquifer stress · ${a.name}`,
        detail: `${a.depthToWaterM.toFixed(1)} m depth · ${a.depletionRateMYear.toFixed(1)} m/year depletion`,
        severity: a.depletionRateMYear >= 4 ? 'danger' : 'warning',
        category: 'Groundwater',
      });
    });

  (input.decisions || []).slice(0, 3).forEach((d) => {
    items.push({
      id: `dec-${d.id}`,
      when: d.timeline_bucket === 'immediate' || d.timeline_bucket === 'today' ? 'today' : '7d',
      title: d.title,
      detail: d.description,
      severity: riskTone(d.priority_level),
      category: 'Decision',
    });
  });

  if (!items.length) {
    items.push({
      id: 'ok',
      when: 'today',
      title: 'No urgent events',
      detail: `System quiet as of ${today}`,
      severity: 'success',
      category: 'Status',
    });
  }

  return items;
}

export function mapLocationsFrom(input: {
  shortageRisks: ApiShortageRisk[];
  alerts: ApiAlert[];
  sensors: ApiSensor[];
  aquifers: ApiAquifer[];
  decisions?: DecisionAction[];
}) {
  return [
    ...input.shortageRisks.map((r) => ({
      id: r.id,
      name: r.name,
      lat: r.coordinates[0],
      lng: r.coordinates[1],
      type: 'reservoir' as const,
      severity: r.severity,
      meta: `${r.currentLevel}% · ${r.estimatedDaysRemaining}d`,
      layer: 'reservoirs' as MapLayer,
    })),
    ...input.alerts.map((a) => ({
      id: a.id,
      name: a.locationName,
      lat: a.lat,
      lng: a.lng,
      type: 'leak' as const,
      severity: a.severity,
      meta: a.zone,
      layer: 'leakage' as MapLayer,
    })),
    ...input.sensors.slice(0, 40).map((s) => ({
      id: s.id,
      name: s.name,
      lat: s.location.lat,
      lng: s.location.lng,
      type: 'sensor' as const,
      severity: s.status,
      meta: `${s.value} ${s.unit}`,
      layer: 'demand' as MapLayer,
    })),
    ...input.aquifers.slice(0, 40).map((a) => ({
      id: a.id,
      name: a.name,
      lat: a.lat,
      lng: a.lng,
      type: 'aquifer' as const,
      severity:
        a.depletionRateMYear >= 4 ? 'critical' : a.depletionRateMYear >= 2 ? 'warning' : 'low',
      meta: `${a.depthToWaterM.toFixed(1)} m`,
      layer: 'stress' as MapLayer,
    })),
    ...(input.decisions || [])
      .filter((d) => d.rank != null && d.rank <= 5)
      .slice(0, 5)
      .map((d, i) => {
        // Place decision pins near first reservoirs if available
        const anchor = input.shortageRisks[i % Math.max(1, input.shortageRisks.length)];
        return {
          id: `dec-pin-${d.id}`,
          name: d.title,
          lat: (anchor?.coordinates[0] ?? 22.5) + i * 0.15,
          lng: (anchor?.coordinates[1] ?? 78.5) + i * 0.12,
          type: 'sensor' as const,
          severity: d.priority_level,
          meta: `Priority ${d.rank ?? i + 1}`,
          layer: 'decisions' as MapLayer,
        };
      }),
  ];
}

export function chartSeriesFrom(input: {
  shortageRisks: ApiShortageRisk[];
  alerts: ApiAlert[];
  weather: ApiWeather | null;
  waterStress: WaterIntelligencePayload | null;
  /** Optional live demand series from /predict (historical + forecast). */
  demandSeries?: Array<{ label: string; value: number }>;
  /** When false, missing feeds yield empty series instead of synthetic sparklines. */
  allowSynthetic?: boolean;
}) {
  const allowSynthetic = input.allowSynthetic !== false;
  const demandBase =
    typeof input.waterStress?.demand?.daily_demand_mgd === 'number'
      ? (input.waterStress.demand.daily_demand_mgd as number)
      : typeof input.waterStress?.demand?.predicted_demand_mgd === 'number'
        ? (input.waterStress.demand.predicted_demand_mgd as number)
        : null;

  const demand =
    input.demandSeries && input.demandSeries.length > 0
      ? input.demandSeries
      : allowSynthetic && demandBase != null
        ? sparkAround(demandBase, 5, 12).map((v, i) => ({
            label: `D${i + 1}`,
            value: Number(v.toFixed(1)),
          }))
        : [];

  const reservoir = [...input.shortageRisks]
    .sort((a, b) => a.name.localeCompare(b.name))
    .slice(0, 8)
    .map((r) => ({
      label: r.name.replace(/ Reservoir| Dam/gi, '').slice(0, 12),
      value: Number(r.currentLevel.toFixed(1)),
      fill:
        r.severity === 'critical' ? '#FF3B30' : r.severity === 'warning' ? '#FF9500' : '#34C759',
    }));

  // Open-Meteo forecast uses high_c / low_c / precipitation_mm (not temp_c).
  const climate =
    input.weather?.forecast_5_day && input.weather.forecast_5_day.length > 0
      ? input.weather.forecast_5_day.map((d, i) => {
          const precip = asNum(d.precipitation_mm ?? d.precip_mm);
          const high = asNum(d.high_c ?? d.temp_c ?? d.temperature_c);
          const low = asNum(d.low_c);
          const mid =
            high != null && low != null ? (high + low) / 2 : high ?? input.weather?.temperature_c ?? 30;
          // Prefer rainfall so the series is not a flat temperature fallback.
          const value = precip != null ? precip : mid;
          const day = String(d.day || '').trim();
          const date = String(d.date || '').slice(5, 10);
          return {
            label: day || date || `D${i + 1}`,
            value: Number(Number(value).toFixed(1)),
          };
        })
      : allowSynthetic && input.weather
        ? sparkAround(input.weather.precipitation_mm ?? 5, 13, 7).map((v, i) => ({
            label: `D${i + 1}`,
            value: Number(v.toFixed(1)),
          }))
        : [];

  return { demand, reservoir, climate };
}

export type { DecisionWorkspaceData };
