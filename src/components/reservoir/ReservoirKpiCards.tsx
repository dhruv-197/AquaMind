import React from 'react';
import type { ForecastUnit, ReservoirSummaryData, SeriesPoint } from './types';
import { formatPct } from '../demand/utils';
import { KpiCard } from '../ui/KpiCard';
import { sparklineFrom } from '../ui/sparkline';
import { riskTone } from '../../design-system/tokens';

type Props = {
  currentStorage?: number | null;
  forecastedStorage?: number | null;
  remainingDays?: number | null;
  peakStorage?: number | null;
  minimumStorage?: number | null;
  confidence?: number | null;
  risk?: string | null;
  summary?: ReservoirSummaryData | null;
  horizonValue?: number;
  horizonUnit?: ForecastUnit;
  /** Storage series backing the sparklines. Absent series means no sparkline. */
  series?: SeriesPoint[] | null;
};

export const ReservoirKpiCards: React.FC<Props> = ({
  currentStorage,
  forecastedStorage,
  remainingDays,
  peakStorage,
  minimumStorage,
  confidence,
  risk,
  summary,
  series,
}) => {
  const days = remainingDays ?? summary?.remaining_days ?? summary?.days_to_critical;
  const riskLabel = risk || summary?.risk_label;
  const conf = confidence ?? summary?.confidence;

  // Charted from the returned storage series only — never padded with
  // placeholder points that would imply a decline we did not observe.
  const observedSpark = sparklineFrom(series, 'historical');
  const forecastSpark = sparklineFrom(series, 'forecast');
  const confidenceSpark = sparklineFrom(series, 'confidence');

  return (
    <section className="grid grid-cols-2 gap-3 lg:grid-cols-4 xl:grid-cols-7">
      <KpiCard
        label="Current storage"
        value={formatPct(currentStorage ?? summary?.current_storage_pct, 1)}
        subtitle="Observed level"
        tooltip="Latest observed reservoir storage as a percentage of total capacity."
        accent="blue"
        sparkline={observedSpark}
      />
      <KpiCard
        label="Forecasted storage"
        value={formatPct(forecastedStorage ?? summary?.forecasted_storage_pct, 1)}
        subtitle={
          summary?.forecasted_storage_mcm != null
            ? `${summary.forecasted_storage_mcm.toFixed(1)} MCM`
            : 'End of forecast range'
        }
        tooltip="Predicted storage level at the end of the selected forecast range."
        accent="violet"
        sparkline={forecastSpark}
      />
      <KpiCard
        label="Remaining days"
        value={days == null ? '-' : String(days)}
        subtitle="Until critical (<20%)"
        tooltip="Estimated days until storage falls below the critical threshold of 20%."
        accent="orange"
        trend={
          days != null
            ? { direction: days < 30 ? 'down' : 'flat', label: days < 30 ? 'Urgent' : 'Stable' }
            : undefined
        }
      />
      <KpiCard
        label="Peak storage"
        value={formatPct(peakStorage ?? summary?.peak_storage_pct, 1)}
        subtitle={summary?.peak_date ? String(summary.peak_date) : 'Within window'}
        tooltip="Highest predicted storage percentage within the forecast window."
        accent="green"
      />
      <KpiCard
        label="Minimum storage"
        value={formatPct(minimumStorage ?? summary?.minimum_storage_pct, 1)}
        subtitle={summary?.minimum_date ? String(summary.minimum_date) : 'Within window'}
        tooltip="Lowest predicted storage percentage within the forecast window."
        accent="red"
      />
      <KpiCard
        label="Risk"
        value={(riskLabel || '-').toUpperCase()}
        subtitle="Storage risk band"
        tooltip="Overall storage risk classification based on predicted levels and trends."
        status={riskLabel ? { label: String(riskLabel).toUpperCase(), tone: riskTone(riskLabel) } : undefined}
        accent="orange"
      />
      <KpiCard
        label="Prediction Confidence"
        value={conf == null ? '-' : `${Math.round(conf * 100)}%`}
        subtitle="Model confidence"
        tooltip="How confident the model is in this storage forecast based on data quality and ensemble agreement."
        comparison="ensemble"
        accent="green"
        sparkline={confidenceSpark}
      />
    </section>
  );
};
