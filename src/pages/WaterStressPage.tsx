import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { Link } from 'react-router-dom';
import {
  StressCharts,
  StressComparisonPanel,
  StressHeader,
  StressInsightsPanel,
  StressKpiCards,
  StressMap,
  StressScenarioPanel,
  buildStressEvidenceReport,
  type StressScenario,
  type StressStatus,
  type StressWorkspaceData,
} from '../components/stress';
import { QuickSummary } from '../components/ui/QuickSummary';
import { Button } from '../components/ui/Button';
import { downloadText } from '../components/demand/utils';
import {
  fetchStressStatus,
  predictStress,
  simulateStress,
} from '../services/waterStressForecast';

function buildStressSummary(data: StressWorkspaceData | null): string[] {
  if (!data?.summary && !data?.series?.length) {
    return [
      'Water stress forecast is ready. Select a region to view the combined score.',
      'Current stress, predicted levels, and population impact will appear here.',
    ];
  }

  const lines: string[] = [];
  const current = data?.summary?.current_stress;
  const predicted = data?.summary?.predicted_stress;
  const risk = String(data?.summary?.risk_label ?? data?.risk_label ?? 'unknown').toLowerCase();
  const population = data?.summary?.population_affected;
  const region = data?.region?.name;

  if (data?.has_scenario && data.summary?.baseline_stress != null && predicted != null) {
    const delta = predicted - data.summary.baseline_stress;
    lines.push(
      `${region ? `${region}: ` : ''}Scenario projects WSI ${predicted.toFixed(1)} vs baseline ${data.summary.baseline_stress.toFixed(1)} (${delta >= 0 ? '+' : ''}${delta.toFixed(1)}).`,
    );
  } else if (current != null && predicted != null) {
    const delta = predicted - current;
    if (Math.abs(delta) < 3) {
      lines.push(
        `${region ? `${region}: ` : ''}Water stress is expected to remain near ${predicted.toFixed(1)} over the forecast range.`,
      );
    } else if (delta > 0) {
      lines.push(
        `${region ? `${region}: ` : ''}Water stress may rise from ${current.toFixed(1)} to ${predicted.toFixed(1)}.`,
      );
    } else {
      lines.push(
        `${region ? `${region}: ` : ''}Water stress may ease from ${current.toFixed(1)} to ${predicted.toFixed(1)}.`,
      );
    }
  } else if (current != null) {
    lines.push(`Current Water Stress Index is ${current.toFixed(1)} (0-100 scale).`);
  }

  if (risk === 'low' || risk === 'minimal' || risk === 'stable') {
    lines.push('Overall system health is stable with low stress risk.');
  } else if (risk === 'moderate' || risk === 'medium' || risk === 'watch') {
    lines.push('Moderate stress detected. Monitor demand and storage closely.');
  } else if (risk !== 'unknown' && risk !== '-') {
    lines.push(`Elevated stress risk (${risk}) requires operational attention.`);
  }

  if (population != null && population > 0) {
    lines.push(`An estimated ${population.toLocaleString()} people may be affected at current stress levels.`);
  }

  return lines.slice(0, 3);
}

const EMPTY_SCENARIO: StressScenario = {
  rainfall_delta_pct: 0,
  population_delta_pct: 0,
  demand_delta_pct: 0,
  temperature_delta_c: 0,
  reservoir_delta_pct: 0,
};

export const WaterStressPage: React.FC = () => {
  const [status, setStatus] = useState<StressStatus | null>(null);
  const [data, setData] = useState<StressWorkspaceData | null>(null);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [scenario, setScenario] = useState<StressScenario>(EMPTY_SCENARIO);
  const [activePresetId, setActivePresetId] = useState<string | null>(null);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const abortRef = useRef<AbortController | null>(null);

  const cancelInFlight = () => {
    abortRef.current?.abort();
    abortRef.current = new AbortController();
    return abortRef.current.signal;
  };

  const refreshStatus = useCallback(async () => {
    setLoading(true);
    try {
      const st = await fetchStressStatus();
      setStatus(st);
      setSelectedId((prev) => prev || st.regions?.[0]?.region_id || 'WARD-08');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unable to load stress status');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void refreshStatus();
    return () => abortRef.current?.abort();
  }, [refreshStatus]);

  const runPredict = useCallback(
    async (regionId?: string | null) => {
      const rid = regionId ?? selectedId;
      const signal = cancelInFlight();
      setBusy(true);
      setError('');
      try {
        const res = await predictStress(
          {
            region_id: rid || undefined,
            horizon_days: 30,
            include_all_regions: true,
          },
          { signal },
        );
        if (signal.aborted) return;
        setData(res.data);
        if (res.data.region?.region_id) setSelectedId(res.data.region.region_id);
        setScenario(EMPTY_SCENARIO);
        setActivePresetId('baseline');
      } catch (err) {
        if (signal.aborted) return;
        setError(err instanceof Error ? err.message : 'Prediction failed');
      } finally {
        if (!signal.aborted) setBusy(false);
      }
    },
    [selectedId],
  );

  useEffect(() => {
    if (!loading && selectedId && !data && !busy) {
      void runPredict(selectedId);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [loading, selectedId]);

  const runSimulate = async () => {
    const signal = cancelInFlight();
    setBusy(true);
    setError('');
    setActivePresetId(null);
    try {
      const res = await simulateStress(
        {
          region_id: selectedId || undefined,
          horizon_days: 30,
          scenario,
        },
        { signal },
      );
      if (signal.aborted) return;
      setData(res.data);
    } catch (err) {
      if (signal.aborted) return;
      setError(err instanceof Error ? err.message : 'Simulation failed');
    } finally {
      if (!signal.aborted) setBusy(false);
    }
  };

  const runPreset = async (presetId: string) => {
    if (presetId === 'baseline') {
      setScenario(EMPTY_SCENARIO);
      setActivePresetId('baseline');
      void runPredict();
      return;
    }
    const signal = cancelInFlight();
    setBusy(true);
    setError('');
    setActivePresetId(presetId);
    try {
      const res = await simulateStress(
        {
          region_id: selectedId || undefined,
          horizon_days: 30,
          preset_id: presetId,
        },
        { signal },
      );
      if (signal.aborted) return;
      setData(res.data);
      setScenario({ ...EMPTY_SCENARIO, ...(res.data.scenario || {}) });
    } catch (err) {
      if (signal.aborted) return;
      setError(err instanceof Error ? err.message : 'Preset simulation failed');
    } finally {
      if (!signal.aborted) setBusy(false);
    }
  };

  const onSelectRegion = useCallback(
    (id: string) => {
      setSelectedId(id);
      void runPredict(id);
    },
    [runPredict],
  );

  const exportEvidence = () => {
    if (!data) return;
    const text = buildStressEvidenceReport({
      generatedAt: data.generated_at || new Date().toISOString(),
      regionName: data.region?.name,
      regionId: data.region?.region_id,
      moduleVersion: status?.module_version || data.module_version,
      hasScenario: Boolean(data.has_scenario),
      projectionDisclaimer: data.projection_disclaimer,
      baselineWsi: data.summary?.baseline_stress,
      scenarioWsi: data.summary?.predicted_stress ?? data.water_stress_index,
      baselineRisk: data.baseline_risk_label || data.summary?.risk_label,
      scenarioRisk: data.risk_label || data.summary?.risk_label,
      deltaVsBaseline: data.summary?.delta_vs_baseline,
      expectedShortageDate: data.expected_stress_date || data.summary?.expected_shortage_date,
      baselineExpectedShortageDate: data.baseline_expected_stress_date,
      components: data.components,
      baselineComponents: data.baseline_components,
      actions: data.recommended_actions,
      insights: data.executive_insights,
      scenario: data.scenario as Record<string, number | string | undefined | null> | undefined,
      demandEffect: data.components?.demand?.detail,
      reservoirEffect: data.components?.reservoir?.detail,
    });
    downloadText(
      `aquamind-stress-evidence-${data.region?.region_id || 'region'}-${Date.now()}.txt`,
      text,
      'text/plain;charset=utf-8',
    );
  };

  const upstream = data?.upstream_status;
  const demandTrained =
    upstream?.demand_trained ??
    Boolean((status?.upstream?.water_demand as { trained?: boolean } | undefined)?.trained);
  const reservoirTrained =
    upstream?.reservoir_trained ??
    Boolean((status?.upstream?.reservoir_forecast as { trained?: boolean } | undefined)?.trained);

  const summaryLines = useMemo(() => buildStressSummary(data), [data]);

  return (
    <div className="space-y-4 pb-8">
      <StressHeader
        ready={Boolean(status?.ready)}
        loading={loading}
        moduleVersion={status?.module_version}
        demandTrained={demandTrained}
        reservoirTrained={reservoirTrained}
        regionName={data?.region?.name}
      />

      <div className="flex flex-wrap items-center justify-between gap-2">
        <p className="text-[14px] text-[var(--am-text-tertiary)]" aria-live="polite">
          {data?.generated_at
            ? `Fusion generated ${new Date(data.generated_at).toLocaleString()}`
            : busy
              ? 'Updating fusion…'
              : 'Awaiting fusion run'}
        </p>
        <Button
          variant="secondary"
          size="sm"
          onClick={exportEvidence}
          disabled={!data}
          aria-label="Export water stress evidence brief"
        >
          Export evidence brief
        </Button>
      </div>

      {error && (
        <div
          className="rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-[15px] text-red-800 dark:border-red-900 dark:bg-red-950/40 dark:text-red-200"
          role="alert"
        >
          {error}
        </div>
      )}

      <QuickSummary
        lines={summaryLines}
        technicalNote="Combines demand, reservoir storage, and climate signals into one score."
      />

      {!status?.ready && !loading ? (
        <section className="rounded-xl border border-amber-200 bg-amber-50 px-5 py-6 dark:border-amber-900 dark:bg-amber-950/30">
          <h2 className="text-base font-semibold text-amber-950 dark:text-amber-100">
            Upstream models not trained
          </h2>
          <p className="mt-2 max-w-2xl text-[15px] text-amber-900/90 dark:text-amber-100/80">
            Water Stress Intelligence fuses Demand Forecast and Reservoir Level Forecast.
            Train those models for full accuracy. Fusion still runs with placeholders.
          </p>
          <div className="mt-4 flex flex-wrap gap-2">
            <Link to="/demand" className="rounded-lg bg-[#1e3a5f] px-4 py-2 text-[15px] font-semibold text-white">
              Open Demand Forecast
            </Link>
            <Link
              to="/reservoir-forecast"
              className="rounded-lg border border-slate-300 bg-white px-4 py-2 text-[15px] font-semibold text-slate-800"
            >
              Open Reservoir Forecast
            </Link>
            <button
              type="button"
              onClick={() => void runPredict()}
              className="rounded-lg border border-amber-300 px-4 py-2 text-[15px] font-semibold text-amber-950 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-amber-600"
            >
              Run with placeholders
            </button>
          </div>
        </section>
      ) : null}

      <StressMap
        regions={data?.map_regions || []}
        selectedId={selectedId}
        onSelect={onSelectRegion}
      />

      <StressKpiCards
        summary={data?.summary}
        riskLabel={data?.risk_label}
        series={data?.series}
      />

      <StressComparisonPanel data={data} />

      <div className="grid items-stretch gap-4 xl:grid-cols-12">
        <div className="xl:col-span-8 2xl:col-span-9">
          <StressCharts
            series={data?.series || []}
            comparison={data?.regional_comparison}
            hasScenario={Boolean(data?.has_scenario)}
            loading={busy}
          />
        </div>
        <div className="xl:col-span-4 2xl:col-span-3">
          <StressScenarioPanel
            scenario={scenario}
            onChange={setScenario}
            onSimulate={() => void runSimulate()}
            onReset={() => {
              setScenario(EMPTY_SCENARIO);
              setActivePresetId('baseline');
              void runPredict();
            }}
            presets={data?.what_if_presets || status?.what_if_presets}
            onPreset={(id) => void runPreset(id)}
            busy={busy}
            deltaVsBaseline={data?.summary?.delta_vs_baseline}
            activePresetId={activePresetId}
          />
        </div>
      </div>

      <StressInsightsPanel
        insights={data?.executive_insights}
        actions={data?.recommended_actions}
        components={data?.components}
        baselineComponents={data?.baseline_components}
        baselineWsi={data?.summary?.baseline_stress}
        currentWsi={data?.summary?.predicted_stress ?? data?.water_stress_index}
        generatedAt={data?.generated_at}
        hasScenario={Boolean(data?.has_scenario)}
        regionId={data?.region?.region_id}
      />
    </div>
  );
};
