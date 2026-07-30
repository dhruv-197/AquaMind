import React from 'react';
import { Inbox } from 'lucide-react';
import { Button } from './Button';

export type EmptyStateProps = {
  title: string;
  description?: string;
  icon?: React.ReactNode;
  primaryAction?: { label: string; onClick: () => void; loading?: boolean };
  secondaryAction?: { label: string; onClick: () => void };
  className?: string;
};

export const EmptyState: React.FC<EmptyStateProps> = ({
  title,
  description,
  icon,
  primaryAction,
  secondaryAction,
  className = '',
}) => (
  <div
    className={`flex flex-col items-center justify-center rounded-[var(--am-radius-xl)] bg-[var(--am-bg-elevated)] px-6 py-12 text-center shadow-[var(--am-shadow-md)] ${className}`}
    role="status"
  >
    <div className="mb-4 flex h-12 w-12 items-center justify-center rounded-2xl bg-[var(--am-bg-muted)] text-[var(--am-text-tertiary)]">
      {icon || <Inbox className="h-5 w-5" strokeWidth={1.75} />}
    </div>
    <h3 className="text-[18px] font-semibold tracking-tight text-[var(--am-text)]">{title}</h3>
    {description ? (
      <p className="mt-2 max-w-md text-[16px] leading-relaxed text-[var(--am-text-secondary)]">{description}</p>
    ) : null}
    {(primaryAction || secondaryAction) && (
      <div className="mt-6 flex flex-wrap items-center justify-center gap-2">
        {primaryAction ? (
          <Button onClick={primaryAction.onClick} loading={primaryAction.loading}>
            {primaryAction.label}
          </Button>
        ) : null}
        {secondaryAction ? (
          <Button variant="secondary" onClick={secondaryAction.onClick}>
            {secondaryAction.label}
          </Button>
        ) : null}
      </div>
    )}
  </div>
);

export default EmptyState;
