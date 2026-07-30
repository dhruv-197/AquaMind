import React from 'react';
import type { LucideIcon } from 'lucide-react';

type Props = {
  icon: LucideIcon;
  className?: string;
};

/** Shared accent icon used next to page titles (matches sidebar weight). */
export const PageTitleIcon: React.FC<Props> = ({ icon: Icon, className = '' }) => (
  <div
    className={`flex h-11 w-11 shrink-0 items-center justify-center rounded-xl border border-[var(--am-border)] bg-[var(--am-accent-soft)] text-[var(--am-accent)] ${className}`}
  >
    <Icon className="h-5 w-5" strokeWidth={2.25} aria-hidden />
  </div>
);

export default PageTitleIcon;
