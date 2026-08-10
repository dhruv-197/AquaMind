import React from 'react';
import type { StressAction } from './types';
import { StatusBadge } from '../ui/Badge';
import { RecommendationFeedbackControls } from '../ui/RecommendationFeedbackControls';
import { componentDeltas, explainWsiChange, formatWsi, topDrivers } from './stressEvidence';

type ComponentMeta = { score: number; contribution: number; detail: string; weight?: number };

type Props = {
  insights?: string[];
  actions?: StressAction[];
  components?: Record<string, ComponentMeta>;
  baselineComponents?: Record<string, ComponentMeta> | null;
  baselineWsi?: number | null;
  currentWsi?: number | null;
  generatedAt?: string | null;
  hasScenario?: boolean;
  regionId?: string;
};

const COMPONENT_LABELS: Record<string, string> = {
  demand: 'Demand',
  reservoir: 'Reservoir',
  climate: 'Climate',
  groundwater: 'Groundwater',
  population: 'Population',
  rainfall: 'Rainfall',
  temperature: 'Temperature',
  historical: 'Recent history',
};

/** Turn technical fusion detail into plain English for operators. */
function plainDetail(key: string, detail: string, score: number): string {
  const s = detail || '';
  const lower = key.toLowerCase();
  if (lower === 'demand') {
    const util = s.match(/util=([\d.]+)/i);
    const risk = s.match(/risk=([A-Z_]+)/i);
    const utilPct = util ? Math.round(Number(util[1])) : null;
    if (utilPct != null && utilPct >= 90) {
      return `Demand is running near capacity${risk ? ` (${risk[1].toLowerCase()} risk)` : ''}.`;
    }
    if (utilPct != null) return `Demand is using about ${utilPct}% of available capacity.`;
    return 'Demand is a major pressure on water supply.';
  }
  if (lower === 'reservoir') {
    const stor = s.match(/Storage=([\d.]+)/i);
    if (stor) return `Reservoir storage is around ${Number(stor[1]).toFixed(0)}%.`;
    return 'Reservoir storage is affecting the Water Stress Index.';
  }
  if (lower === 'rainfall' || lower === 'climate') {
    const def = s.match(/deficit=([\d.-]+)/i);
    if (def) {
      const v = Number(def[1]);
      if (v > 5) return `Rainfall is below normal by about ${Math.round(v)}%.`;
      if (v < -5) return `Rainfall is above normal by about ${Math.round(Math.abs(v))}%.`;
    }
    return 'Recent rainfall is included in the stress picture.';
  }
  if (lower === 'groundwater') {
    const depth = s.match(/depth=([\d.]+)/i);
    if (depth) return `Groundwater is about ${Number(depth[1]).toFixed(0)} m deep.`;
    return 'Groundwater levels are part of this score.';
  }
  if (lower === 'population') {
    const pop = s.match(/Population=([\d,]+)/i);
    if (pop) return `About ${pop[1]} people live in this service area.`;
    return 'Population load is included in the score.';
  }
  if (lower === 'historical') return 'Recent stress history is carried forward into today’s score.';
  if (score >= 70) return 'This factor is pushing stress higher.';
  if (score >= 40) return 'This factor is a moderate contributor.';
  return 'This factor has a smaller influence right now.';
}

function plainInsight(raw: string): string {
  let t = raw;
  t = t.replace(/\([^)]*(?:util=|share=|Δ |WSI=|MGD)[^)]*\)/gi, '');
  t = t.replace(/Primary stress driver:\s*(\w+)\s*\.?/i, (_, k) => {
    const label = COMPONENT_LABELS[String(k).toLowerCase()] || k;
    return `The main pressure today is ${label.toLowerCase()}.`;
  });
  t = t.replace(/population at risk exceeds\s*([\d,]+)/i, 'A large population could be affected ($1 people)');
  t = t.replace(/≈\s*([\d,]+)/g, 'about $1');
  t = t.replace(/\s{2,}/g, ' ').trim();
  if (!/[.!?]$/.test(t)) t += '.';
  return t;
}

function plainAction(a: StressAction): { title: string; description: string; priority?: string } {
  const priorityMap: Record<string, string> = {
    immediate: 'Do now',
    short_term: 'This week',
    monitor: 'Watch',
    medium_term: 'Plan ahead',
  };
  let description = a.description
    .replace(/WSI remains [A-Z_]+/gi, 'stress stays high')
    .replace(/if WSI crosses High/gi, 'if stress rises further')
    .replace(/population at risk ≈\s*([\d,]+)/gi, 'about $1 people could be affected')
    .replace(/\([^)]*\)/g, '')
    .replace(/\s{2,}/g, ' ')
    .trim();
  return {
    title: a.title,
    description,
    priority: a.priority ? priorityMap[a.priority] || a.priority.replace(/_/g, ' ') : undefined,
  };
}

export const StressInsightsPanel: React.FC<Props> = ({
  insights,
  actions,
  components,
  baselineComponents,
  baselineWsi,
  currentWsi,
  generatedAt,
  hasScenario,
  regionId,
}) => {
  const entries = components
    ? (Object.entries(components) as Array<[string, ComponentMeta]>).sort(
        (a, b) => b[1].contribution - a[1].contribution,
      )
    : [];

  const totalContribution = entries.reduce((s, [, m]) => s + Math.abs(m.contribution), 0) || 1;
  const deltas = componentDeltas(baselineComponents, components);
  const explanation = explainWsiChange({
    previous: baselineWsi,
    current: currentWsi,
    deltas,
  });
  const drivers = topDrivers(components, 3);

  return (
    <div className="space-y-4">
      {(hasScenario && explanation) || generatedAt || drivers.length ? (
        <section className="am-soft-card" aria-labelledby="wsi-explain-heading">
          <header className="border-b border-[var(--am-divider)] px-5 py-4">
            <h3 id="wsi-explain-heading" className="text-[17px] font-semibold text-[var(--am-text)]">
              Why the score moved
            </h3>
            <p className="mt-0.5 text-[15px] text-[var(--am-text-secondary)]">
              Uses fusion component contributions only — no invented drivers.
            </p>
          </header>
          <div className="space-y-3 p-5 text-[15px] text-[var(--am-text-secondary)]">
            {generatedAt ? (
              <p className="text-[14px] text-[var(--am-text-tertiary)]">
                Data freshness: fusion at {new Date(generatedAt).toLocaleString()}
                {currentWsi != null ? ` · Current WSI ${formatWsi(currentWsi)}` : ''}
                {baselineWsi != null ? ` · Prior / baseline ${formatWsi(baselineWsi)}` : ''}
              </p>
            ) : null}
            {explanation ? <p className="leading-relaxed text-[var(--am-text)]">{explanation}</p> : null}
            {!explanation && !hasScenario ? (
              <p>Run a scenario to compare component contributions against the baseline fusion.</p>
            ) : null}
            {drivers.length ? (
              <ol className="list-decimal space-y-1 pl-5">
                {drivers.map((d) => (
                  <li key={d.key}>
                    <span className="font-medium text-[var(--am-text)]">
                      {COMPONENT_LABELS[d.key.toLowerCase()] || d.key}
                    </span>
                    {d.detail ? ` — ${plainDetail(d.key, d.detail, d.score)}` : ''}
                  </li>
                ))}
              </ol>
            ) : null}
          </div>
        </section>
      ) : null}

      <div className="grid items-stretch gap-4 lg:grid-cols-3">
        <section className="am-soft-card flex h-full flex-col">
          <header className="border-b border-[var(--am-divider)] px-5 py-4">
            <h3 className="text-[17px] font-semibold text-[var(--am-text)]">Executive insights</h3>
          </header>
          <ul className="flex-1 space-y-2.5 p-5 text-[16px] leading-relaxed text-[var(--am-text-secondary)]">
            {(insights || []).length ? (
              insights!.map((t, i) => <li key={i}>{plainInsight(t)}</li>)
            ) : (
              <li className="text-[var(--am-text-tertiary)]">Run a forecast to generate insights.</li>
            )}
          </ul>
        </section>

        <section className="am-soft-card flex h-full flex-col">
          <header className="border-b border-[var(--am-divider)] px-5 py-4">
            <h3 className="text-[17px] font-semibold text-[var(--am-text)]">Recommended actions</h3>
          </header>
          <ul className="flex-1 space-y-3 p-5">
            {(actions || []).length ? (
              actions!.map((a) => {
                const plain = plainAction(a);
                return (
                  <li key={a.id}>
                    <div className="flex flex-wrap items-center gap-2">
                      <p className="text-[16px] font-semibold text-[var(--am-text)]">{plain.title}</p>
                      {plain.priority ? <StatusBadge status={plain.priority} /> : null}
                    </div>
                    <p className="mt-1 text-[15px] text-[var(--am-text-secondary)]">{plain.description}</p>
                    <RecommendationFeedbackControls
                      recommendationId={a.id}
                      source="stress"
                      regionId={regionId}
                    />
                  </li>
                );
              })
            ) : (
              <li className="text-[16px] text-[var(--am-text-tertiary)]">No actions yet.</li>
            )}
          </ul>
        </section>

        <section className="am-soft-card flex h-full flex-col">
          <header className="border-b border-[var(--am-divider)] px-5 py-4">
            <h3 className="text-[17px] font-semibold text-[var(--am-text)]">Stress score fusion</h3>
            <p className="mt-0.5 text-[15px] text-[var(--am-text-secondary)]">
              Share of the score each input contributed, next to the published weight the
              fusion applied to it. Both come straight from the API response.
            </p>
          </header>
          <ul className="flex-1 space-y-3 p-5">
            {entries.length ? (
              entries.map(([key, meta]) => {
                const pct = (Math.abs(meta.contribution) / totalContribution) * 100;
                const label = COMPONENT_LABELS[key.toLowerCase()] || key;
                // Weight is the published fusion coefficient returned with the
                // response; rendering it means the on-screen breakdown can be
                // checked against the API rather than taken on trust.
                const weightPct =
                  typeof meta.weight === 'number' && Number.isFinite(meta.weight)
                    ? Math.round(meta.weight * 100)
                    : null;
                return (
                  <li key={key}>
                    <div className="flex items-center justify-between gap-2 text-[15px]">
                      <span className="font-semibold text-[var(--am-text)]">{label}</span>
                      <span className="flex items-center gap-2">
                        {weightPct != null ? (
                          <span
                            className="rounded-full bg-[var(--am-bg-muted)] px-2 py-0.5 text-[13px] font-medium tabular-nums text-[var(--am-text-tertiary)]"
                            title={`Published fusion weight for ${label}`}
                          >
                            weight {weightPct}%
                          </span>
                        ) : null}
                        <span className="tabular-nums text-[var(--am-text-secondary)]">{pct.toFixed(0)}%</span>
                      </span>
                    </div>
                    <div
                      className="mt-1.5 h-2 overflow-hidden rounded-full bg-[var(--am-bg-muted)]"
                      role="progressbar"
                      aria-valuenow={Math.round(pct)}
                      aria-valuemin={0}
                      aria-valuemax={100}
                      aria-label={`${label} contribution`}
                    >
                      <div
                        className="h-full rounded-full bg-[var(--am-accent)] transition-all duration-500"
                        style={{ width: `${pct}%` }}
                      />
                    </div>
                    <p className="mt-1 text-[14px] text-[var(--am-text-tertiary)]">
                      {plainDetail(key, meta.detail, meta.score)}
                    </p>
                  </li>
                );
              })
            ) : (
              <li className="text-[16px] text-[var(--am-text-tertiary)]">No component breakdown.</li>
            )}
          </ul>
        </section>
      </div>
    </div>
  );
};
