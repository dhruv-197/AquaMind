import React from 'react';
import type { ForecastSummaryData } from './types';
import { formatMgd, formatPct } from './utils';
import { StatusBadge } from '../ui/Badge';

type Props = {
  summary?: ForecastSummaryData | null;
  capacityMgd?: number | null;
  recommendation?: string | null;
};

function Progress({ value, tone = 'blue' }: { value?: number | null; tone?: 'blue' | 'amber' }) {
  const pct = Math.max(0, Math.min(100, value ?? 0));
  return (
    <div className="mt-1.5 h-2 w-full overflow-hidden rounded-full bg-[var(--am-bg-muted)]">
      <div
        className="h-full rounded-full transition-all duration-500"
        style={{
          width: `${pct}%`,
          background: tone === 'amber' ? 'var(--am-warning)' : 'var(--am-accent)',
        }}
      />
    </div>
  );
}

export const ForecastSummary: React.FC<Props> = ({ summary, capacityMgd, recommendation }) => {
  const util = summary?.capacity_utilization_pct;
  const conf = summary?.confidence != null ? summary.confidence * 100 : null;
  const risk = summary?.expected_shortage_risk || '-';
  const rec =
    recommendation ||
    (util != null && util >= 90
      ? 'Prioritize demand management and peak shaving before capacity breach.'
      : (summary?.growth_pct ?? 0) > 5
        ? 'Plan supply augmentation; demand growth is elevated across the horizon.'
        : 'Maintain monitoring cadence; forecast remains within operable headroom.');

  return (
    <section className="flex h-full flex-col rounded-[16px] border border-[var(--am-border)] bg-[var(--am-bg-elevated)] shadow-[var(--am-shadow-sm)]">
      <header className="border-b border-[var(--am-divider)] px-5 py-4">
        <h3 className="text-[17px] font-semibold text-[var(--am-text)]">Forecast summary</h3>
        <p className="mt-0.5 text-[15px] text-[var(--am-text-secondary)]">Peak, usage, growth, and recommended next step</p>
      </header>

      <div className="grid flex-1 grid-cols-2 gap-3 p-5">
        <Metric label="Peak day" value={summary?.peak_date || '-'} />
        <Metric label="Peak demand" value={formatMgd(summary?.predicted_peak_demand_mgd, 1)} />
        <Metric
          label="Growth"
          value={
            summary?.growth_pct == null
              ? '-'
              : `${summary.growth_pct >= 0 ? '+' : ''}${summary.growth_pct.toFixed(1)}%`
          }
        />
        <Metric label="Avg forecast" value={formatMgd(summary?.average_forecast_mgd, 1)} />
      </div>

      <div className="space-y-3 border-t border-[var(--am-divider)] px-5 py-4">
        <div>
          <div className="flex items-center justify-between text-[15px]">
            <span className="text-[var(--am-text-secondary)]">Water System Usage</span>
            <span className="tabular-nums font-semibold text-[var(--am-text)]">{formatPct(util)}</span>
          </div>
          <Progress value={util} tone={(util ?? 0) >= 90 ? 'amber' : 'blue'} />
          <p className="mt-1 text-[14px] text-[var(--am-text-tertiary)]">Maximum Capacity {formatMgd(capacityMgd, 1)}</p>
        </div>

        <div className="flex items-center justify-between text-[15px]">
          <span className="text-[var(--am-text-secondary)]">Shortage risk</span>
          <StatusBadge status={risk} />
        </div>

        <div>
          <div className="flex items-center justify-between text-[15px]">
            <span className="text-[var(--am-text-secondary)]">Prediction Confidence</span>
            <span className="tabular-nums font-semibold text-[var(--am-text)]">
              {conf == null ? '-' : `${Math.round(conf)}%`}
            </span>
          </div>
          <Progress value={conf} />
        </div>
      </div>

      <div className="border-t border-[var(--am-divider)] px-5 py-4">
        <p className="text-[16px] font-semibold uppercase tracking-wide text-[var(--am-text-tertiary)]">
          Recommendation
        </p>
        <p className="mt-1.5 text-[16px] leading-relaxed text-[var(--am-text)]">{rec}</p>
      </div>
    </section>
  );
};

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-[14px] border border-[var(--am-border)] bg-[var(--am-bg-muted)]/60 p-3">
      <p className="text-[16px] font-semibold uppercase tracking-wide text-[var(--am-text-tertiary)]">{label}</p>
      <p className="mt-1 text-[17px] font-semibold tabular-nums text-[var(--am-text)]">{value}</p>
    </div>
  );
}
