import React from 'react';
import type { StressWorkspaceData } from './types';
import { componentDeltas, explainWsiChange, formatWsi, topDrivers } from './stressEvidence';
import { StatusBadge } from '../ui/Badge';

type Props = {
  data: StressWorkspaceData | null;
};

function Metric({
  label,
  baseline,
  scenario,
}: {
  label: string;
  baseline: string;
  scenario: string;
}) {
  return (
    <div className="rounded-[14px] border border-[var(--am-border)] bg-[var(--am-bg-elevated)] px-3 py-2.5">
      <p className="text-[13px] font-semibold uppercase tracking-wide text-[var(--am-text-tertiary)]">{label}</p>
      <div className="mt-1.5 grid grid-cols-2 gap-2 text-[15px]">
        <div>
          <p className="text-[12px] text-[var(--am-text-tertiary)]">Baseline</p>
          <p className="font-semibold tabular-nums text-[var(--am-text)]">{baseline}</p>
        </div>
        <div>
          <p className="text-[12px] text-[var(--am-text-tertiary)]">Scenario</p>
          <p className="font-semibold tabular-nums text-[var(--am-accent)]">{scenario}</p>
        </div>
      </div>
    </div>
  );
}

export const StressComparisonPanel: React.FC<Props> = ({ data }) => {
  if (!data?.has_scenario) return null;

  const baselineWsi = data.summary?.baseline_stress;
  const scenarioWsi = data.summary?.predicted_stress ?? data.water_stress_index;
  const deltas = componentDeltas(data.baseline_components, data.components);
  const explanation = explainWsiChange({
    previous: baselineWsi,
    current: scenarioWsi,
    deltas,
  });
  const drivers = topDrivers(data.components, 3);
  const demandDetail = data.components?.demand?.detail || data.baseline_components?.demand?.detail;
  const reservoirDetail =
    data.components?.reservoir?.detail || data.baseline_components?.reservoir?.detail;

  return (
    <section
      className="am-soft-card"
      aria-labelledby="stress-comparison-heading"
      data-testid="stress-comparison-panel"
    >
      <header className="border-b border-[var(--am-divider)] px-5 py-4">
        <div className="flex flex-wrap items-center gap-2">
          <h3 id="stress-comparison-heading" className="text-[17px] font-semibold text-[var(--am-text)]">
            Baseline vs scenario
          </h3>
          <StatusBadge status="Projection" kind="neutral" />
        </div>
        <p className="mt-1 text-[15px] text-[var(--am-text-secondary)]">
          {data.projection_disclaimer ||
            'Scenario values are projections from the fusion model, not field observations.'}
        </p>
      </header>

      <div className="grid gap-3 p-5 sm:grid-cols-2 lg:grid-cols-4">
        <Metric
          label="Water Stress Index"
          baseline={formatWsi(baselineWsi)}
          scenario={formatWsi(scenarioWsi)}
        />
        <Metric
          label="Stage / risk"
          baseline={String(data.baseline_risk_label || data.summary?.risk_label || '—')}
          scenario={String(data.risk_label || data.summary?.risk_label || '—')}
        />
        <Metric
          label="Shortage timing"
          baseline={String(data.baseline_expected_stress_date || '—')}
          scenario={String(data.expected_stress_date || data.summary?.expected_shortage_date || '—')}
        />
        <Metric
          label="Δ vs baseline"
          baseline="0.0"
          scenario={
            data.summary?.delta_vs_baseline == null
              ? '—'
              : `${data.summary.delta_vs_baseline >= 0 ? '+' : ''}${data.summary.delta_vs_baseline.toFixed(1)}`
          }
        />
      </div>

      <div className="grid gap-4 border-t border-[var(--am-divider)] px-5 py-4 lg:grid-cols-2">
        <div>
          <h4 className="text-[15px] font-semibold text-[var(--am-text)]">What changed</h4>
          <p className="mt-1 text-[15px] leading-relaxed text-[var(--am-text-secondary)]">
            {explanation || 'Component-level change details are not available for this run.'}
          </p>
          {demandDetail ? (
            <p className="mt-2 text-[14px] text-[var(--am-text-tertiary)]">Demand: {demandDetail}</p>
          ) : null}
          {reservoirDetail ? (
            <p className="mt-1 text-[14px] text-[var(--am-text-tertiary)]">Storage: {reservoirDetail}</p>
          ) : null}
        </div>
        <div>
          <h4 className="text-[15px] font-semibold text-[var(--am-text)]">Top drivers (scenario)</h4>
          {drivers.length ? (
            <ol className="mt-2 list-decimal space-y-1 pl-5 text-[15px] text-[var(--am-text-secondary)]">
              {drivers.map((d) => (
                <li key={d.key}>
                  <span className="font-medium text-[var(--am-text)]">{d.key}</span>
                  {d.detail ? ` — ${d.detail}` : ''}
                </li>
              ))}
            </ol>
          ) : (
            <p className="mt-2 text-[15px] text-[var(--am-text-tertiary)]">No driver breakdown available.</p>
          )}
          {deltas.length ? (
            <ul className="mt-3 space-y-1 text-[14px] text-[var(--am-text-tertiary)]">
              {deltas.slice(0, 4).map((row) => (
                <li key={row.key}>
                  {row.key}: {formatWsi(row.baselineScore)} → {formatWsi(row.scenarioScore)} (
                  {(row.delta ?? 0) >= 0 ? '+' : ''}
                  {Number(row.delta).toFixed(1)})
                </li>
              ))}
            </ul>
          ) : null}
        </div>
      </div>

      {(data.recommended_actions || []).length ? (
        <div className="border-t border-[var(--am-divider)] px-5 py-4">
          <h4 className="text-[15px] font-semibold text-[var(--am-text)]">Ranked recommendations</h4>
          <ol className="mt-2 list-decimal space-y-1.5 pl-5 text-[15px] text-[var(--am-text-secondary)]">
            {(data.recommended_actions || []).slice(0, 5).map((a) => (
              <li key={a.id}>
                <span className="font-medium text-[var(--am-text)]">{a.title}</span>
                {a.priority ? ` · ${a.priority.replace(/_/g, ' ')}` : ''}
              </li>
            ))}
          </ol>
        </div>
      ) : null}
    </section>
  );
};
