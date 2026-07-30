import React from 'react';

type Props = {
  range?: string;
  onRangeChange?: (range: any) => void;
  rightSlot?: React.ReactNode;
  subtitle?: string;
};

/** Slim bar for export actions only (chart window filters removed). */
export const ForecastToolbar: React.FC<Props> = ({ rightSlot, subtitle }) => {
  if (!rightSlot && !subtitle) return null;
  return (
    <div className="flex flex-wrap items-center justify-between gap-3 rounded-[16px] border border-[var(--am-border)] bg-[var(--am-bg-elevated)] px-4 py-2.5 shadow-[var(--am-shadow-sm)]">
      {subtitle ? <span className="text-[15px] text-[var(--am-text-secondary)]">{subtitle}</span> : <span />}
      {rightSlot}
    </div>
  );
};
