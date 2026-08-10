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

export const StressHeader: React.FC<Props> = ({ moduleVersion, regionName }) => {
  return (
    <header className="overflow-hidden rounded-[20px] border border-[var(--am-border)] bg-[var(--am-bg-elevated)] px-5 py-5 shadow-[var(--am-shadow-md)]">
      <div className="flex flex-wrap items-center gap-x-3 gap-y-2">
        <PageTitleIcon icon={CircleGauge} />
        <h1 className="text-[30px] font-bold tracking-[-0.02em] text-[var(--am-text)]">
          Regional Water Stress
        </h1>
        {moduleVersion ? (
          <span className="rounded-full bg-[var(--am-bg-muted)] px-2.5 py-0.5 text-[13px] font-medium text-[var(--am-text-tertiary)]">
            Stress Intelligence v{moduleVersion}
          </span>
        ) : null}
      </div>
      <p className="mt-1.5 text-[17px] text-[var(--am-text-secondary)]">
        View the overall health of your water system
        {regionName ? `, currently focused on ${regionName}` : ''}.
      </p>
      <p className="mt-2.5 text-[15px] leading-relaxed text-[var(--am-text-tertiary)]">
        <span className="font-medium text-[var(--am-text-secondary)]">Technical: </span>
        A per-region fusion of demand, reservoir storage, rainfall, groundwater, population and
        recent history, each with its own published weight shown in the breakdown below. This is
        scoped to one region and is deliberately separate from the system-wide Water Stress Index
        on the dashboard, which fuses shortage, groundwater, leakage, demand and climate across the
        whole network.
      </p>
    </header>
  );
};
