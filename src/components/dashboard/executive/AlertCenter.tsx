import React, { useMemo, useState } from 'react';
import { Badge } from '../../ui/Badge';
import { SectionTitle } from './ExecutiveKpis';
import type { ApiAlert } from '../../../services/telemetry';
import { riskTone } from '../../../design-system/tokens';

type Props = { alerts: ApiAlert[] };

const TABS = ['critical', 'high', 'medium', 'resolved'] as const;

function departmentFor(alert: ApiAlert) {
  const sev = (alert.severity || '').toLowerCase();
  if (sev === 'critical') return 'Emergency Ops';
  if (sev === 'high') return 'Network Maintenance';
  return 'District Control';
}

export const AlertCenter: React.FC<Props> = ({ alerts }) => {
  const [tab, setTab] = useState<(typeof TABS)[number]>('critical');

  const grouped = useMemo(() => {
    const active = alerts.filter((a) => a.status === 'active' || !a.status);
    const resolved = alerts.filter((a) => a.status === 'resolved' || a.status === 'closed');
    return {
      critical: active.filter((a) => a.severity === 'critical'),
      high: active.filter((a) => a.severity === 'high'),
      medium: active.filter((a) => a.severity === 'medium' || a.severity === 'warning'),
      resolved,
    };
  }, [alerts]);

  const list = grouped[tab];

  return (
    <section className="rounded-[var(--am-radius-xl)] bg-[var(--am-bg-elevated)] p-5 shadow-[var(--am-shadow-md)]">
      <SectionTitle
        title="Alert Center"
        subtitle="Severity-ranked incidents with predicted impact and recommended ownership."
      />
      <div className="mt-4 flex flex-wrap gap-1 rounded-xl bg-[var(--am-bg-muted)] p-1">
        {TABS.map((t) => (
          <button
            key={t}
            type="button"
            onClick={() => setTab(t)}
            className={`rounded-lg px-3 py-2 text-[15px] font-semibold capitalize transition-colors ${
              tab === t
                ? 'bg-[var(--am-bg-elevated)] text-[var(--am-text)] shadow-[var(--am-shadow-sm)]'
                : 'text-[var(--am-text-secondary)]'
            }`}
          >
            {t} ({grouped[t].length})
          </button>
        ))}
      </div>

      <ul className="mt-4 max-h-[360px] space-y-2 overflow-y-auto">
        {list.length === 0 ? (
          <li className="rounded-[14px] bg-[var(--am-bg-muted)] p-4 text-[16px] text-[var(--am-text-secondary)]">
            No alerts in this bucket.
          </li>
        ) : (
          list.map((a) => {
            const tone = riskTone(a.severity);
            return (
              <li key={a.id} className="rounded-[14px] bg-[var(--am-bg-muted)] p-3.5">
                <div className="flex flex-wrap items-start justify-between gap-2">
                  <div className="min-w-0">
                    <p className="text-[16px] font-semibold text-[var(--am-text)]">{a.locationName}</p>
                    <p className="mt-1 text-[15px] text-[var(--am-text-secondary)]">
                      Prediction: {a.detectedFlowDropPercent}% flow drop · anomaly {a.anomalyScore.toFixed(2)} · ~
                      {a.estimatedWaterLossLpm.toFixed(0)} L/min estimated water loss
                    </p>
                    <p className="mt-1 text-[15px] text-[var(--am-text-secondary)]">
                      Action: {a.aiDiagnostics || 'Dispatch field crew for acoustic verification.'}
                    </p>
                    <p className="mt-1 text-[14px] font-medium text-[var(--am-text-tertiary)]">
                      Owner · {departmentFor(a)} · {a.zone}
                    </p>
                  </div>
                  <Badge tone={tone === 'neutral' ? 'accent' : tone}>{a.severity}</Badge>
                </div>
              </li>
            );
          })
        )}
      </ul>
    </section>
  );
};
