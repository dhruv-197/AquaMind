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
import type { DecisionWorkspaceData } from './types';
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
    return [
      {
        metric: 'Water saved',
        Current: comparison.current.water_saved_mcm,
        Optimized: comparison.optimized.water_saved_mcm,
      },
      {
        metric: 'Risk ↓',
        Current: comparison.current.risk_reduction,
        Optimized: comparison.optimized.risk_reduction,
      },
      {
        metric: 'Pop (k)',
        Current: comparison.current.population_protected / 1000,
        Optimized: comparison.optimized.population_protected / 1000,
      },
      {
        metric: 'Cost (₹L)',
        Current: comparison.current.estimated_cost_inr / 100_000,
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
        description="Run strategy comparison to see Current vs Optimized impact."
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
            Current strategy vs optimized decision plan
          </p>
        </div>
        <div className="flex flex-wrap gap-3 text-[14px] text-[var(--am-text-secondary)]">
          <span>
            Δ water <strong className="tabular-nums text-[var(--am-text)]">{delta.water_saved_mcm.toFixed(1)} MCM</strong>
          </span>
          <span>
            Δ risk <strong className="tabular-nums text-[var(--am-text)]">{delta.risk_reduction.toFixed(1)}</strong>
          </span>
          <span>
            Δ pop <strong className="tabular-nums text-[var(--am-text)]">{delta.population_protected.toLocaleString()}</strong>
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
            <Bar dataKey="Current" fill="#8E8E93" radius={[6, 6, 0, 0]} maxBarSize={36} animationDuration={500}>
              <LabelList
                dataKey="Current"
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
        "Current" is the zero-intervention baseline. It shows 0 by definition (no new action taken), so every bar
        is the full impact the optimized plan adds.
      </p>
    </section>
  );
};

function StrategyCard({
  side,
  featured,
}: {
  side: NonNullable<DecisionWorkspaceData['scenario_comparison']>['current'];
  featured: boolean;
}) {
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
          <dt className="text-[var(--am-text-tertiary)]">Water saved</dt>
          <dd className="mt-0.5 font-semibold tabular-nums text-[var(--am-text)]">{side.water_saved_mcm.toFixed(1)} MCM</dd>
        </div>
        <div>
          <dt className="text-[var(--am-text-tertiary)]">Risk reduction</dt>
          <dd className="mt-0.5 font-semibold tabular-nums text-[var(--am-text)]">{side.risk_reduction.toFixed(1)}</dd>
        </div>
        <div>
          <dt className="text-[var(--am-text-tertiary)]">Population</dt>
          <dd className="mt-0.5 font-semibold tabular-nums text-[var(--am-text)]">{side.population_protected.toLocaleString()}</dd>
        </div>
        <div>
          <dt className="text-[var(--am-text-tertiary)]">Cost</dt>
          <dd className="mt-0.5 font-semibold tabular-nums text-[var(--am-text)]">{formatInr(side.estimated_cost_inr)}</dd>
        </div>
      </dl>
    </div>
  );
}
