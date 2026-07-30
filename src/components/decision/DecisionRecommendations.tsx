import React, { useState } from 'react';
import type { DecisionAction } from './types';
import { StatusBadge } from '../ui/Badge';
import { Button } from '../ui/Button';
import { EmptyState } from '../ui/EmptyState';

type Props = {
  actions?: DecisionAction[];
};

function effortLabel(cost?: number) {
  if (cost == null) return '-';
  if (cost < 500_000) return 'Low';
  if (cost < 5_000_000) return 'Medium';
  return 'High';
}

function formatInr(n?: number) {
  if (n == null || Number.isNaN(n)) return '-';
  if (Math.abs(n) >= 1_000_000) return `₹${(n / 1_000_000).toFixed(1)}M`;
  if (Math.abs(n) >= 1_000) return `₹${(n / 1_000).toFixed(0)}K`;
  return `₹${n.toFixed(0)}`;
}

export const DecisionRecommendations: React.FC<Props> = ({ actions }) => {
  const [openId, setOpenId] = useState<string | null>(null);
  const list = actions || [];
  const featured = list[0];
  const rest = list.slice(1);

  return (
    <section className="space-y-4">
      <header>
        <h3 className="am-section-title text-[19px]">Top recommendations</h3>
        <p className="mt-1 text-[16px] text-[var(--am-text-secondary)]">
          Ranked by impact, risk reduction, population benefit, and water saved
        </p>
      </header>

      {list.length === 0 ? (
        <EmptyState
          title="No recommendations yet"
          description="Generate decisions from upstream forecasts to populate the priority queue."
        />
      ) : (
        <>
          {featured ? (
            <article className="relative overflow-hidden rounded-[20px] border border-[var(--am-accent)]/25 bg-[var(--am-accent-soft)] p-5 shadow-[var(--am-shadow-md)]">
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div className="min-w-0 flex-1">
                  <p className="text-[14px] font-semibold uppercase tracking-[0.08em] text-[var(--am-accent)]">
                    Flagship recommendation · #{featured.rank ?? 1}
                  </p>
                  <h4 className="mt-1 text-[19px] font-semibold tracking-tight text-[var(--am-text)] sm:text-[22px]">
                    {featured.title}
                  </h4>
                  <p className="mt-2 text-[16px] leading-relaxed text-[var(--am-text-secondary)]">
                    {featured.description}
                  </p>
                </div>
                <StatusBadge status={featured.priority_level} />
              </div>

              <div className="mt-4 grid grid-cols-2 gap-2.5 sm:grid-cols-4">
                {[
                  ['Priority score', String(Math.round(featured.optimization_score ?? featured.impact_score ?? 0))],
                  ['Water saved', `${(featured.estimated_water_saved_mcm ?? 0).toFixed(1)} MCM`],
                  ['Population', (featured.population_protected ?? 0).toLocaleString()],
                  ['Cost', formatInr(featured.estimated_cost_inr)],
                  ['Effort', effortLabel(featured.estimated_cost_inr)],
                  ['Confidence', featured.confidence != null ? `${Math.round(featured.confidence * 100)}%` : '-'],
                  ['Risk ↓', String(Math.round(featured.risk_reduction_score ?? 0))],
                  [
                    'Benefit',
                    (featured.expected_benefits?.[0] || featured.ai_reasoning?.why || featured.why || '-').slice(0, 48),
                  ],
                ].map(([k, v]) => (
                  <div key={k} className="rounded-[12px] bg-[var(--am-bg-elevated)]/85 px-2.5 py-2">
                    <p className="text-[16px] font-semibold uppercase tracking-wide text-[var(--am-text-tertiary)]">{k}</p>
                    <p className="mt-0.5 truncate text-[16px] font-semibold text-[var(--am-text)]" title={String(v)}>
                      {v}
                    </p>
                  </div>
                ))}
              </div>

              <div className="mt-3 rounded-[14px] border border-[var(--am-border)] bg-[var(--am-bg-elevated)]/70 p-3.5">
                <p className="text-[14px] font-semibold uppercase tracking-wide text-[var(--am-text-tertiary)]">
                  Reasoning
                </p>
                <p className="mt-1 text-[16px] leading-relaxed text-[var(--am-text-secondary)]">
                  {featured.ai_reasoning?.why || featured.why || featured.description}
                </p>
              </div>

              <div className="mt-3">
                <Button
                  variant="tertiary"
                  size="sm"
                  onClick={() => setOpenId(openId === featured.id ? null : featured.id)}
                >
                  {openId === featured.id ? 'Hide benefits' : 'Show expected benefits'}
                </Button>
                {openId === featured.id && (featured.expected_benefits || []).length ? (
                  <ul className="mt-3 list-disc space-y-1 pl-5 text-[16px] text-[var(--am-text-secondary)]">
                    {featured.expected_benefits!.map((b, i) => (
                      <li key={i}>{b}</li>
                    ))}
                  </ul>
                ) : null}
              </div>
            </article>
          ) : null}

          {rest.length > 0 ? (
            <ul className="divide-y divide-[var(--am-divider)] overflow-hidden rounded-[20px] border border-[var(--am-border)] bg-[var(--am-bg-elevated)] shadow-[var(--am-shadow-md)]">
              {rest.map((a) => {
                const open = openId === a.id;
                return (
                  <li key={a.id} className="px-4 py-3.5 sm:px-5">
                    <button
                      type="button"
                      className="w-full rounded-[8px] text-left focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--am-accent)]"
                      onClick={() => setOpenId(open ? null : a.id)}
                      aria-expanded={open}
                    >
                      <div className="flex flex-wrap items-center gap-x-2 gap-y-1">
                        <span className="font-mono text-[14px] text-[var(--am-text-tertiary)]">#{a.rank ?? '-'}</span>
                        <h4 className="text-[16px] font-semibold text-[var(--am-text)]">{a.title}</h4>
                        <StatusBadge status={a.priority_level} />
                        <span className="ml-auto shrink-0 text-[15px] font-semibold text-[var(--am-accent)]">
                          {open ? 'Hide' : 'Why'}
                        </span>
                      </div>
                      <p className="mt-1 text-[15px] text-[var(--am-text-secondary)]">{a.description}</p>
                      <div className="mt-2 flex flex-wrap gap-x-3 gap-y-1 text-[14px] tabular-nums text-[var(--am-text-secondary)]">
                        <span>Water {(a.estimated_water_saved_mcm ?? 0).toFixed(1)} MCM</span>
                        <span>Pop {(a.population_protected ?? 0).toLocaleString()}</span>
                        <span>Cost {formatInr(a.estimated_cost_inr)}</span>
                        <span>Score {a.optimization_score ?? '-'}</span>
                      </div>
                    </button>
                    {open ? (
                      <div className="mt-3 rounded-[14px] border border-[var(--am-border)] bg-[var(--am-bg-muted)]/60 p-3 text-[15px] text-[var(--am-text-secondary)]">
                        <p className="font-semibold text-[var(--am-text)]">AI reasoning</p>
                        <p className="mt-1">{a.ai_reasoning?.why || a.why}</p>
                        <p className="mt-2 text-[var(--am-text-tertiary)]">
                          Confidence: {a.confidence != null ? `${Math.round(a.confidence * 100)}%` : '-'} · Effort{' '}
                          {effortLabel(a.estimated_cost_inr)}
                        </p>
                      </div>
                    ) : null}
                  </li>
                );
              })}
            </ul>
          ) : null}
        </>
      )}
    </section>
  );
};
