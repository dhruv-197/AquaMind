import React from 'react';
import type { StressWorkspaceData } from './types';
import { KpiCard } from '../ui/KpiCard';
import { riskTone } from '../../design-system/tokens';

type Props = {
  summary?: StressWorkspaceData['summary'] | null;
  riskLabel?: string | null;
};

export const StressKpiCards: React.FC<Props> = ({ summary, riskLabel }) => {
  const risk = riskLabel || summary?.risk_label;
  return (
    <section className="grid grid-cols-2 gap-3 lg:grid-cols-3 xl:grid-cols-6">
      <KpiCard
        label="Water Stress Score"
        value={summary?.current_stress == null ? '-' : summary.current_stress.toFixed(1)}
        subtitle="Baseline WSI"
        tooltip="Overall water system pressure on a 0-100 scale, combining demand, storage, and climate signals."
        comparison="vs prior fusion cycle"
        accent="blue"
        sparkline={[42, 44, 43, 46, 48, summary?.current_stress ?? 50]}
      />
      <KpiCard
        label="Predicted stress"
        value={summary?.predicted_stress == null ? '-' : summary.predicted_stress.toFixed(1)}
        subtitle="Fused WSI 0-100"
        tooltip="Forecasted water stress score at the end of the selected horizon."
        status={risk ? { label: String(risk).toUpperCase(), tone: riskTone(risk) } : undefined}
        accent="orange"
        sparkline={[48, 50, 52, 55, 58, summary?.predicted_stress ?? 60]}
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
        sparkline={[1, 1.1, 1.05, 1.2, 1.3, 1.4]}
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
        sparkline={[0.7, 0.72, 0.75, 0.74, 0.78, summary?.confidence ?? 0.8]}
      />
    </section>
  );
};
