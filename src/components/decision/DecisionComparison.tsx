import React, { useMemo } from 'react';
import {
  Bar,
  BarChart,
  CartesianGrid,
  LabelList,
  Legend,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';
import type { DecisionWorkspaceData, StrategySide } from './types';
import { SkeletonChart } from '../ui/Skeleton';
import { EmptyState } from '../ui/EmptyState';

type Props = {
  comparison?: DecisionWorkspaceData['scenario_comparison'] | null;
  loading?: boolean;
};

function formatInr(n?: number | null) {
  if (n == null || Number.isNaN(n)) return '-';
  if (Math.abs(n) >= 1_000_000) return `₹${(n / 1_000_000).toFixed(1)}M`;
  if (Math.abs(n) >= 1_000) return `₹${(n / 1_000).toFixed(0)}K`;
  return `₹${n.toFixed(0)}`;
}

const tipStyle = {
  background: 'var(--am-bg-elevated)',
  border: '1px solid var(--am-border)',
  borderRadius: 12,
  fontSize: 14,
  color: 'var(--am-text)',
  boxShadow: 'var(--am-shadow-md)',
};

export const DecisionComparison: React.FC<Props> = ({ comparison, loading }) => {
  const chartData = useMemo(() => {
    if (!comparison) return [];
    // Compare live system state (WSI / people at risk), not incremental action zeros.
    return [
      {
        metric: 'WSI',
        Baseline: comparison.current.projected_wsi ?? 0,
        Optimized: comparison.optimized.projected_wsi ?? 0,
      },
      {
        metric: 'Pop at risk (k)',
        Baseline: (comparison.current.population_at_risk ?? 0) / 1000,
        Optimized: (comparison.optimized.population_at_risk ?? 0) / 1000,
      },
      {
        metric: 'Water saved',
        Baseline: comparison.current.water_saved_mcm,
        Optimized: comparison.optimized.water_saved_mcm,
      },
      {
        metric: 'Cost (₹L)',
        Baseline: comparison.current.estimated_cost_inr / 100_000,
        Optimized: comparison.optimized.estimated_cost_inr / 100_000,
      },
    ];
  }, [comparison]);

  if (loading) return <SkeletonChart height={260} />;

  if (!comparison) {
    return (
      <EmptyState
        className="min-h-[220px]"
        title="No comparison yet"
        description="Run strategy comparison to see baseline vs optimized impact."
      />
    );
  }

  const { current, optimized, delta } = comparison;

  return (
    <section className="am-soft-card p-5">
      <div className="mb-4 flex flex-wrap items-end justify-between gap-2">
        <div>
          <h3 className="text-[17px] font-semibold text-[var(--am-text)]">Scenario comparison</h3>
          <p className="mt-0.5 text-[15px] text-[var(--am-text-secondary)]">
            Baseline (no new actions) vs ranked action plan
          </p>
        </div>
        <div className="flex flex-wrap gap-3 text-[14px] text-[var(--am-text-secondary)]">
          <span>
            Δ water{' '}
            <strong className="tabular-nums text-[var(--am-text)]">{delta.water_saved_mcm.toFixed(1)} MCM</strong>
          </span>
          <span>
            Δ risk <strong className="tabular-nums text-[var(--am-text)]">{delta.risk_reduction.toFixed(1)}</strong>
          </span>
          <span>
            Δ pop{' '}
            <strong className="tabular-nums text-[var(--am-text)]">{delta.population_protected.toLocaleString()}</strong>
          </span>
          <span>
            Cost <strong className="tabular-nums text-[var(--am-text)]">{formatInr(delta.estimated_cost_inr)}</strong>
          </span>
        </div>
      </div>

      <div className="mb-4 grid gap-3 sm:grid-cols-2">
        <StrategyCard side={current} featured={false} />
        <StrategyCard side={optimized} featured />
      </div>

      <div className="h-[220px] w-full">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={chartData} margin={{ top: 8, right: 8, left: 0, bottom: 4 }} barGap={6}>
            <CartesianGrid stroke="var(--am-divider)" strokeDasharray="3 6" vertical={false} />
            <XAxis
              dataKey="metric"
              tick={{ fill: 'var(--am-text-tertiary)', fontSize: 13 }}
              axisLine={false}
              tickLine={false}
              interval={0}
            />
            <YAxis
              tick={{ fill: 'var(--am-text-tertiary)', fontSize: 13 }}
              width={36}
              axisLine={false}
              tickLine={false}
            />
            <Tooltip contentStyle={tipStyle} />
            <Legend />
            <Bar dataKey="Baseline" fill="#8E8E93" radius={[6, 6, 0, 0]} maxBarSize={36} animationDuration={500}>
              <LabelList
                dataKey="Baseline"
                position="top"
                formatter={(v: number) => v.toFixed(1)}
                style={{ fontSize: 14, fill: 'var(--am-text-tertiary)' }}
              />
            </Bar>
            <Bar dataKey="Optimized" fill="#007AFF" radius={[6, 6, 0, 0]} maxBarSize={36} animationDuration={500}>
              <LabelList
                dataKey="Optimized"
                position="top"
                formatter={(v: number) => v.toFixed(1)}
                style={{ fontSize: 14, fill: 'var(--am-text-tertiary)' }}
              />
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>
      <p className="mt-2 text-[14px] text-[var(--am-text-tertiary)]">
        Why baseline water saved / cost show 0: that side means “take no new action,” so there is no
        incremental savings or spend yet. WSI and population-at-risk show the live system if you stay
        on current operations; the optimized bars show estimated plan impact.
      </p>
    </section>
  );
};

function StrategyCard({
  side,
  featured,
}: {
  side: StrategySide;
  featured: boolean;
}) {
  const isBaseline = !featured;
  return (
    <div
      className={`rounded-[16px] border p-4 ${
        featured
          ? 'border-[var(--am-accent)]/25 bg-[var(--am-accent-soft)]'
          : 'border-[var(--am-border)] bg-[var(--am-bg-muted)]/60'
      }`}
    >
      <p className="text-[14px] font-semibold uppercase tracking-wide text-[var(--am-text-tertiary)]">{side.label}</p>
      <p className="mt-1 text-[15px] text-[var(--am-text-secondary)]">{side.description}</p>
      <dl className="mt-3 grid grid-cols-2 gap-2 text-[15px]">
        <div>
          <dt className="text-[var(--am-text-tertiary)]">Projected WSI</dt>
          <dd className="mt-0.5 font-semibold tabular-nums text-[var(--am-text)]">
            {side.projected_wsi != null ? side.projected_wsi.toFixed(1) : '—'}
          </dd>
        </div>
        <div>
          <dt className="text-[var(--am-text-tertiary)]">Risk stage</dt>
          <dd className="mt-0.5 font-semibold tabular-nums text-[var(--am-text)]">{side.risk_label || '—'}</dd>
        </div>
        {isBaseline ? (
          <>
            <div>
              <dt className="text-[var(--am-text-tertiary)]">Population at risk</dt>
              <dd className="mt-0.5 font-semibold tabular-nums text-[var(--am-text)]">
                {(side.population_at_risk ?? 0).toLocaleString()}
              </dd>
            </div>
            <div>
              <dt className="text-[var(--am-text-tertiary)]">Storage</dt>
              <dd className="mt-0.5 font-semibold tabular-nums text-[var(--am-text)]">
                {side.projected_storage_pct != null ? `${side.projected_storage_pct.toFixed(0)}%` : '—'}
              </dd>
            </div>
            <div className="col-span-2 rounded-[10px] bg-[var(--am-bg-elevated)]/70 px-2.5 py-2 text-[13px] text-[var(--am-text-tertiary)]">
              New-action impact: water saved 0 · cost ₹0 (no interventions queued)
            </div>
          </>
        ) : (
          <>
            <div>
              <dt className="text-[var(--am-text-tertiary)]">Water saved</dt>
              <dd className="mt-0.5 font-semibold tabular-nums text-[var(--am-text)]">
                {side.water_saved_mcm.toFixed(1)} MCM
              </dd>
            </div>
            <div>
              <dt className="text-[var(--am-text-tertiary)]">Risk reduction</dt>
              <dd className="mt-0.5 font-semibold tabular-nums text-[var(--am-text)]">
                {side.risk_reduction.toFixed(1)}
              </dd>
            </div>
            <div>
              <dt className="text-[var(--am-text-tertiary)]">Population protected</dt>
              <dd className="mt-0.5 font-semibold tabular-nums text-[var(--am-text)]">
                {side.population_protected.toLocaleString()}
              </dd>
            </div>
            <div>
              <dt className="text-[var(--am-text-tertiary)]">Cost</dt>
              <dd className="mt-0.5 font-semibold tabular-nums text-[var(--am-text)]">
                {formatInr(side.estimated_cost_inr)}
              </dd>
            </div>
          </>
        )}
      </dl>
    </div>
  );
}
