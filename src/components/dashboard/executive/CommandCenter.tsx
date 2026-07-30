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
import { predictWaterIntelligence } from '../../../services/telemetry';
import { recommendDecisions, compareStrategies } from '../../../services/decisionOptimization';
import { fetchDemandStatus, fetchDemandMetrics, predictDemand } from '../../../services/demandForecast';
import { fetchReservoirStatus, fetchReservoirMetrics } from '../../../services/reservoirForecast';
import { fetchStressStatus } from '../../../services/waterStressForecast';
import { fetchDecisionStatus } from '../../../services/decisionOptimization';
import { apiGet } from '../../../services/apiClient';
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
} from './derive';

const DEFAULT_SCENARIO: ScenarioState = {
  rainfallDeltaPct: 0,
  temperatureDeltaC: 0,
  demandIncreasePct: 0,
  populationGrowthPct: 0,
  reservoirFailure: false,
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
};

function fmtDate(iso?: string | null) {
  if (!iso) return '-';
  try {
    return new Date(iso).toLocaleString();
  } catch {
    return '-';
  }
}

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
}) => {
  const navigate = useNavigate();
  const [selected, setSelected] = useState<SelectedRegion>(null);
  const [scenario, setScenario] = useState<ScenarioState>(DEFAULT_SCENARIO);
  const [simulating, setSimulating] = useState(false);
  const [scenarioHint, setScenarioHint] = useState<string | null>(null);
  const [liveStress, setLiveStress] = useState<WaterIntelligencePayload | null>(waterStressProp);
  const [decisionActions, setDecisionActions] = useState<DecisionAction[]>([]);
  const [decisionLoading, setDecisionLoading] = useState(true);
  const [appliedIds, setAppliedIds] = useState<string[]>([]);
  const [predictionCards, setPredictionCards] = useState<PredictionCard[]>([]);
  const [demandChartSeries, setDemandChartSeries] = useState<Array<{ label: string; value: number }>>([]);

  useEffect(() => {
    setLiveStress(waterStressProp);
  }, [waterStressProp]);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      setDecisionLoading(true);
      try {
        const res = await recommendDecisions({
          region_id: selected?.id?.startsWith('REG') ? selected.id : undefined,
          horizon_days: 30,
          max_actions: 8,
        });
        if (cancelled) return;
        const actions =
          res.data?.top_recommendations ||
          res.data?.recommended_actions ||
          [];
        setDecisionActions(actions);
      } catch {
        if (!cancelled) {
          // Fallback from legacy recommendation feed
          setDecisionActions(
            (recommendations || []).slice(0, 5).map((r, i) => ({
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
        }
      } finally {
        if (!cancelled) setDecisionLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [selected?.id, recommendations]);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const [demandSt, demandMet, resSt, resMet, stressSt, decSt, leakPerf] = await Promise.allSettled([
          fetchDemandStatus(),
          fetchDemandMetrics(),
          fetchReservoirStatus(),
          fetchReservoirMetrics(),
          fetchStressStatus(),
          fetchDecisionStatus(),
          apiGet<{
            success: boolean;
            model?: { metrics?: { test?: { f1?: number; accuracy?: number }; validation?: { f1?: number } } };
          }>('/model-performance/leak'),
        ]);

        if (cancelled) return;

        const demandTrained = demandSt.status === 'fulfilled' && demandSt.value.trained;
        const resTrained = resSt.status === 'fulfilled' && resSt.value.trained;
        const demandMetrics =
          demandMet.status === 'fulfilled' ? (demandMet.value.metrics || {}) : {};
        const resMetrics = resMet.status === 'fulfilled' ? (resMet.value.metrics || {}) : {};

        const leakTest =
          leakPerf.status === 'fulfilled' ? leakPerf.value.model?.metrics?.test : undefined;
        const leakF1 = typeof leakTest?.f1 === 'number' ? leakTest.f1 : null;
        const leakAcc = typeof leakTest?.accuracy === 'number' ? leakTest.accuracy : null;

        const wsi = liveStress?.water_stress?.water_stress_index;
        const avgStorage =
          shortageRisks.length > 0
            ? shortageRisks.reduce((s, r) => s + r.currentLevel, 0) / shortageRisks.length
            : null;

        const demandMgdRaw = (liveStress?.demand as Record<string, unknown> | undefined)?.daily_demand_mgd;
        const demandMgd = typeof demandMgdRaw === 'number' ? demandMgdRaw : null;

        const demandAccLabel = formatForecastAccuracy(demandMetrics, 'MGD');
        const resAccLabel = formatForecastAccuracy(resMetrics, 'pp');

        setPredictionCards([
          {
            id: 'demand',
            title: 'Demand Forecast',
            current: demandTrained
              ? demandMgd != null
                ? `${demandMgd.toFixed(1)} MGD`
                : 'Model ready'
              : 'Untrained',
            confidence: demandTrained ? confidenceFromMetrics(demandMetrics, true) : 'Train required',
            trend: demandTrained ? demandAccLabel : 'Municipal demand outlook',
            href: '/demand',
            tone: demandTrained ? 'success' : 'warning',
          },
          {
            id: 'reservoir',
            title: 'Reservoir Forecast',
            current: avgStorage == null ? '-' : `${avgStorage.toFixed(1)}% avg`,
            confidence: resTrained ? confidenceFromMetrics(resMetrics, true) : 'Train required',
            trend: resTrained
              ? resAccLabel
              : `${shortageRisks.filter((r) => r.severity === 'critical').length} critical assets`,
            href: '/reservoir-forecast',
            tone: resTrained ? 'accent' : 'warning',
          },
          {
            id: 'stress',
            title: 'Water Stress',
            current: wsi == null ? '-' : wsi.toFixed(1),
            confidence: liveStress?.water_stress?.stage || 'Fusion',
            trend: 'Multi-model fused index',
            href: '/water-stress',
            tone: (wsi ?? 0) > 60 ? 'danger' : (wsi ?? 0) > 40 ? 'warning' : 'success',
          },
          {
            id: 'leak',
            title: 'Leakage Risk',
            current: String(alerts.filter((a) => a.status === 'active' || !a.status).length),
            confidence: leakF1 != null ? `F1 ${(leakF1 * 100).toFixed(1)}%` : 'Acoustic feed',
            trend: 'Active network alerts',
            href: '/leak-detection',
            tone: alerts.some((a) => a.severity === 'critical') ? 'danger' : 'warning',
          },
          {
            id: 'climate',
            title: 'Climate Outlook',
            current: weather ? `${weather.temperature_c}°C` : '-',
            confidence: weather?.heatwave_warning ? 'Heatwatch' : 'Seasonal',
            trend: weather ? `Deficit ${weather.rainfall_deficit_pct}%` : 'No climate row',
            href: '/climate-risk',
            tone: weather?.heatwave_warning ? 'warning' : 'success',
          },
        ]);
      } catch {
        /* prediction cards stay previous */
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [liveStress, shortageRisks, alerts, weather]);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const res = await predictDemand({ value: 14, unit: 'days', include_history_days: 21 });
        if (cancelled) return;
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
      } catch {
        /* keep synthetic fallback in chartSeriesFrom */
      }
    })();
    return () => {
      cancelled = true;
    };
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

  const avgStorage =
    filteredRisks.length > 0
      ? filteredRisks.reduce((s, r) => s + r.currentLevel, 0) / filteredRisks.length
      : shortageRisks.length > 0
        ? shortageRisks.reduce((s, r) => s + r.currentLevel, 0) / shortageRisks.length
        : 0;

  const criticalAlerts = alerts.filter(
    (a) => (a.status === 'active' || !a.status) && a.severity === 'critical'
  ).length;

  const wsi = liveStress?.water_stress?.water_stress_index ?? null;
  const score = securityScoreFrom(wsi, avgStorage, criticalAlerts);
  const muni = municipalStatus(score);
  const aiConfidence =
    typeof liveStress?.water_stress?.components?.demand?.weight === 'number'
      ? 0.72 + (liveStress?.water_stress ? 0.12 : 0)
      : 0.68;

  const kpis = useMemo(
    () =>
      deriveExecutiveKpis({
        shortageRisks: filteredRisks.length ? filteredRisks : shortageRisks,
        alerts: filteredAlerts.length ? filteredAlerts : alerts,
        aquifers,
        weather,
        waterStress: liveStress,
        populationAtRisk:
          decisionActions[0]?.population_protected != null
            ? decisionActions.reduce((s, a) => s + (a.population_protected || 0), 0) / Math.max(1, decisionActions.length)
            : undefined,
      }),
    [filteredRisks, shortageRisks, filteredAlerts, alerts, aquifers, weather, liveStress, decisionActions]
  );

  const charts = useMemo(
    () =>
      chartSeriesFrom({
        shortageRisks: filteredRisks.length ? filteredRisks : shortageRisks,
        alerts,
        weather,
        waterStress: liveStress,
        demandSeries: demandChartSeries,
      }),
    [filteredRisks, shortageRisks, alerts, weather, liveStress, demandChartSeries]
  );

  const lastUpdated = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });

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
        aiConfidence={aiConfidence}
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
        onApply={(action) => {
          setAppliedIds((ids) => (ids.includes(action.id) ? ids : [...ids, action.id]));
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
