import React from 'react';
import type { DecisionWorkspaceData } from './types';

type Props = {
  reasoning?: string[];
  outcomes?: DecisionWorkspaceData['expected_outcomes'] | null;
  /** stack = fill a sidebar column; grid = two-up footer */
  layout?: 'grid' | 'stack';
};

/** Soften technical reasoning into operator-friendly English. */
function plainReason(raw: string): string {
  let t = raw;
  t = t.replace(/Demand forecast shows\s*([\d.]+)%\s*change across the horizon\.?/i, (_, n) => {
    const v = Number(n);
    if (Math.abs(v) < 1) return 'Demand is expected to stay roughly steady over the planning window.';
    if (v > 0) return `Demand is expected to rise by about ${Math.round(v)}% over the planning window.`;
    return `Demand is expected to ease by about ${Math.round(Math.abs(v))}% over the planning window.`;
  });
  t = t.replace(
    /Water Stress Index is\s*([\d.]+)\s*\(([A-Z_]+)\)\s*with population impact\s*([\d,]+)\.?/i,
    (_, wsi, label, pop) => {
      const level = String(label).toLowerCase().replace(/_/g, ' ');
      return `Water Stress Index is ${level} (about ${Math.round(Number(wsi))}), affecting roughly ${pop} people.`;
    },
  );
  t = t.replace(
    /Top action '([^']+)' ranked #?\d+\s*\(score\s*[\d.]+\)\s*because:\s*(.+)/i,
    (_, title, why) => {
      let reason = String(why)
        .replace(/capacity utilisation\s*([\d.]+)%/i, 'systems already using about $1% of capacity')
        .replace(/Demand growth\s*([\d.]+)%/i, 'demand growing about $1%')
        .replace(/\s{2,}/g, ' ')
        .trim();
      return `Priority action: ${title}. ${reason}`;
    },
  );
  t = t.replace(/score\s*[\d.]+/gi, '');
  t = t.replace(/\s{2,}/g, ' ').trim();
  if (t && !/[.!?]$/.test(t)) t += '.';
  return t;
}

export const DecisionInsights: React.FC<Props> = ({ reasoning, outcomes, layout = 'grid' }) => {
  const shell = layout === 'stack' ? 'space-y-4' : 'grid gap-4 lg:grid-cols-2';

  return (
    <div className={shell}>
      <section className="am-soft-card">
        <header className="border-b border-[var(--am-divider)] px-5 py-3.5">
          <h3 className="text-[17px] font-semibold text-[var(--am-text)]">Expected outcomes</h3>
          <p className="mt-0.5 text-[15px] text-[var(--am-text-secondary)]">
            Combined impact of the optimized action plan
          </p>
        </header>
        <dl className="grid grid-cols-2 gap-3 p-4 sm:p-5">
          <Outcome
            label="Water saved"
            value={
              outcomes?.estimated_water_saved_mcm == null
                ? '-'
                : `${outcomes.estimated_water_saved_mcm.toFixed(1)} MCM`
            }
          />
          <Outcome
            label="Population protected"
            value={outcomes?.population_protected?.toLocaleString() ?? '-'}
          />
          <Outcome
            label="Net benefit"
            value={
              outcomes?.net_benefit_inr == null
                ? '-'
                : `₹${(outcomes.net_benefit_inr / 1_000_000).toFixed(1)}M`
            }
          />
          <Outcome
            label="Risk reduction"
            value={
              outcomes?.average_risk_reduction == null
                ? '-'
                : `${Math.round(Number(outcomes.average_risk_reduction))}`
            }
          />
        </dl>
      </section>

      <section className="am-soft-card">
        <header className="border-b border-[var(--am-divider)] px-5 py-3.5">
          <h3 className="text-[17px] font-semibold text-[var(--am-text)]">AI reasoning</h3>
          <p className="mt-0.5 text-[15px] text-[var(--am-text-secondary)]">
            Why this plan ranks above the current strategy
          </p>
        </header>
        <ul className="space-y-2.5 p-4 text-[16px] leading-relaxed text-[var(--am-text-secondary)] sm:p-5">
          {(reasoning || []).length ? (
            reasoning!.map((t, i) => (
              <li key={i} className="flex gap-2">
                <span className="mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full bg-[var(--am-accent)]" aria-hidden />
                <span>{plainReason(t)}</span>
              </li>
            ))
          ) : (
            <li className="text-[var(--am-text-tertiary)]">
              Generate recommendations to see plain-language reasoning.
            </li>
          )}
        </ul>
      </section>
    </div>
  );
};

function Outcome({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-[14px] border border-[var(--am-border)] bg-[var(--am-bg-muted)]/60 p-3">
      <dt className="text-[16px] font-semibold uppercase tracking-wide text-[var(--am-text-tertiary)]">{label}</dt>
      <dd className="mt-1 text-[17px] font-semibold tabular-nums text-[var(--am-text)]">{value}</dd>
    </div>
  );
}
