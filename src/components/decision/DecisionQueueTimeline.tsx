import React from 'react';
import type { DecisionWorkspaceData, TimelineBucket } from './types';

type Props = {
  queue?: DecisionWorkspaceData['priority_queue'];
  timeline?: TimelineBucket[];
};

export const DecisionQueueTimeline: React.FC<Props> = ({ queue, timeline }) => {
  return (
    <div className="grid gap-4 lg:grid-cols-2">
      <section className="am-soft-card overflow-hidden">
        <header className="border-b border-[var(--am-divider)] px-5 py-3.5">
          <h3 className="text-[17px] font-semibold text-[var(--am-text)]">Priority queue</h3>
          <p className="mt-0.5 text-[15px] text-[var(--am-text-secondary)]">
            Ranked actions ready for operations
          </p>
        </header>
        <ol className="divide-y divide-[var(--am-divider)]">
          {(queue || []).length === 0 ? (
            <li className="px-5 py-6 text-[16px] text-[var(--am-text-tertiary)]">No queued actions.</li>
          ) : (
            (queue || []).map((q) => (
              <li key={q.id} className="flex items-center justify-between gap-3 px-5 py-3 text-[16px]">
                <div className="min-w-0">
                  <p className="truncate font-medium text-[var(--am-text)]">
                    <span className="mr-2 font-mono text-[14px] text-[var(--am-text-tertiary)]">#{q.rank}</span>
                    {q.title}
                  </p>
                  <p className="mt-0.5 text-[14px] uppercase tracking-wide text-[var(--am-text-tertiary)]">
                    {q.decision_type.replace(/_/g, ' ')} · {q.priority_level.replace(/_/g, ' ')}
                  </p>
                </div>
                <span className="shrink-0 font-mono text-[15px] font-semibold tabular-nums text-[var(--am-text)]">
                  {q.optimization_score}
                </span>
              </li>
            ))
          )}
        </ol>
      </section>

      <section className="am-soft-card overflow-hidden">
        <header className="border-b border-[var(--am-divider)] px-5 py-3.5">
          <h3 className="text-[17px] font-semibold text-[var(--am-text)]">Operational timeline</h3>
          <p className="mt-0.5 text-[15px] text-[var(--am-text-secondary)]">
            Today · 7 days · 30 days · 6 months
          </p>
        </header>
        <div className="grid gap-3 p-4 sm:grid-cols-2 sm:p-5">
          {(timeline || []).map((bucket) => (
            <div
              key={bucket.bucket}
              className="rounded-[14px] border border-[var(--am-border)] bg-[var(--am-bg-muted)]/50 p-3"
            >
              <div className="mb-2 flex items-center justify-between gap-2">
                <p className="text-[14px] font-semibold uppercase tracking-wide text-[var(--am-text-tertiary)]">
                  {bucket.label}
                </p>
                <span className="font-mono text-[14px] tabular-nums text-[var(--am-text-tertiary)]">
                  {bucket.count}
                </span>
              </div>
              {bucket.actions.length === 0 ? (
                <p className="text-[15px] text-[var(--am-text-tertiary)]">No actions in this window</p>
              ) : (
                <ul className="space-y-1.5">
                  {bucket.actions.map((a) => (
                    <li
                      key={`${bucket.bucket}-${a.id}`}
                      className="rounded-lg bg-[var(--am-bg-elevated)] px-2.5 py-1.5 text-[15px] text-[var(--am-text-secondary)]"
                    >
                      {a.title}
                    </li>
                  ))}
                </ul>
              )}
            </div>
          ))}
        </div>
      </section>
    </div>
  );
};
