import React from 'react';
import { Waves } from 'lucide-react';
import { PageTitleIcon } from '../ui/PageTitleIcon';

type Props = {
  modelName?: string;
  modelVersion?: string;
  modelStatus: 'ready' | 'untrained' | 'loading' | 'predicting';
  lastTrained?: string | null;
  dataPoints?: number | null;
  onTrain?: () => void;
  training?: boolean;
  selectedName?: string | null;
};

export const ReservoirHeader: React.FC<Props> = () => {
  return (
    <header className="overflow-hidden rounded-[20px] border border-[var(--am-border)] bg-[var(--am-bg-elevated)] px-5 py-5 shadow-[var(--am-shadow-md)]">
      <div className="flex items-center gap-3">
        <PageTitleIcon icon={Waves} />
        <h1 className="text-[30px] font-bold tracking-[-0.02em] text-[var(--am-text)]">
          Reservoir Forecast
        </h1>
      </div>
      <p className="mt-1.5 text-[17px] text-[var(--am-text-secondary)]">
        Predict how reservoir storage may change over the coming days.
      </p>
      <p className="mt-2.5 text-[15px] leading-relaxed text-[var(--am-text-tertiary)]">
        <span className="font-medium text-[var(--am-text-secondary)]">Technical: </span>
        Prediction uses historical storage, rainfall, weather, and environmental variables.
      </p>
    </header>
  );
};
