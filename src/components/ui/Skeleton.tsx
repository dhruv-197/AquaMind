import React from 'react';

type SkeletonProps = {
  className?: string;
};

export const Skeleton: React.FC<SkeletonProps & { style?: React.CSSProperties }> = ({
  className = '',
  style,
}) => (
  <div
    className={`animate-pulse rounded-[12px] bg-[var(--am-bg-muted)] ${className}`}
    style={style}
    aria-hidden
  />
);

export const SkeletonCard: React.FC<{ className?: string }> = ({ className = '' }) => (
  <div
    className={`rounded-[var(--am-radius-xl)] bg-[var(--am-bg-elevated)] p-5 shadow-[var(--am-shadow-md)] ${className}`}
    aria-busy="true"
    aria-label="Loading"
  >
    <Skeleton className="h-3 w-24" />
    <Skeleton className="mt-4 h-8 w-32" />
    <Skeleton className="mt-3 h-3 w-40" />
  </div>
);

export const SkeletonChart: React.FC<{ height?: number; className?: string }> = ({
  height = 320,
  className = '',
}) => (
  <div
    className={`rounded-[var(--am-radius-xl)] bg-[var(--am-bg-elevated)] p-5 shadow-[var(--am-shadow-md)] ${className}`}
    style={{ minHeight: height }}
    aria-busy="true"
    aria-label="Loading chart"
  >
    <Skeleton className="mb-4 h-4 w-40" />
    <div className="flex h-[240px] items-end gap-2 pt-4">
      {Array.from({ length: 12 }).map((_, i) => (
        <Skeleton key={i} className="flex-1" style={{ height: `${30 + ((i * 17) % 60)}%` } as React.CSSProperties} />
      ))}
    </div>
  </div>
);

export const SkeletonTable: React.FC<{ rows?: number }> = ({ rows = 5 }) => (
  <div className="rounded-[var(--am-radius-xl)] bg-[var(--am-bg-elevated)] p-4 shadow-[var(--am-shadow-md)]" aria-busy="true">
    <Skeleton className="mb-4 h-4 w-48" />
    <div className="space-y-3">
      {Array.from({ length: rows }).map((_, i) => (
        <Skeleton key={i} className="h-10 w-full" />
      ))}
    </div>
  </div>
);

export const SkeletonMap: React.FC<{ height?: number }> = ({ height = 380 }) => (
  <div
    className="overflow-hidden rounded-[var(--am-radius-xl)] bg-[var(--am-bg-elevated)] shadow-[var(--am-shadow-md)]"
    style={{ height }}
    aria-busy="true"
    aria-label="Loading map"
  >
    <div className="border-b border-[var(--am-divider)] px-4 py-3">
      <Skeleton className="h-4 w-44" />
      <Skeleton className="mt-2 h-3 w-64" />
    </div>
    <div className="relative h-[calc(100%-64px)] bg-[var(--am-bg-muted)]">
      <Skeleton className="absolute left-4 top-4 h-24 w-40" />
      <Skeleton className="absolute right-4 top-4 h-28 w-36" />
    </div>
  </div>
);

export default Skeleton;
