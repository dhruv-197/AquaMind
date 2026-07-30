import React from 'react';
import { CircleGauge } from 'lucide-react';
import { PageTitleIcon } from '../ui/PageTitleIcon';

type Props = {
  ready: boolean;
  loading?: boolean;
  moduleVersion?: string;
  demandTrained?: boolean;
  reservoirTrained?: boolean;
  regionName?: string | null;
};

export const StressHeader: React.FC<Props> = () => {
  return (
    <header className="overflow-hidden rounded-[20px] border border-[var(--am-border)] bg-[var(--am-bg-elevated)] px-5 py-5 shadow-[var(--am-shadow-md)]">
      <div className="flex items-center gap-3">
        <PageTitleIcon icon={CircleGauge} />
        <h1 className="text-[30px] font-bold tracking-[-0.02em] text-[var(--am-text)]">
          Water Stress Score
        </h1>
      </div>
      <p className="mt-1.5 text-[17px] text-[var(--am-text-secondary)]">
        View the overall health of your water system.
      </p>
      <p className="mt-2.5 text-[15px] leading-relaxed text-[var(--am-text-tertiary)]">
        <span className="font-medium text-[var(--am-text-secondary)]">Technical: </span>
        Combines demand, reservoir storage, and climate signals into one score.
      </p>
    </header>
  );
};
