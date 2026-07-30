import React from 'react';
import { StatusBadge } from '../../ui/Badge';
import { SectionTitle } from './ExecutiveKpis';
import type { ModelHealthRow } from './derive';

type Props = { models: ModelHealthRow[] };

export const ModelHealthPanel: React.FC<Props> = ({ models }) => (
  <section className="am-soft-card p-5 sm:p-6">
    <SectionTitle
      title="Supporting AI Models"
      subtitle="Holdout metrics from backend evaluation. MAPE / MAE (forecasts), F1 / accuracy (classifier)."
    />
    <div className="mt-4 overflow-x-auto">
      <table className="am-table w-full min-w-[720px] border-collapse text-left text-[16px]">
        <thead>
          <tr>
            {['Model', 'Status', 'Accuracy', 'Last trained', 'Confidence', 'Health', 'Version'].map((h) => (
              <th
                key={h}
                className="border-b border-[var(--am-divider)] px-4 py-3.5 text-[14px] font-semibold uppercase tracking-[0.06em] text-[var(--am-text-secondary)]"
              >
                {h}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {models.map((m) => (
            <tr key={m.id} className="hover:bg-[var(--am-bg-muted)]">
              <td className="border-b border-[var(--am-divider)] px-4 py-3.5 font-semibold text-[var(--am-text)]">
                {m.name}
              </td>
              <td className="border-b border-[var(--am-divider)] px-4 py-3.5">
                <StatusBadge status={m.status} />
              </td>
              <td className="border-b border-[var(--am-divider)] px-4 py-3.5 tabular-nums text-[15px] leading-snug text-[var(--am-text)]">
                {m.accuracy}
              </td>
              <td className="border-b border-[var(--am-divider)] px-4 py-3.5 text-[var(--am-text-secondary)]">
                {m.lastTrained}
              </td>
              <td className="border-b border-[var(--am-divider)] px-4 py-3.5 tabular-nums text-[var(--am-text)]">
                {m.confidence}
              </td>
              <td className="border-b border-[var(--am-divider)] px-4 py-3.5">
                <StatusBadge
                  kind={
                    m.health === 'success'
                      ? 'healthy'
                      : m.health === 'warning'
                        ? 'moderate'
                        : m.health === 'danger'
                          ? 'critical'
                          : 'ready'
                  }
                />
              </td>
              <td className="border-b border-[var(--am-divider)] px-4 py-3.5 font-mono text-[15px] text-[var(--am-text-secondary)]">
                {m.version}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  </section>
);
