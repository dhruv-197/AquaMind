import React, { useId, useState } from 'react';
import { Info } from 'lucide-react';

export type InfoTooltipProps = {
  content: string;
  label?: string;
  className?: string;
};

/** Accessible info icon with hover/focus tooltip for KPI and metric explanations. */
export const InfoTooltip: React.FC<InfoTooltipProps> = ({
  content,
  label = 'More information',
  className = '',
}) => {
  const tipId = useId();
  const [open, setOpen] = useState(false);

  return (
    <span className={`relative inline-flex ${className}`}>
      <button
        type="button"
        aria-label={label}
        aria-describedby={open ? tipId : undefined}
        onMouseEnter={() => setOpen(true)}
        onMouseLeave={() => setOpen(false)}
        onFocus={() => setOpen(true)}
        onBlur={() => setOpen(false)}
        className="inline-flex h-5 w-5 items-center justify-center rounded-full text-[var(--am-text-tertiary)] transition-colors hover:bg-[var(--am-bg-muted)] hover:text-[var(--am-text-secondary)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--am-accent)]"
      >
        <Info className="h-3.5 w-3.5" strokeWidth={2} aria-hidden />
      </button>
      {open ? (
        <span
          id={tipId}
          role="tooltip"
          className="absolute left-1/2 top-full z-50 mt-2 w-56 -translate-x-1/2 rounded-lg border border-[var(--am-border)] bg-[var(--am-bg-elevated)] px-3 py-2 text-left text-[15px] font-normal normal-case tracking-normal leading-relaxed text-[var(--am-text-secondary)] shadow-[var(--am-shadow-lg)]"
        >
          {content}
        </span>
      ) : null}
    </span>
  );
};

export default InfoTooltip;
