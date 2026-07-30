import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import {
  DecisionComparison,
  DecisionHeader,
  DecisionInsights,
  DecisionKpiCards,
  DecisionQueueTimeline,
  DecisionRecommendations,
  type DecisionStatus,
  type DecisionWorkspaceData,
} from '../components/decision';
import { QuickSummary } from '../components/ui/QuickSummary';
import {
  compareStrategies,
  fetchDecisionStatus,
  recommendDecisions,
} from '../services/decisionOptimization';

function buildDecisionSummary(data: DecisionWorkspaceData | null): string[] {
  if (!data?.recommended_actions?.length && !data?.top_recommendations?.length) {
    return [
      'Recommended actions will appear after generating a forecast for the selected region.',
      'Actions are ranked by impact, risk reduction, and implementation effort.',
    ];
  }

  const actions = data?.top_recommendations || data?.recommended_actions || [];
  const top = actions[0];
  const lines: string[] = [];
  const priority = data?.priority_level;
  const count = actions.length;

  if (top?.title) {
    lines.push(`Top recommended action: ${top.title}.`);
  }

  if (priority) {
    lines.push(`Overall priority level is ${String(priority).replace(/_/g, ' ').toLowerCase()}.`);
  }

  if (count > 0) {
    lines.push(`${count} prioritized action${count === 1 ? '' : 's'} ready for review.`);
  }

  return lines.slice(0, 3);
}

export const DecisionIntelligencePage: React.FC = () => {
  const [status, setStatus] = useState<DecisionStatus | null>(null);
  const [data, setData] = useState<DecisionWorkspaceData | null>(null);
  const [regionId, setRegionId] = useState('WARD-08');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);

  const refreshStatus = useCallback(async () => {
    setLoading(true);
    try {
      const st = await fetchDecisionStatus();
      setStatus(st);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unable to load decision status');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void refreshStatus();
  }, [refreshStatus]);

  const runOptimize = useCallback(async () => {
    setBusy(true);
    setError('');
    try {
      const [rec, cmp] = await Promise.all([
        recommendDecisions({ region_id: regionId, horizon_days: 30, max_actions: 12 }),
        compareStrategies({ region_id: regionId, horizon_days: 30, max_actions: 8 }),
      ]);
      setData({
        ...rec.data,
        scenario_comparison: cmp.data.scenario_comparison,
      });
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Decision optimization failed');
    } finally {
      setBusy(false);
    }
  }, [regionId]);

  useEffect(() => {
    if (!loading && !data && !busy) {
      void runOptimize();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [loading]);

  const upstream = status?.upstream || {};
  const demandReady = Boolean((upstream.water_demand as { trained?: boolean } | undefined)?.trained);
  const reservoirReady = Boolean(
    (upstream.reservoir_forecast as { trained?: boolean } | undefined)?.trained,
  );
  const stressReady = Boolean((upstream.water_stress as { ready?: boolean } | undefined)?.ready);

  const summaryLines = useMemo(() => buildDecisionSummary(data), [data]);

  return (
    <div className="space-y-5 pb-8">
      <DecisionHeader
        ready={Boolean(status?.ready)}
        loading={loading}
        moduleVersion={status?.module_version}
        demandReady={demandReady || data?.upstream_ready?.demand}
        reservoirReady={reservoirReady || data?.upstream_ready?.reservoir}
        stressReady={stressReady || data?.upstream_ready?.stress}
        onRefresh={() => void runOptimize()}
        refreshing={busy}
      />

      {error && (
        <div className="rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-[15px] text-red-800 dark:border-red-900 dark:bg-red-950/40 dark:text-red-200">
          {error}
        </div>
      )}

      <QuickSummary
        lines={summaryLines}
        technicalNote="Actions are ranked using demand, reservoir, and water stress predictions."
      />

      {!status?.ready && !loading ? (
        <section className="rounded-xl border border-amber-200 bg-amber-50 px-5 py-6 dark:border-amber-900 dark:bg-amber-950/30">
          <h2 className="text-base font-semibold text-amber-950 dark:text-amber-100">
            Upstream predictions limited
          </h2>
          <p className="mt-2 max-w-2xl text-[15px] text-amber-900/90 dark:text-amber-100/80">
            Train Demand and Reservoir models, then open Water Stress for richer recommendations.
            Baseline infrastructure actions are still available.
          </p>
          <div className="mt-4 flex flex-wrap gap-2">
            <Link to="/demand" className="rounded-lg bg-[#1e3a5f] px-4 py-2 text-[15px] font-semibold text-white">
              Demand Forecast
            </Link>
            <Link
              to="/reservoir-forecast"
              className="rounded-lg border border-slate-300 bg-white px-4 py-2 text-[15px] font-semibold text-slate-800"
            >
              Reservoir Forecast
            </Link>
            <Link
              to="/water-stress"
              className="rounded-lg border border-slate-300 bg-white px-4 py-2 text-[15px] font-semibold text-slate-800"
            >
              Water Stress
            </Link>
          </div>
        </section>
      ) : null}

      <div className="flex flex-wrap items-center gap-2 rounded-[16px] border border-[var(--am-border)] bg-[var(--am-bg-elevated)] px-4 py-3 shadow-[var(--am-shadow-sm)]">
        <label className="text-[14px] font-semibold uppercase tracking-wide text-[var(--am-text-tertiary)]">
          Region
        </label>
        <select
          value={regionId}
          onChange={(e) => setRegionId(e.target.value)}
          className="rounded-lg border border-[var(--am-border)] bg-[var(--am-bg)] px-3 py-2 text-[15px] text-[var(--am-text)]"
        >
          <option value="WARD-03">Ward 3</option>
          <option value="WARD-08">Ward 8</option>
          <option value="ZONE-NORTH">North Zone</option>
          <option value="ZONE-EAST">East Zone</option>
          <option value="DIST-CENTRAL">Central District</option>
          <option value="MUNI-PILOT">Pilot Municipality</option>
        </select>
        <button
          type="button"
          onClick={() => void runOptimize()}
          disabled={busy}
          className="rounded-lg bg-[var(--am-accent)] px-3 py-2 text-[15px] font-semibold text-white disabled:opacity-40"
        >
          Apply region
        </button>
      </div>

      <DecisionKpiCards
        outcomes={data?.expected_outcomes}
        priority={data?.priority_level}
        actionCount={data?.recommended_actions?.length}
      />

      {/* Balanced workspace: recommendations left, comparison + insights right (fills empty column) */}
      <div className="grid items-start gap-4 xl:grid-cols-12">
        <div className="min-w-0 xl:col-span-7">
          <DecisionRecommendations actions={data?.top_recommendations || data?.recommended_actions} />
        </div>
        <div className="flex min-w-0 flex-col gap-4 xl:sticky xl:top-4 xl:col-span-5 xl:self-start">
          <DecisionComparison comparison={data?.scenario_comparison} loading={busy} />
          <DecisionInsights
            layout="stack"
            reasoning={data?.ai_reasoning}
            outcomes={data?.expected_outcomes}
          />
        </div>
      </div>

      <DecisionQueueTimeline queue={data?.priority_queue} timeline={data?.operational_timeline} />
    </div>
  );
};
