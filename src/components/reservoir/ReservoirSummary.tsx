import React from 'react';
import type { ReservoirSummaryData, ExecutiveRecommendation } from './types';
import { formatPct } from '../demand/utils';
import { StatusBadge } from '../ui/Badge';

type Props = {
  summary?: ReservoirSummaryData | null;
  recommendations?: ExecutiveRecommendation[];
};

export const ReservoirSummary: React.FC<Props> = ({ summary, recommendations }) => {
  const conf = summary?.confidence != null ? summary.confidence * 100 : null;
  const risk = summary?.risk_label || '-';

  return (
    <section className="flex h-full flex-col rounded-[20px] border border-[var(--am-border)] bg-[var(--am-bg-elevated)] shadow-[var(--am-shadow-md)]">
      <header className="border-b border-[var(--am-divider)] px-5 py-4">
        <h3 className="text-[17px] font-semibold text-[var(--am-text)]">Forecast summary</h3>
        <p className="mt-0.5 text-[15px] text-[var(--am-text-secondary)]">
          Storage, risk, confidence, and executive guidance
        </p>
      </header>

      <div className="grid flex-1 grid-cols-2 gap-3 p-5">
        <Metric label="Forecasted %" value={formatPct(summary?.forecasted_storage_pct, 1)} />
        <Metric
          label="Storage MCM"
          value={summary?.forecasted_storage_mcm == null ? '-' : summary.forecasted_storage_mcm.toFixed(1)}
        />
        <div className="col-span-2 rounded-[14px] border border-[var(--am-border)] bg-[var(--am-bg-muted)]/60 p-3">
          <p className="text-[16px] font-semibold uppercase tracking-wide text-[var(--am-text-tertiary)]">
            Remaining usable storage
          </p>
          <p className="mt-1 text-[19px] font-semibold tabular-nums text-[var(--am-text)]">
            {summary?.remaining_usable_storage_mcm == null
              ? '-'
              : `${summary.remaining_usable_storage_mcm.toFixed(1)} MCM`}
          </p>
        </div>
      </div>

      <div className="space-y-3 border-t border-[var(--am-divider)] px-5 py-4 text-[15px]">
        <Row
          label="Storage change"
          value={
            summary?.storage_change_pct == null
              ? '-'
              : `${summary.storage_change_pct >= 0 ? '+' : ''}${summary.storage_change_pct.toFixed(1)} pp`
          }
        />
        <Row label="Days to critical" value={String(summary?.days_to_critical ?? '-')} />
        <div className="flex items-center justify-between">
          <span className="text-[var(--am-text-secondary)]">Risk</span>
          <StatusBadge status={risk} />
        </div>
        <Row label="Prediction Confidence" value={conf == null ? '-' : `${conf.toFixed(0)}%`} />
      </div>

      {recommendations && recommendations.length > 0 ? (
        <div className="border-t border-[var(--am-divider)] px-5 py-4">
          <p className="mb-2 text-[16px] font-semibold uppercase tracking-wide text-[var(--am-text-tertiary)]">
            Executive recommendations
          </p>
          <ul className="space-y-1.5">
            {recommendations.slice(0, 4).map((r) => (
              <li key={r.id} className="text-[15px] leading-snug text-[var(--am-text-secondary)]">
                {r.text}
              </li>
            ))}
          </ul>
        </div>
      ) : null}
    </section>
  );
};

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-[14px] border border-[var(--am-border)] bg-[var(--am-bg-muted)]/60 p-3">
      <p className="text-[16px] font-semibold uppercase tracking-wide text-[var(--am-text-tertiary)]">{label}</p>
      <p className="mt-1 text-[18px] font-semibold tabular-nums text-[var(--am-text)]">{value}</p>
    </div>
  );
}

function Row({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-center justify-between">
      <span className="text-[var(--am-text-secondary)]">{label}</span>
      <span className="font-semibold tabular-nums text-[var(--am-text)]">{value}</span>
    </div>
  );
}
