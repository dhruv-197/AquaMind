import React, { useMemo, useState } from 'react';
import { Badge } from '../../ui/Badge';
import { SectionTitle } from './ExecutiveKpis';
import type { TimelineItem } from './derive';

type Props = { items: TimelineItem[] };

const TABS = [
  { id: 'today' as const, label: 'Today' },
  { id: '7d' as const, label: 'Next 7 Days' },
  { id: '30d' as const, label: 'Next 30 Days' },
];

export const OperationalTimeline: React.FC<Props> = ({ items }) => {
  const [tab, setTab] = useState<'today' | '7d' | '30d'>('today');
  const filtered = useMemo(() => items.filter((i) => i.when === tab), [items, tab]);

  return (
    <section className="rounded-[var(--am-radius-xl)] bg-[var(--am-bg-elevated)] p-5 shadow-[var(--am-shadow-md)]">
      <SectionTitle
        title="Operational Timeline"
        subtitle="Upcoming shortages, depletion windows, high-risk regions, and queued actions."
      />
      <div className="mt-4 flex gap-1 rounded-xl bg-[var(--am-bg-muted)] p-1">
        {TABS.map((t) => (
          <button
            key={t.id}
            type="button"
            onClick={() => setTab(t.id)}
            className={`flex-1 rounded-lg px-3 py-2 text-[16px] font-semibold transition-colors ${
              tab === t.id
                ? 'bg-[var(--am-bg-elevated)] text-[var(--am-text)] shadow-[var(--am-shadow-sm)]'
                : 'text-[var(--am-text-secondary)]'
            }`}
          >
            {t.label}
          </button>
        ))}
      </div>
      <ul className="mt-4 max-h-[340px] space-y-2 overflow-y-auto">
        {filtered.length === 0 ? (
          <li className="rounded-[14px] bg-[var(--am-bg-muted)] p-4 text-[16px] text-[var(--am-text-secondary)]">
            No events in this window.
          </li>
        ) : (
          filtered.map((item) => (
            <li key={item.id} className="rounded-[14px] bg-[var(--am-bg-muted)] p-3.5">
              <div className="flex items-start justify-between gap-3">
                <div className="min-w-0">
                  <p className="text-[16px] font-semibold text-[var(--am-text)]">{item.title}</p>
                  <p className="mt-1 text-[15px] leading-relaxed text-[var(--am-text-secondary)]">{item.detail}</p>
                </div>
                <div className="flex shrink-0 flex-col items-end gap-1">
                  <Badge tone={item.severity === 'neutral' ? 'accent' : item.severity}>
                    {item.severity}
                  </Badge>
                  <span className="text-[16px] font-semibold uppercase tracking-wide text-[var(--am-text-tertiary)]">
                    {item.category}
                  </span>
                </div>
              </div>
            </li>
          ))
        )}
      </ul>
    </section>
  );
};
