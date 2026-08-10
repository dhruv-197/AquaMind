import React, { useEffect, useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import type {
  ApiAlert,
  ApiAquifer,
  ApiSensor,
  ApiShortageRisk,
  ApiWeather,
  WaterIntelligencePayload,
} from '../../../services/telemetry';
import {
  componentMetadata,
  isComponentUsable,
  predictWaterIntelligence,
} from '../../../services/telemetry';
import type { WaterIntelligenceComponent } from '../../../types/apiContracts';
import { recommendDecisions, compareStrategies } from '../../../services/decisionOptimization';
import { fetchDemandStatus, fetchDemandMetrics, predictDemand } from '../../../services/demandForecast';
import { fetchReservoirStatus, fetchReservoirMetrics } from '../../../services/reservoirForecast';
import { fetchStressStatus } from '../../../services/waterStressForecast';
import { fetchDecisionStatus } from '../../../services/decisionOptimization';
import { apiGet, apiPost, isAbortError } from '../../../services/apiClient';
import { DASHBOARD_TIMEOUT_MS } from '../../../hooks/useDashboardData';
import type { DecisionAction } from '../../decision/types';
import { ExecutiveHeader } from './ExecutiveHeader';
import { ExecutiveKpis } from './ExecutiveKpis';
import { IntelligenceMap } from './IntelligenceMap';
import { PredictionCenter } from './PredictionCenter';
import { DecisionPanel } from './DecisionPanel';
import { ScenarioSimulation } from './ScenarioSimulation';
import { ExecutiveAnalytics } from './ExecutiveAnalytics';
import { ReportCenter } from './ReportCenter';
import {
  chartSeriesFrom,
  confidenceFromMetrics,
  deriveExecutiveKpis,
  formatForecastAccuracy,
  municipalStatus,
  securityScoreFrom,
  type PredictionCard,
  type ScenarioState,
  type SelectedRegion,
  type UnavailableSources,
} from './derive';

/** The five weighted inputs behind the Water Stress Index fusion. */
const FUSION_COMPONENTS: WaterIntelligenceComponent[] = [
  'shortage',
  'groundwater',
  'leak',
  'demand',
  'climate',
];

const DEFAULT_SCENARIO: ScenarioState = {
  rainfallDeltaPct: 0,
  temperatureDeltaC: 0,
  demandIncreasePct: 0,
  populationGrowthPct: 0,
  reservoirFailure: false,
};

/** Per-feed load state. Optional so existing callers keep working unchanged. */
export type CommandCenterFeedStatus = {
  waterStress?: 'idle' | 'loading' | 'success' | 'error';
  shortageRisks?: 'idle' | 'loading' | 'success' | 'error';
  alerts?: 'idle' | 'loading' | 'success' | 'error';
  weather?: 'idle' | 'loading' | 'success' | 'error';
  aquifers?: 'idle' | 'loading' | 'success' | 'error';
};

export type CommandCenterProps = {
  sensors: ApiSensor[];
  alerts: ApiAlert[];
  shortageRisks: ApiShortageRisk[];
  aquifers: ApiAquifer[];
  weather: ApiWeather | null;
  waterStress: WaterIntelligencePayload | null;
  recommendations: Array<{ id?: string; title?: string; description?: string; action_description?: string; priority?: string }>;
  onOpenReportModal: () => void;
  onRefresh: () => void;
  /** Lets panels show "still loading" / "unavailable" instead of a plausible zero. */
  feedStatus?: CommandCenterFeedStatus;
  /** Pulls in the recommendation feed only if a panel actually needs it. */
  onRequestRecommendations?: () => void;
  /** ISO time of the newest loaded payload; falls back to render time. */
  lastUpdatedAt?: string | null;
};

type ModelReadiness = {
  demandTrained: boolean;
  reservoirTrained: boolean;
  demandMetrics: Record<string, unknown>;
  reservoirMetrics: Record<string, unknown>;
  leakF1: number | null;
};

export const CommandCenter: React.FC<CommandCenterProps> = ({
  sensors,
  alerts,
  shortageRisks,
  aquifers,
  weather,
  waterStress: waterStressProp,
  recommendations,
  onOpenReportModal,
  onRefresh,
  feedStatus,
  onRequestRecommendations,
  lastUpdatedAt,
}) => {
  const navigate = useNavigate();
  const [selected, setSelected] = useState<SelectedRegion>(null);
  const [scenario, setScenario] = useState<ScenarioState>(DEFAULT_SCENARIO);
  const [simulating, setSimulating] = useState(false);
  const [scenarioHint, setScenarioHint] = useState<string | null>(null);
  const [liveStress, setLiveStress] = useState<WaterIntelligencePayload | null>(waterStressProp);
  const [decisionActions, setDecisionActions] = useState<DecisionAction[]>([]);
  const [decisionLoading, setDecisionLoading] = useState(true);
  const [decisionFailed, setDecisionFailed] = useState(false);
  const [appliedIds, setAppliedIds] = useState<string[]>([]);
  const [applyingId, setApplyingId] = useState<string | null>(null);
  const [modelReadiness, setModelReadiness] = useState<ModelReadiness | null>(null);
  const [demandChartSeries, setDemandChartSeries] = useState<Array<{ label: string; value: number }>>([]);
  const [demandKpi, setDemandKpi] = useState<{ current: number | null; forecast: number | null }>({
    current: null,
    forecast: null,
  });

  useEffect(() => {
    setLiveStress(waterStressProp);
  }, [waterStressProp]);

  // Decision actions depend only on the selected region. Recommendations are a
  // failure fallback handled separately, so they must not retrigger this POST.
  useEffect(() => {
    const controller = new AbortController();
    const init = { signal: controller.signal, timeoutMs: DASHBOARD_TIMEOUT_MS };
    (async () => {
      setDecisionLoading(true);
      try {
        const res = await recommendDecisions(
          {
            region_id: selected?.id?.startsWith('REG') ? selected.id : undefined,
            horizon_days: 30,
            max_actions: 8,
          },
          init
        );
        if (controller.signal.aborted) return;
        setDecisionActions(res.data?.top_recommendations || res.data?.recommended_actions || []);
        setDecisionFailed(false);
      } catch (error) {
        if (isAbortError(error) || controller.signal.aborted) return;
        setDecisionFailed(true);
        onRequestRecommendations?.();
      } finally {
        if (!controller.signal.aborted) setDecisionLoading(false);
      }
    })();
    return () => controller.abort();
  }, [selected?.id, onRequestRecommendations]);

  // Legacy recommendation feed only backfills the panel when decisions failed.
  useEffect(() => {
    if (!decisionFailed || !recommendations?.length) return;
    setDecisionActions(
      recommendations.slice(0, 5).map((r, i) => ({
        id: r.id || `legacy-${i}`,
        title: r.title || `Recommendation ${i + 1}`,
        description: r.action_description || r.description || '',
        decision_type: 'operational',
        priority_level: r.priority || 'medium',
        implementation_priority: r.priority || 'medium',
        timeline_bucket: '7d',
        why: '',
        contributing_models: [],
        expected_benefits: [],
        estimated_water_saved_mcm: 0,
        population_protected: 0,
        estimated_cost_inr: 0,
        estimated_benefit_inr: 0,
        impact_score: 50 - i * 5,
        risk_reduction_score: 40 - i * 4,
        confidence: 0.7,
        optimization_score: 70 - i * 6,
        rank: i + 1,
      }))
    );
  }, [decisionFailed, recommendations]);

  // Model readiness never changes between renders of a dashboard session, so it
  // is fetched once instead of on every telemetry update.
  useEffect(() => {
    const controller = new AbortController();
    const init = { signal: controller.signal, timeoutMs: DASHBOARD_TIMEOUT_MS };
    (async () => {
      const [demandSt, demandMet, resSt, resMet, , , leakPerf] = await Promise.allSettled([
        fetchDemandStatus(init),
        fetchDemandMetrics(init),
        fetchReservoirStatus(init),
        fetchReservoirMetrics(init),
        fetchStressStatus(init),
        fetchDecisionStatus(init),
        apiGet<{
          success: boolean;
          model?: { metrics?: { test?: { f1?: number; accuracy?: number } } };
        }>('/model-performance/leak', init),
      ]);
      if (controller.signal.aborted) return;

      const leakTest = leakPerf.status === 'fulfilled' ? leakPerf.value.model?.metrics?.test : undefined;
      setModelReadiness({
        demandTrained: demandSt.status === 'fulfilled' && demandSt.value.trained,
        reservoirTrained: resSt.status === 'fulfilled' && resSt.value.trained,
        demandMetrics: demandMet.status === 'fulfilled' ? demandMet.value.metrics || {} : {},
        reservoirMetrics: resMet.status === 'fulfilled' ? resMet.value.metrics || {} : {},
        leakF1: typeof leakTest?.f1 === 'number' ? leakTest.f1 : null,
      });
    })();
    return () => controller.abort();
  }, []);

  const predictionCards = useMemo<PredictionCard[]>(() => {
    const demandTrained = modelReadiness?.demandTrained ?? false;
    const resTrained = modelReadiness?.reservoirTrained ?? false;
    const demandMetrics = modelReadiness?.demandMetrics ?? {};
    const resMetrics = modelReadiness?.reservoirMetrics ?? {};
    const leakF1 = modelReadiness?.leakF1 ?? null;

    const wsi = liveStress?.water_stress?.water_stress_index;
    const avgStorage =
      shortageRisks.length > 0
        ? shortageRisks.reduce((s, r) => s + r.currentLevel, 0) / shortageRisks.length
        : null;
    const demandMgd =
      liveStress?.demand?.daily_demand_mgd ??
      liveStress?.demand?.forecasted_demand_mgd ??
      liveStress?.demand?.predicted_demand_mgd ??
      null;

    const pending = (feed: keyof CommandCenterFeedStatus) =>
      feedStatus?.[feed] === 'loading' || feedStatus?.[feed] === 'idle';

    return [
      {
        id: 'demand',
        title: 'Demand Forecast',
        current: demandTrained ? (demandMgd != null ? `${demandMgd.toFixed(1)} MGD` : 'Model ready') : 'Untrained',
        confidence: demandTrained ? confidenceFromMetrics(demandMetrics, true) : 'Train required',
        trend: demandTrained ? formatForecastAccuracy(demandMetrics, 'MGD') : 'Municipal demand outlook',
        href: '/demand',
        tone: demandTrained ? 'success' : 'warning',
      },
      {
        id: 'reservoir',
        title: 'Reservoir Forecast',
        current: avgStorage == null ? (pending('shortageRisks') ? 'Loading...' : '-') : `${avgStorage.toFixed(1)}% avg`,
        confidence: resTrained ? confidenceFromMetrics(resMetrics, true) : 'Train required',
        trend: resTrained
          ? formatForecastAccuracy(resMetrics, 'pp')
          : `${shortageRisks.filter((r) => r.severity === 'critical').length} critical assets`,
        href: '/reservoir-forecast',
        tone: resTrained ? 'accent' : 'warning',
      },
      {
        id: 'stress',
        title: 'Water Stress',
        current: wsi == null ? (pending('waterStress') ? 'Loading...' : '-') : wsi.toFixed(1),
        confidence: liveStress?.water_stress?.stage || 'Fusion',
        trend: 'Multi-model fused index',
        href: '/water-stress',
        tone: (wsi ?? 0) > 60 ? 'danger' : (wsi ?? 0) > 40 ? 'warning' : 'success',
      },
      {
        id: 'leak',
        title: 'Leakage Risk',
        current: pending('alerts')
          ? 'Loading...'
          : feedStatus?.alerts === 'error' && alerts.length === 0
            ? '-'
            : String(alerts.filter((a) => a.status === 'active' || !a.status).length),
        confidence: leakF1 != null ? `F1 ${(leakF1 * 100).toFixed(1)}%` : 'Acoustic feed',
        trend:
          feedStatus?.alerts === 'error' && alerts.length === 0
            ? 'Alert feed unavailable'
            : 'Active network alerts',
        href: '/leak-detection',
        tone: alerts.some((a) => a.severity === 'critical') ? 'danger' : 'warning',
      },
      {
        id: 'climate',
        title: 'Climate Outlook',
        current: weather ? `${weather.temperature_c}°C` : pending('weather') ? 'Loading...' : '-',
        confidence: weather?.heatwave_warning ? 'Heatwatch' : 'Seasonal',
        trend: weather
          ? `Deficit ${weather.rainfall_deficit_pct}%`
          : pending('weather')
            ? 'Fetching climate feed'
            : 'No climate row',
        href: '/climate-risk',
        tone: weather?.heatwave_warning ? 'warning' : 'success',
      },
    ];
  }, [modelReadiness, liveStress, shortageRisks, alerts, weather, feedStatus]);

  useEffect(() => {
    const controller = new AbortController();
    (async () => {
      try {
        const res = await predictDemand(
          { value: 14, unit: 'days', include_history_days: 21 },
          { signal: controller.signal, timeoutMs: DASHBOARD_TIMEOUT_MS }
        );
        if (controller.signal.aborted) return;
        const series = res.data?.series || [];
        const points = series
          .slice(-16)
          .map((p) => {
            const raw = p.forecast ?? p.historical ?? p.rolling_avg;
            if (raw == null || Number.isNaN(Number(raw))) return null;
            return {
              label: String(p.date || '').slice(5) || String(p.period_label || ''),
              value: Number(Number(raw).toFixed(1)),
            };
          })
          .filter((p): p is { label: string; value: number } => p != null);
        if (points.length) setDemandChartSeries(points);

        // Latest observed and last forecast point, taken straight from the
        // model response so the demand KPIs never extrapolate a value.
        const lastOf = (key: 'historical' | 'forecast'): number | null => {
          for (let i = series.length - 1; i >= 0; i -= 1) {
            const raw = series[i]?.[key];
            if (raw != null && Number.isFinite(Number(raw))) return Number(raw);
          }
          return null;
        };
        setDemandKpi({ current: lastOf('historical'), forecast: lastOf('forecast') });
      } catch (error) {
        if (isAbortError(error) || controller.signal.aborted) return;
        /* leave demand series empty so charts show ChartEmpty, not synthetic data */
      }
    })();
    return () => controller.abort();
  }, []);

  const filteredRisks = useMemo(() => {
    if (!selected) return shortageRisks;
    if (selected.type === 'reservoir') {
      return shortageRisks.filter((r) => r.id === selected.id || r.name === selected.name);
    }
    return shortageRisks;
  }, [selected, shortageRisks]);

  const filteredAlerts = useMemo(() => {
    if (!selected) return alerts;
    if (selected.type === 'leak') return alerts.filter((a) => a.id === selected.id);
    return alerts;
  }, [selected, alerts]);

  const shortageUnavailable =
    (feedStatus?.shortageRisks === 'error' || feedStatus?.shortageRisks === 'loading') &&
    shortageRisks.length === 0;
  const alertsUnavailable =
    (feedStatus?.alerts === 'error' || feedStatus?.alerts === 'loading') && alerts.length === 0;
  const stressUnavailable =
    (feedStatus?.waterStress === 'error' || feedStatus?.waterStress === 'loading') && liveStress == null;

  const avgStorage =
    filteredRisks.length > 0
      ? filteredRisks.reduce((s, r) => s + r.currentLevel, 0) / filteredRisks.length
      : shortageRisks.length > 0
        ? shortageRisks.reduce((s, r) => s + r.currentLevel, 0) / shortageRisks.length
        : null;

  const criticalAlerts = alertsUnavailable
    ? null
    : alerts.filter((a) => (a.status === 'active' || !a.status) && a.severity === 'critical').length;

  const wsi = liveStress?.water_stress?.water_stress_index ?? null;
  const score =
    shortageUnavailable || alertsUnavailable || stressUnavailable
      ? null
      : securityScoreFrom(wsi, avgStorage ?? undefined, criticalAlerts ?? 0);
  const muni =
    score == null
      ? { label: 'Unavailable', tone: 'neutral' as const }
      : municipalStatus(score);
  // How many of the five weighted WSI inputs the backend positively reports as
  // usable this cycle. This replaces a former hardcoded "prediction confidence"
  // percentage: the fusion returns availability per component, so we show that
  // instead of a number no model produced.
  const fusionInputs = useMemo(() => {
    if (!liveStress) return null;
    const total = FUSION_COMPONENTS.length;
    const live = FUSION_COMPONENTS.filter((component) =>
      isComponentUsable(componentMetadata(liveStress, component)),
    ).length;
    return { live, total };
  }, [liveStress]);

  // A feed that failed or is still arriving renders a placeholder, never a zero
  // that would read like a measurement.
  const unavailable = useMemo<UnavailableSources>(() => {
    // A background refresh keeps its previous reading on screen, so "loading"
    // only replaces a KPI when there is nothing to show yet.
    const state = (
      feed: 'idle' | 'loading' | 'success' | 'error' | undefined,
      hasValue: boolean
    ): 'loading' | 'error' | undefined => {
      if (feed === 'error') return hasValue ? undefined : 'error';
      if ((feed === 'loading' || feed === 'idle') && !hasValue) return 'loading';
      return undefined;
    };
    return {
      shortageRisks: state(feedStatus?.shortageRisks, shortageRisks.length > 0),
      alerts: state(feedStatus?.alerts, alerts.length > 0),
      aquifers: state(feedStatus?.aquifers, aquifers.length > 0),
      weather: state(feedStatus?.weather, weather != null),
      waterStress: state(feedStatus?.waterStress, liveStress != null),
    };
  }, [feedStatus, shortageRisks, alerts, aquifers, weather, liveStress]);

  const kpis = useMemo(
    () =>
      deriveExecutiveKpis({
        shortageRisks: filteredRisks.length ? filteredRisks : shortageRisks,
        alerts: filteredAlerts.length ? filteredAlerts : alerts,
        aquifers,
        weather,
        waterStress: liveStress,
        unavailable,
        demandMgd: demandKpi.current,
        forecastDemandMgd: demandKpi.forecast,
        demandSeries: demandChartSeries,
        populationAtRisk:
          decisionActions[0]?.population_protected != null
            ? decisionActions.reduce((s, a) => s + (a.population_protected || 0), 0) / Math.max(1, decisionActions.length)
            : undefined,
      }),
    [
      filteredRisks,
      shortageRisks,
      filteredAlerts,
      alerts,
      aquifers,
      weather,
      liveStress,
      decisionActions,
      unavailable,
      demandKpi,
      demandChartSeries,
    ]
  );

  const charts = useMemo(
    () =>
      chartSeriesFrom({
        shortageRisks: filteredRisks.length ? filteredRisks : shortageRisks,
        alerts,
        weather,
        waterStress: liveStress,
        demandSeries: demandChartSeries,
        allowSynthetic: false,
      }),
    [filteredRisks, shortageRisks, alerts, weather, liveStress, demandChartSeries]
  );

  // Prefer the time the data was actually fetched over the render time.
  const lastUpdated = (lastUpdatedAt ? new Date(lastUpdatedAt) : new Date()).toLocaleTimeString([], {
    hour: '2-digit',
    minute: '2-digit',
  });

  const runScenario = async () => {
    setSimulating(true);
    setScenarioHint(null);
    try {
      const baseDemand =
        typeof liveStress?.demand?.daily_demand_mgd === 'number'
          ? (liveStress.demand.daily_demand_mgd as number)
          : 70;
      const baseTemp = weather?.temperature_c ?? 32;
      const baseDeficit = weather?.rainfall_deficit_pct ?? 0;
      const baseStorage = avgStorage || 45;

      const payload = await predictWaterIntelligence({
        rainfall_deficit_pct: baseDeficit + scenario.rainfallDeltaPct,
        temperature_c: baseTemp + scenario.temperatureDeltaC,
        daily_demand_mgd: baseDemand * (1 + scenario.demandIncreasePct / 100),
        population_thousands: 1200 * (1 + scenario.populationGrowthPct / 100),
        reservoir_capacity_pct: scenario.reservoirFailure ? Math.min(18, baseStorage * 0.35) : baseStorage,
        heatwave_warning: baseTemp + scenario.temperatureDeltaC >= 40,
      });
      setLiveStress(payload);
      const next = payload.water_stress?.water_stress_index;
      setScenarioHint(
        `Scenario applied · WSI ${next?.toFixed(1) ?? '-'} (${payload.water_stress?.stage || 'n/a'}). Map focus and KPIs refreshed.`
      );
    } catch (err) {
      setScenarioHint(err instanceof Error ? err.message : 'Scenario simulation failed');
    } finally {
      setSimulating(false);
    }
  };

  const exportPdf = () => {
    window.print();
  };

  const exportCsv = () => {
    const rows = [
      ['kpi', 'value'],
      ...kpis.map((k) => [k.label, k.value]),
      ['security_score', String(score)],
      ['wsi', wsi == null ? '' : String(wsi)],
    ];
    const csv = rows.map((r) => r.map((c) => `"${String(c).replace(/"/g, '""')}"`).join(',')).join('\n');
    const blob = new Blob([csv], { type: 'text/csv;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `aquamind-executive-${new Date().toISOString().slice(0, 10)}.csv`;
    a.click();
    URL.revokeObjectURL(url);
  };

  const focusScenario = () => {
    document.getElementById('scenario-simulation')?.scrollIntoView({ behavior: 'smooth', block: 'start' });
  };

  return (
    <div className="space-y-5 pb-8 print:space-y-4">
      {appliedIds.length > 0 ? (
        <div className="rounded-xl bg-[var(--am-success-soft)] px-4 py-2 text-[16px] text-[var(--am-success)]">
          Applied {appliedIds.length} recommendation{appliedIds.length > 1 ? 's' : ''} to the operational queue.
        </div>
      ) : null}

      <ExecutiveHeader
        securityScore={score}
        systemHealth={muni}
        fusionInputs={fusionInputs}
        lastUpdated={lastUpdated}
        municipalStatus={muni}
        criticalAlerts={criticalAlerts}
        regionLabel={selected?.name}
        onGenerateReport={onOpenReportModal}
        onScenarioFocus={focusScenario}
        onExportPdf={exportPdf}
        onRefresh={onRefresh}
      />

      <ExecutiveKpis kpis={kpis} />

      <div className="grid grid-cols-1 gap-4">
        <IntelligenceMap selected={selected} onSelect={setSelected} />
      </div>

      <PredictionCenter cards={predictionCards} />

      <DecisionPanel
        actions={decisionActions}
        loading={decisionLoading}
        failed={decisionFailed && decisionActions.length === 0}
        appliedIds={appliedIds}
        applyingId={applyingId}
        onApply={async (action) => {
          setApplyingId(action.id);
          try {
            // Persist operator intent; dashboard Apply is not a measured outcome.
            await apiPost('/api/v1/recommendations/feedback', {
              recommendation_id: action.id,
              action: 'accepted',
              source: 'decision',
              region_id: selected?.id,
              note: 'Applied from Operations Dashboard',
            });
            setAppliedIds((ids) => (ids.includes(action.id) ? ids : [...ids, action.id]));
          } finally {
            setApplyingId(null);
          }
        }}
        onCompare={() => {
          void compareStrategies({ horizon_days: 30 }).finally(() => navigate('/decision-intelligence'));
        }}
      />

      <ScenarioSimulation
        scenario={scenario}
        onChange={setScenario}
        onApply={() => void runScenario()}
        onReset={() => {
          setScenario(DEFAULT_SCENARIO);
          setLiveStress(waterStressProp);
          setScenarioHint(null);
        }}
        simulating={simulating}
        resultHint={scenarioHint}
      />

      <ExecutiveAnalytics {...charts} />

      <ReportCenter
        onGenerateReport={onOpenReportModal}
        onExportPdf={exportPdf}
        onExportCsv={exportCsv}
      />
    </div>
  );
};

export default CommandCenter;
