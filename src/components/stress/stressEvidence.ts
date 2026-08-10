/** Pure helpers for Water Stress scenario comparison + evidence export. */

export type ComponentMeta = {
  score?: number;
  contribution?: number;
  detail?: string;
  weight?: number;
};

export type StressEvidenceInput = {
  generatedAt?: string | null;
  regionName?: string | null;
  regionId?: string | null;
  moduleVersion?: string | null;
  hasScenario?: boolean;
  projectionDisclaimer?: string | null;
  baselineWsi?: number | null;
  scenarioWsi?: number | null;
  baselineRisk?: string | null;
  scenarioRisk?: string | null;
  deltaVsBaseline?: number | null;
  expectedShortageDate?: string | null;
  baselineExpectedShortageDate?: string | null;
  components?: Record<string, ComponentMeta> | null;
  baselineComponents?: Record<string, ComponentMeta> | null;
  actions?: Array<{ id?: string; title?: string; description?: string; priority?: string }> | null;
  insights?: string[] | null;
  scenario?: Record<string, number | string | undefined | null> | null;
  assumptions?: string[] | null;
  demandEffect?: string | null;
  reservoirEffect?: string | null;
};

const MISSING = '—';

export function formatWsi(value: number | null | undefined): string {
  if (value == null || Number.isNaN(Number(value))) return MISSING;
  return Number(value).toFixed(1);
}

export function topDrivers(
  components: Record<string, ComponentMeta> | null | undefined,
  limit = 3,
): Array<{ key: string; contribution: number; score: number; detail: string }> {
  if (!components) return [];
  return Object.entries(components)
    .map(([key, meta]) => ({
      key,
      contribution: Number(meta.contribution ?? 0),
      score: Number(meta.score ?? 0),
      detail: String(meta.detail ?? ''),
    }))
    .sort((a, b) => Math.abs(b.contribution) - Math.abs(a.contribution))
    .slice(0, limit);
}

export function componentDeltas(
  baseline: Record<string, ComponentMeta> | null | undefined,
  current: Record<string, ComponentMeta> | null | undefined,
): Array<{ key: string; baselineScore: number | null; scenarioScore: number | null; delta: number | null }> {
  if (!baseline || !current) return [];
  const keys = Array.from(new Set([...Object.keys(baseline), ...Object.keys(current)]));
  return keys
    .map((key) => {
      const b = baseline[key]?.score;
      const c = current[key]?.score;
      const baselineScore = b == null || Number.isNaN(Number(b)) ? null : Number(b);
      const scenarioScore = c == null || Number.isNaN(Number(c)) ? null : Number(c);
      const delta =
        baselineScore == null || scenarioScore == null ? null : scenarioScore - baselineScore;
      return { key, baselineScore, scenarioScore, delta };
    })
    .filter((row) => row.delta != null && Math.abs(row.delta) >= 0.5)
    .sort((a, b) => Math.abs(b.delta ?? 0) - Math.abs(a.delta ?? 0));
}

export function explainWsiChange(args: {
  previous?: number | null;
  current?: number | null;
  deltas?: Array<{ key: string; delta: number | null }>;
}): string | null {
  const { previous, current, deltas } = args;
  if (previous == null || current == null) return null;
  const change = current - previous;
  if (Math.abs(change) < 0.5) {
    return `Water Stress Index is essentially unchanged (${formatWsi(previous)} → ${formatWsi(current)}).`;
  }
  const direction = change > 0 ? 'increased' : 'decreased';
  const top = (deltas || []).filter((d) => d.delta != null).slice(0, 2);
  if (!top.length) {
    return `Water Stress Index ${direction} from ${formatWsi(previous)} to ${formatWsi(current)}.`;
  }
  const driverText = top
    .map((d) => {
      const sign = (d.delta ?? 0) > 0 ? '+' : '';
      return `${d.key} (${sign}${Number(d.delta).toFixed(1)})`;
    })
    .join(', ');
  return `Water Stress Index ${direction} from ${formatWsi(previous)} to ${formatWsi(current)}, mainly from ${driverText}.`;
}

export function buildStressEvidenceReport(input: StressEvidenceInput): string {
  const lines: string[] = [];
  lines.push('AquaMind Water Stress Evidence Brief');
  lines.push('====================================');
  lines.push(`Generated: ${input.generatedAt || MISSING}`);
  lines.push(`Region: ${input.regionName || MISSING}${input.regionId ? ` (${input.regionId})` : ''}`);
  lines.push(`Model / module version: ${input.moduleVersion || MISSING}`);
  lines.push('');
  if (input.hasScenario) {
    lines.push('NOTE: Scenario values are projections, not field observations.');
    if (input.projectionDisclaimer) lines.push(input.projectionDisclaimer);
    lines.push('');
  }

  lines.push('Water Stress Index');
  lines.push('------------------');
  lines.push(`Baseline WSI: ${formatWsi(input.baselineWsi)}  |  Stage: ${input.baselineRisk || MISSING}`);
  lines.push(`Scenario WSI: ${formatWsi(input.scenarioWsi)}  |  Stage: ${input.scenarioRisk || MISSING}`);
  lines.push(
    `Delta vs baseline: ${
      input.deltaVsBaseline == null
        ? MISSING
        : `${input.deltaVsBaseline >= 0 ? '+' : ''}${Number(input.deltaVsBaseline).toFixed(1)}`
    }`,
  );
  lines.push(`Expected shortage (scenario): ${input.expectedShortageDate || MISSING}`);
  lines.push(`Expected shortage (baseline): ${input.baselineExpectedShortageDate || MISSING}`);
  if (input.demandEffect) lines.push(`Demand effect: ${input.demandEffect}`);
  if (input.reservoirEffect) lines.push(`Reservoir / storage effect: ${input.reservoirEffect}`);
  lines.push('');

  lines.push('Top drivers (scenario)');
  lines.push('----------------------');
  const drivers = topDrivers(input.components, 5);
  if (!drivers.length) {
    lines.push(MISSING);
  } else {
    for (const d of drivers) {
      lines.push(`- ${d.key}: score=${formatWsi(d.score)}, contribution=${d.contribution.toFixed(2)}`);
    }
  }
  lines.push('');

  lines.push('Component changes (baseline → scenario)');
  lines.push('---------------------------------------');
  const deltas = componentDeltas(input.baselineComponents, input.components);
  if (!deltas.length) {
    lines.push(input.hasScenario ? 'No material component score changes reported.' : MISSING);
  } else {
    for (const row of deltas) {
      const sign = (row.delta ?? 0) >= 0 ? '+' : '';
      lines.push(
        `- ${row.key}: ${formatWsi(row.baselineScore)} → ${formatWsi(row.scenarioScore)} (${sign}${Number(row.delta).toFixed(1)})`,
      );
    }
  }
  lines.push('');

  lines.push('Recommendations');
  lines.push('---------------');
  const actions = input.actions || [];
  if (!actions.length) {
    lines.push(MISSING);
  } else {
    actions.forEach((a, i) => {
      lines.push(`${i + 1}. [${a.priority || 'n/a'}] ${a.title || a.id || 'Untitled'}`);
      if (a.description) lines.push(`   ${a.description}`);
    });
  }
  lines.push('');

  lines.push('Insights');
  lines.push('--------');
  const insights = input.insights || [];
  if (!insights.length) lines.push(MISSING);
  else insights.forEach((t) => lines.push(`- ${t}`));
  lines.push('');

  lines.push('Assumptions / scenario knobs');
  lines.push('----------------------------');
  if (input.scenario && Object.keys(input.scenario).length) {
    for (const [k, v] of Object.entries(input.scenario)) {
      if (v == null || v === '') continue;
      lines.push(`- ${k}: ${v}`);
    }
  } else if (input.assumptions?.length) {
    input.assumptions.forEach((a) => lines.push(`- ${a}`));
  } else {
    lines.push(MISSING);
  }
  lines.push('');
  lines.push('Measured savings are not claimed in this brief.');
  return lines.join('\n');
}
