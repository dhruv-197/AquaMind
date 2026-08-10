import React from 'react';
import { LayoutGrid } from 'lucide-react';
import { Skeleton, SkeletonCard, SkeletonMap } from '../../ui/Skeleton';
import { PageTitleIcon } from '../../ui/PageTitleIcon';
import { SectionTitle } from './ExecutiveKpis';

/**
 * The command center layout, rendered before the first-view telemetry lands.
 *
 * Mirrors the real header / KPI / map / prediction structure so the page does
 * not reflow when data arrives, and shows no numbers at all — a placeholder
 * zero would be indistinguishable from a real reading.
 */
export const CommandCenterSkeleton: React.FC = () => (
  <div className="space-y-5 pb-8" aria-busy="true" aria-label="Loading operations dashboard">
    <section className="overflow-hidden rounded-[var(--am-radius-xl)] bg-[var(--am-bg-elevated)] p-5 shadow-[var(--am-shadow-md)] sm:p-6">
      <div className="flex flex-col gap-5 xl:flex-row xl:items-end xl:justify-between">
        <div className="min-w-0">
          <p className="text-[14px] font-semibold uppercase tracking-[0.08em] text-[var(--am-text-tertiary)]">
            AquaMind Operations
          </p>
          <div className="mt-1 flex items-center gap-3">
            <PageTitleIcon icon={LayoutGrid} />
            <h1 className="text-[30px] font-bold tracking-[-0.02em] text-[var(--am-text)] sm:text-[32px]">
              Operations Dashboard
            </h1>
          </div>
          <p className="mt-1.5 max-w-2xl text-[17px] text-[var(--am-text-secondary)]">
            Loading current conditions, upcoming risks, and recommended actions...
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          {Array.from({ length: 4 }).map((_, i) => (
            <Skeleton key={i} className="h-10 w-36" />
          ))}
        </div>
      </div>

      <div className="mt-6 grid grid-cols-2 gap-3 md:grid-cols-3 xl:grid-cols-6">
        {Array.from({ length: 6 }).map((_, i) => (
          <div key={i} className="rounded-[14px] bg-[var(--am-bg-muted)] p-3.5">
            <Skeleton className="h-3 w-20" />
            <Skeleton className="mt-3 h-6 w-24" />
          </div>
        ))}
      </div>
    </section>

    <section>
      <SectionTitle
        title="Key Metrics"
        subtitle="Live view of demand, storage, water stress, and climate conditions."
      />
      <div className="mt-4 grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-3 2xl:grid-cols-5">
        {Array.from({ length: 5 }).map((_, i) => (
          <SkeletonCard key={i} />
        ))}
      </div>
    </section>

    <SkeletonMap />

    <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-5">
      {Array.from({ length: 5 }).map((_, i) => (
        <SkeletonCard key={i} />
      ))}
    </div>
  </div>
);

export default CommandCenterSkeleton;
