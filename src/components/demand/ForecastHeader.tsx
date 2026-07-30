import React from 'react';
import { ChartSpline } from 'lucide-react';
import { PageTitleIcon } from '../ui/PageTitleIcon';

type Props = {
  modelName?: string;
  modelVersion?: string;
  modelStatus: 'ready' | 'untrained' | 'loading' | 'predicting';
  lastTrained?: string | null;
  dataPoints?: number | null;
  onTrain?: () => void;
  training?: boolean;
};

export const ForecastHeader: React.FC<Props> = () => {
  return (
    <header className="overflow-hidden rounded-[16px] border border-[var(--am-border)] bg-[var(--am-bg-elevated)] px-5 py-5 shadow-[var(--am-shadow-sm)]">
      <div className="flex items-center gap-3">
        <PageTitleIcon icon={ChartSpline} />
        <h1 className="text-[30px] font-bold tracking-[-0.02em] text-[var(--am-text)]">
          Demand Forecast
        </h1>
      </div>
      <p className="mt-1.5 text-[17px] text-[var(--am-text-secondary)]">
        Predict how much water your community will need over the coming days.
      </p>
      <p className="mt-2 text-[15px] leading-relaxed text-[var(--am-text-tertiary)]">
        Technical: Prediction uses historical demand, weather, and system capacity data.
      </p>
    </header>
  );
};

export function formatHorizonLabel(value: number, unit: string): string {
  return `${value} ${unit}`;
}
