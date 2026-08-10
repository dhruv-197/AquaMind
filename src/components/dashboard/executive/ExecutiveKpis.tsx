import React from 'react';
import { KpiCard } from '../../ui/KpiCard';
import type { ExecutiveKpi } from './derive';

type Props = { kpis: ExecutiveKpi[] };

const ACCENTS = ['blue', 'violet', 'green', 'orange', 'red', 'blue', 'orange', 'green', 'violet'] as const;

export const ExecutiveKpis: React.FC<Props> = ({ kpis }) => (
  <section>
    <SectionTitle
      title="Key Metrics"
      subtitle="Live view of demand, storage, water stress, and climate conditions."
    />
    <div className="mt-4 grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-3 2xl:grid-cols-5">
      {kpis.map((k, i) => (
        <KpiCard
          key={k.id}
          label={k.label}
          value={k.value}
          subtitle={k.forecast}
          tooltip={k.tooltip || `Live ${k.label.toLowerCase()} for operational monitoring.`}
          trend={k.trend}
          status={k.status}
          sparkline={k.sparkline}
          accent={ACCENTS[i % ACCENTS.length]}
        />
      ))}
    </div>
  </section>
);

export function SectionTitle({ title, subtitle }: { title: string; subtitle?: string }) {
  return (
    <div>
      <h2 className="am-section-title text-[22px]">{title}</h2>
      {subtitle ? <p className="mt-1 text-[16px] leading-relaxed text-[var(--am-text-secondary)]">{subtitle}</p> : null}
    </div>
  );
}
