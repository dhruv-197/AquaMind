import React, { useEffect, useId, useLayoutEffect, useRef, useState } from 'react';
import { createPortal } from 'react-dom';
import { Info } from 'lucide-react';

export type InfoTooltipProps = {
  content: string;
  label?: string;
  className?: string;
};

/**
 * Accessible info icon. Tooltip is portaled to document.body so it never
 * clips inside overflow-hidden KPI / map / card containers.
 */
export const InfoTooltip: React.FC<InfoTooltipProps> = ({
  content,
  label = 'More information',
  className = '',
}) => {
  const tipId = useId();
  const btnRef = useRef<HTMLButtonElement>(null);
  const [open, setOpen] = useState(false);
  const [coords, setCoords] = useState<{ top: number; left: number } | null>(null);

  const updatePosition = () => {
    const el = btnRef.current;
    if (!el) return;
    const rect = el.getBoundingClientRect();
    const tipWidth = 224; // w-56
    const tipHeight = 96;
    const gap = 8;
    // Anchor under the icon and grow rightward so the tip never covers the
    // card title sitting to the left of the (i) control.
    let left = rect.left;
    left = Math.max(8, Math.min(left, window.innerWidth - tipWidth - 8));
    let top = rect.bottom + gap;
    if (top + tipHeight > window.innerHeight) {
      top = Math.max(8, rect.top - gap - tipHeight);
    }
    setCoords({ top, left });
  };

  useLayoutEffect(() => {
    if (!open) return;
    updatePosition();
  }, [open]);

  useEffect(() => {
    if (!open) return;
    const onReposition = () => updatePosition();
    window.addEventListener('scroll', onReposition, true);
    window.addEventListener('resize', onReposition);
    return () => {
      window.removeEventListener('scroll', onReposition, true);
      window.removeEventListener('resize', onReposition);
    };
  }, [open]);

  return (
    <span className={`relative inline-flex shrink-0 ${className}`}>
      <button
        ref={btnRef}
        type="button"
        aria-label={label}
        aria-describedby={open ? tipId : undefined}
        onMouseEnter={() => setOpen(true)}
        onMouseLeave={() => setOpen(false)}
        onFocus={() => setOpen(true)}
        onBlur={() => setOpen(false)}
        className="inline-flex h-6 w-6 shrink-0 items-center justify-center rounded-full text-[var(--am-text-tertiary)] transition-colors hover:bg-[var(--am-bg-muted)] hover:text-[var(--am-text-secondary)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--am-accent)]"
      >
        <Info className="h-3.5 w-3.5" strokeWidth={2} aria-hidden />
      </button>
      {open && coords && typeof document !== 'undefined'
        ? createPortal(
            <span
              id={tipId}
              role="tooltip"
              style={{ position: 'fixed', top: coords.top, left: coords.left, zIndex: 1300 }}
              className="pointer-events-none w-56 rounded-lg border border-[var(--am-border)] bg-[var(--am-bg-elevated)] px-3 py-2 text-left text-[14px] font-normal normal-case tracking-normal leading-relaxed text-[var(--am-text-secondary)] shadow-[var(--am-shadow-lg)]"
            >
              {content}
            </span>,
            document.body,
          )
        : null}
    </span>
  );
};

export default InfoTooltip;
