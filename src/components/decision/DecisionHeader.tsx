import React from 'react';
import { ListChecks } from 'lucide-react';
import { PageTitleIcon } from '../ui/PageTitleIcon';

type Props = {
  ready: boolean;
  loading?: boolean;
  moduleVersion?: string;
  demandReady?: boolean;
  reservoirReady?: boolean;
  stressReady?: boolean;
  onRefresh?: () => void;
  refreshing?: boolean;
};

export const DecisionHeader: React.FC<Props> = ({ onRefresh, refreshing }) => {
  return (
    <header className="overflow-hidden rounded-[20px] border border-[var(--am-border)] bg-[var(--am-bg-elevated)] px-5 py-5 shadow-[var(--am-shadow-md)]">
      <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
        <div>
          <div className="flex items-center gap-3">
            <PageTitleIcon icon={ListChecks} />
            <h1 className="text-[30px] font-bold tracking-[-0.02em] text-[var(--am-text)]">
              Recommended Actions
            </h1>
          </div>
          <p className="mt-1.5 text-[17px] text-[var(--am-text-secondary)]">
            AI prioritizes the most important actions to take.
          </p>
          <p className="mt-2 text-[15px] leading-relaxed text-[var(--am-text-tertiary)]">
            <span className="font-medium text-[var(--am-text-secondary)]">Technical: </span>
            Actions are ranked using demand, reservoir, and water stress predictions.
          </p>
        </div>
        {onRefresh ? (
          <button
            type="button"
            onClick={onRefresh}
            disabled={refreshing}
            className="am-btn inline-flex h-11 items-center justify-center gap-2 rounded-[14px] bg-[var(--am-accent)] px-5 text-[17px] font-semibold text-white shadow-[var(--am-shadow-sm)] transition-colors hover:bg-[var(--am-accent-hover)] disabled:opacity-40"
          >
            <ListChecks className="h-4 w-4" strokeWidth={2.25} />
            {refreshing ? 'Optimizing…' : 'Generate recommendations'}
          </button>
        ) : null}
      </div>
    </header>
  );
};
