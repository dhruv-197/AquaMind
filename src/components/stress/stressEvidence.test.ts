/** Unit tests for Water Stress evidence / explainability helpers. */
import assert from 'node:assert/strict';
import { describe, it } from 'node:test';
import {
  buildStressEvidenceReport,
  componentDeltas,
  explainWsiChange,
  formatWsi,
  topDrivers,
} from './stressEvidence.ts';

describe('stressEvidence helpers', () => {
  it('formats missing WSI clearly', () => {
    assert.equal(formatWsi(null), '—');
    assert.equal(formatWsi(42.26), '42.3');
  });

  it('ranks top drivers by absolute contribution', () => {
    const drivers = topDrivers(
      {
        demand: { score: 80, contribution: 12 },
        rainfall: { score: 40, contribution: -8 },
        reservoir: { score: 30, contribution: 3 },
      },
      2,
    );
    assert.equal(drivers[0].key, 'demand');
    assert.equal(drivers[1].key, 'rainfall');
  });

  it('explains baseline versus scenario WSI change from component deltas', () => {
    const deltas = componentDeltas(
      {
        demand: { score: 40, contribution: 5 },
        rainfall: { score: 30, contribution: 4 },
      },
      {
        demand: { score: 70, contribution: 10 },
        rainfall: { score: 55, contribution: 8 },
      },
    );
    assert.ok(deltas.some((d) => d.key === 'demand' && d.delta === 30));
    const text = explainWsiChange({ previous: 40, current: 58, deltas });
    assert.match(text || '', /increased from 40\.0 to 58\.0/);
    assert.match(text || '', /demand/);
  });

  it('builds an evidence brief with partial data without inventing values', () => {
    const report = buildStressEvidenceReport({
      generatedAt: '2026-08-10T12:00:00Z',
      regionName: 'Ward 8',
      regionId: 'WARD-08',
      hasScenario: true,
      projectionDisclaimer: 'Scenario values are projections.',
      baselineWsi: 45,
      scenarioWsi: 62,
      baselineRisk: 'Moderate',
      scenarioRisk: 'High',
      deltaVsBaseline: 17,
      components: { demand: { score: 70, contribution: 10, detail: 'util=92' } },
      baselineComponents: { demand: { score: 40, contribution: 5, detail: 'util=70' } },
      actions: [{ id: 'a1', title: 'Reduce industrial allocation', priority: 'immediate' }],
      insights: [],
      scenario: { rainfall_delta_pct: -35 },
    });
    assert.match(report, /Baseline WSI: 45\.0/);
    assert.match(report, /Scenario WSI: 62\.0/);
    assert.match(report, /projections/);
    assert.match(report, /Reduce industrial allocation/);
    assert.match(report, /rainfall_delta_pct: -35/);
    assert.match(report, /Measured savings are not claimed/);
    assert.ok(!report.includes('undefined'));
  });

  it('represents missing optional AI fields clearly', () => {
    const report = buildStressEvidenceReport({
      hasScenario: false,
      actions: null,
      insights: null,
      components: null,
    });
    assert.match(report, /Recommendations[\s\S]*—/);
    assert.match(report, /Insights[\s\S]*—/);
  });
});
