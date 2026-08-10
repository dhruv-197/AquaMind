import React from 'react';
import type { StressSeriesPoint, StressWorkspaceData } from './types';
import { KpiCard } from '../ui/KpiCard';
import { sparklineFrom } from '../ui/sparkline';
import { riskTone } from '../../design-system/tokens';

type Props = {
  summary?: StressWorkspaceData['summary'] | null;
  riskLabel?: string | null;
  /** Fusion series backing the sparklines. Absent series means no sparkline. */
  series?: StressSeriesPoint[] | null;
};

export const StressKpiCards: React.FC<Props> = ({ summary, riskLabel, series }) => {
  const risk = riskLabel || summary?.risk_label;

  // Sparklines are drawn from the fusion series only. When the series is
  // missing or too short the card renders without a line rather than showing
  // a trend nobody measured.
  const historicalSpark = sparklineFrom(series, 'historical');
  const forecastSpark = sparklineFrom(series, 'forecast');
  const confidenceSpark = sparklineFrom(series, 'confidence');

  return (
    <section className="grid grid-cols-2 gap-3 lg:grid-cols-3 xl:grid-cols-6">
      <KpiCard
        label="Water Stress Index"
        value={summary?.current_stress == null ? '-' : summary.current_stress.toFixed(1)}
        subtitle="Baseline WSI"
        tooltip="Overall water system pressure on a 0-100 scale, combining demand, storage, and climate signals."
        accent="blue"
        sparkline={historicalSpark}
      />
      <KpiCard
        label="Predicted stress"
        value={summary?.predicted_stress == null ? '-' : summary.predicted_stress.toFixed(1)}
        subtitle="Fused WSI 0-100"
        tooltip="Forecasted Water Stress Index at the end of the selected horizon."
        status={risk ? { label: String(risk), tone: riskTone(risk) } : undefined}
        accent="orange"
        sparkline={forecastSpark}
      />
      <KpiCard
        label="Highest risk region"
        value={summary?.highest_risk_region || '-'}
        subtitle="Across map catalog"
        tooltip="The region with the highest predicted water stress in the current forecast."
        accent="red"
      />
      <KpiCard
        label="Population affected"
        value={summary?.population_affected == null ? '-' : summary.population_affected.toLocaleString()}
        subtitle="At-risk estimate"
        tooltip="Estimated population that may be affected by elevated water stress."
        accent="violet"
      />
      <KpiCard
        label="Expected shortage"
        value={summary?.expected_shortage_date || '-'}
        subtitle="Projected date"
        tooltip="Earliest projected date when supply may not meet demand at current trends."
        accent="orange"
      />
      <KpiCard
        label="Prediction Confidence"
        value={summary?.confidence == null ? '-' : `${Math.round(summary.confidence * 100)}%`}
        subtitle={(risk || '-').toUpperCase()}
        tooltip="How confident the fusion model is in the combined stress forecast."
        comparison="model ensemble"
        accent="green"
        sparkline={confidenceSpark}
      />
    </section>
  );
};
