import React from 'react';
import type { LucideIcon } from 'lucide-react';
import { PageTitleIcon } from './PageTitleIcon';

export type PageHeaderProps = {
  title: string;
  subtitle?: string;
  icon?: LucideIcon;
  actions?: React.ReactNode;
  breadcrumb?: React.ReactNode;
  className?: string;
};

export const PageHeader: React.FC<PageHeaderProps> = ({
  title,
  subtitle,
  icon,
  actions,
  breadcrumb,
  className = '',
}) => (
  <header className={`mb-6 flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between ${className}`}>
    <div className="min-w-0">
      {breadcrumb ? <div className="mb-2 text-[15px] text-[var(--am-text-tertiary)]">{breadcrumb}</div> : null}
      <div className="flex items-center gap-3">
        {icon ? <PageTitleIcon icon={icon} /> : null}
        <h1 className="text-[30px] font-bold tracking-[-0.02em] leading-tight text-[var(--am-text)]">{title}</h1>
      </div>
      {subtitle ? (
        <p className="mt-1.5 max-w-2xl text-[17px] leading-relaxed text-[var(--am-text-secondary)]">{subtitle}</p>
      ) : null}
    </div>
    {actions ? <div className="flex flex-wrap items-center gap-2 shrink-0">{actions}</div> : null}
  </header>
);

export default PageHeader;
