import React, { useState } from 'react';
import { Link } from 'react-router-dom';
import { Badge, StatusBadge } from '../../ui/Badge';
import { Button } from '../../ui/Button';
import { SkeletonTable } from '../../ui/Skeleton';
import { SectionTitle } from './ExecutiveKpis';
import type { DecisionAction } from '../../decision/types';
import { riskTone } from '../../../design-system/tokens';

type Props = {
  actions: DecisionAction[];
  loading?: boolean;
  failed?: boolean;
  appliedIds?: string[];
  applyingId?: string | null;
  onApply: (action: DecisionAction) => void | Promise<void>;
  onCompare: () => void;
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

export const DecisionPanel: React.FC<Props> = ({
  actions,
  loading,
  failed,
  appliedIds = [],
  applyingId = null,
  onApply,
  onCompare,
}) => {
  const top = actions.slice(0, 5);
  const featured = top[0];
  const rest = top.slice(1);
  const [statusMessage, setStatusMessage] = useState('');

  const handleApply = async (action: DecisionAction) => {
    setStatusMessage('');
    try {
      await onApply(action);
      setStatusMessage(`“${action.title}” marked as applied. Open Recommended Actions to Accept / Defer formally.`);
    } catch (err) {
      setStatusMessage(err instanceof Error ? err.message : 'Could not apply this recommendation.');
    }
  };

  return (
    <section className="am-soft-card p-5 sm:p-6">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
        <SectionTitle
          title="Recommended Actions"
          subtitle="Ranked action plan by estimated impact, risk reduction, and implementation effort."
        />
        <div className="flex flex-wrap gap-2">
          <Button variant="secondary" onClick={onCompare}>
            Compare Scenario
          </Button>
          <Link to="/decision-intelligence">
            <Button variant="ghost">Full workspace</Button>
          </Link>
        </div>
      </div>

      {statusMessage ? (
        <p className="mt-3 text-[15px] text-[var(--am-text-secondary)]" role="status" aria-live="polite">
          {statusMessage}
        </p>
      ) : null}

      {loading ? (
        <div className="mt-5">
          <SkeletonTable rows={4} />
        </div>
      ) : top.length === 0 ? (
        <p className="mt-6 text-[16px] text-[var(--am-text-secondary)]">
          {failed
            ? 'Recommendations unavailable right now. Use Refresh above or open the full workspace to retry.'
            : 'No ranked actions yet. Upstream forecasts may still be training.'}
        </p>
      ) : (
        <div className="mt-5 space-y-4">
          {featured ? (
            <article className="relative overflow-hidden rounded-[18px] border border-[var(--am-accent)]/20 bg-[var(--am-accent-soft)] p-5">
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div className="min-w-0">
                  <p className="text-[14px] font-semibold uppercase tracking-[0.08em] text-[var(--am-accent)]">
                    Top recommendation
                  </p>
                  <h3 className="mt-1 text-[19px] font-semibold tracking-tight text-[var(--am-text)]">
                    {featured.title}
                  </h3>
                  <p className="mt-2 max-w-3xl text-[16px] leading-relaxed text-[var(--am-text-secondary)]">
                    {featured.description || featured.why || featured.ai_reasoning?.why}
                  </p>
                </div>
                <div className="flex h-7 shrink-0 items-center gap-2">
                  {appliedIds.includes(featured.id) ? <StatusBadge status="Applied" kind="success" /> : null}
                  <StatusBadge status={featured.priority_level} />
                </div>
              </div>
              <div className="mt-4 grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-6">
                {[
                  ['Priority score', String(Math.round(featured.optimization_score ?? featured.impact_score ?? 0))],
                  ['Water saved', `${(featured.estimated_water_saved_mcm ?? 0).toFixed(1)} MCM`],
                  ['Population', (featured.population_protected ?? 0).toLocaleString()],
                  ['Risk ↓', String(Math.round(featured.risk_reduction_score ?? 0))],
                  ['Cost', formatInr(featured.estimated_cost_inr)],
                  ['Effort', effortLabel(featured.estimated_cost_inr)],
                ].map(([k, v]) => (
                  <div key={k} className="rounded-[14px] bg-[var(--am-bg-elevated)]/80 px-3 py-2.5">
                    <p className="text-[16px] font-semibold uppercase tracking-wide text-[var(--am-text-tertiary)]">
                      {k}
                    </p>
                    <p className="mt-1 text-[17px] font-semibold tabular-nums text-[var(--am-text)]">{v}</p>
                  </div>
                ))}
              </div>
              <div className="mt-4 flex flex-wrap gap-2">
                <Button
                  onClick={() => void handleApply(featured)}
                  disabled={applyingId === featured.id}
                  loading={applyingId === featured.id}
                  aria-label={
                    appliedIds.includes(featured.id)
                      ? `Re-apply ${featured.title}`
                      : `Apply ${featured.title}`
                  }
                >
                  {appliedIds.includes(featured.id) ? 'Applied' : 'Apply'}
                </Button>
                <Link to="/decision-intelligence">
                  <Button variant="secondary">View details</Button>
                </Link>
              </div>
            </article>
          ) : null}

          {rest.length > 0 ? (
            <div className="overflow-x-auto">
              <table className="am-table w-full min-w-[820px] border-collapse text-left text-[16px]">
                <thead>
                  <tr>
                    {['Recommendation', 'Priority', 'Impact', 'Water saved', 'Population', 'Risk ↓', 'Effort', 'Actions'].map(
                      (h) => (
                        <th
                          key={h}
                          className="border-b border-[var(--am-divider)] px-3 py-3 text-[14px] font-semibold uppercase tracking-[0.06em] text-[var(--am-text-secondary)]"
                        >
                          {h}
                        </th>
                      ),
                    )}
                  </tr>
                </thead>
                <tbody>
                  {rest.map((a) => {
                    const tone = riskTone(a.priority_level);
                    const applied = appliedIds.includes(a.id);
                    return (
                      <tr key={a.id} className="transition-colors hover:bg-[var(--am-bg-muted)]">
                        <td className="border-b border-[var(--am-divider)] px-3 py-3.5">
                          <p className="font-semibold text-[var(--am-text)]">{a.title}</p>
                          <p className="mt-0.5 line-clamp-1 text-[15px] text-[var(--am-text-secondary)]">
                            {a.description}
                          </p>
                        </td>
                        <td className="border-b border-[var(--am-divider)] px-3 py-3.5">
                          <Badge tone={tone === 'neutral' ? 'accent' : tone}>
                            {Math.round(a.optimization_score ?? a.impact_score ?? 0)}
                          </Badge>
                        </td>
                        <td className="border-b border-[var(--am-divider)] px-3 py-3.5 tabular-nums">
                          {Math.round(a.impact_score ?? 0)}
                        </td>
                        <td className="border-b border-[var(--am-divider)] px-3 py-3.5 tabular-nums">
                          {a.estimated_water_saved_mcm?.toFixed(1) ?? '-'} MCM
                        </td>
                        <td className="border-b border-[var(--am-divider)] px-3 py-3.5 tabular-nums">
                          {(a.population_protected ?? 0).toLocaleString()}
                        </td>
                        <td className="border-b border-[var(--am-divider)] px-3 py-3.5 tabular-nums">
                          {Math.round(a.risk_reduction_score ?? 0)}
                        </td>
                        <td className="border-b border-[var(--am-divider)] px-3 py-3.5 text-[var(--am-text-secondary)]">
                          {effortLabel(a.estimated_cost_inr)}
                        </td>
                        <td className="border-b border-[var(--am-divider)] px-3 py-3.5">
                          <div className="flex flex-wrap gap-1.5">
                            <Button
                              size="sm"
                              onClick={() => void handleApply(a)}
                              disabled={applyingId === a.id}
                              loading={applyingId === a.id}
                              aria-label={applied ? `Re-apply ${a.title}` : `Apply ${a.title}`}
                            >
                              {applied ? 'Applied' : 'Apply'}
                            </Button>
                            <Link to="/decision-intelligence">
                              <Button size="sm" variant="ghost">
                                Details
                              </Button>
                            </Link>
                          </div>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          ) : null}
        </div>
      )}
    </section>
  );
};
