import React from 'react';
import type { ForecastSummaryData, ForecastUnit } from './types';
import { formatMgd } from './utils';
import { KpiCard } from '../ui/KpiCard';
import { riskTone } from '../../design-system/tokens';

type Props = {
  predictedDemand?: number | null;
  peakDemand?: number | null;
  capacity?: number | null;
  confidence?: number | null;
  risk?: string | null;
  horizonValue: number;
  horizonUnit: ForecastUnit;
  summary?: ForecastSummaryData | null;
};

export const ForecastKpiCards: React.FC<Props> = ({
  predictedDemand,
  peakDemand,
  capacity,
  confidence,
  risk,
  horizonValue,
  horizonUnit,
  summary,
}) => {
  const util =
    predictedDemand != null && capacity
      ? Math.min(100, Math.round((predictedDemand / capacity) * 100))
      : null;

  return (
    <section className="grid grid-cols-2 gap-3 lg:grid-cols-3 xl:grid-cols-6">
      <KpiCard
        label="Predicted demand"
        value={formatMgd(predictedDemand, 1)}
        subtitle="Million gallons / day"
        tooltip="Expected water demand for the selected forecast range."
        sparkline={
          summary?.point_count
            ? [0.82, 0.88, 0.91, 0.95, 1, 0.97].map((x) => (predictedDemand || 0) * x)
            : undefined
        }
      />
      <KpiCard
        label="Peak demand"
        value={formatMgd(peakDemand ?? summary?.predicted_peak_demand_mgd, 1)}
        subtitle={summary?.peak_date ? String(summary.peak_date) : 'Within forecast window'}
        tooltip="Highest predicted demand within the selected forecast range."
      />
      <KpiCard
        label="Maximum Capacity"
        value={formatMgd(capacity, 1)}
        subtitle="System capacity"
        tooltip="Maximum water the system can supply under normal operating conditions."
      />
      <KpiCard
        label="Prediction Confidence"
        value={confidence == null ? '-' : `${Math.round(confidence * 100)}%`}
        subtitle="Model confidence"
        tooltip="How reliable the prediction is based on available data and model performance."
        status={
          confidence != null
            ? {
                label: confidence >= 0.75 ? 'High' : confidence >= 0.5 ? 'Fair' : 'Low',
                tone: confidence >= 0.75 ? 'success' : confidence >= 0.5 ? 'warning' : 'danger',
              }
            : undefined
        }
      />
      <KpiCard
        label="Risk"
        value={(risk || '-').toUpperCase()}
        subtitle={util != null ? `${util}% water system usage` : 'Vs maximum capacity'}
        tooltip="Shortage risk relative to system capacity for the forecast range."
        status={risk ? { label: (risk || '').toUpperCase(), tone: riskTone(risk) } : undefined}
      />
      <KpiCard
        label="Forecast Range"
        value={`${horizonValue} ${horizonUnit}`.toUpperCase()}
        subtitle={`${summary?.point_count ?? horizonValue} forecast points`}
        tooltip="How far ahead the prediction looks from today."
      />
    </section>
  );
};
