import React from 'react';
import {
  Activity,
  Download,
  FileBarChart2,
  LayoutGrid,
  RefreshCw,
  ShieldCheck,
  SlidersHorizontal,
} from 'lucide-react';
import { Badge } from '../../ui/Badge';
import { Button } from '../../ui/Button';
import { PageTitleIcon } from '../../ui/PageTitleIcon';
import type { RiskTone } from '../../../design-system/tokens';

type Props = {
  securityScore: number | null;
  systemHealth: { label: string; tone: RiskTone };
  /**
   * Weighted WSI inputs the backend reported as usable this cycle, or null
   * while the fusion has not answered. Never a synthesized confidence figure.
   */
  fusionInputs: { live: number; total: number } | null;
  lastUpdated: string;
  municipalStatus: { label: string; tone: RiskTone };
  criticalAlerts: number | null;
  regionLabel?: string | null;
  onGenerateReport: () => void;
  onScenarioFocus: () => void;
  onExportPdf: () => void;
  onRefresh?: () => void;
};

export const ExecutiveHeader: React.FC<Props> = ({
  securityScore,
  systemHealth,
  fusionInputs,
  lastUpdated,
  municipalStatus,
  criticalAlerts,
  regionLabel,
  onGenerateReport,
  onScenarioFocus,
  onExportPdf,
  onRefresh,
}) => (
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
          See current conditions, upcoming risks, and recommended actions
          {regionLabel ? ` · focused on ${regionLabel}` : ''}.
        </p>
      </div>

      <div className="flex flex-wrap gap-2">
        <Button variant="primary" icon={<FileBarChart2 className="h-4 w-4" strokeWidth={2} />} onClick={onGenerateReport}>
          Generate Executive Report
        </Button>
        <Button variant="secondary" icon={<SlidersHorizontal className="h-4 w-4" strokeWidth={2} />} onClick={onScenarioFocus}>
          Scenario Simulation
        </Button>
        <Button variant="ghost" icon={<Download className="h-4 w-4" strokeWidth={2} />} onClick={onExportPdf}>
          Export PDF
        </Button>
        {onRefresh ? (
          <Button variant="ghost" icon={<RefreshCw className="h-4 w-4" strokeWidth={2} />} onClick={onRefresh}>
            Refresh
          </Button>
        ) : null}
      </div>
    </div>

    <div className="mt-6 grid grid-cols-2 gap-3 md:grid-cols-3 xl:grid-cols-6">
      <HeroMetric
        label="Water Security Score"
        value={securityScore == null ? '-' : String(securityScore)}
        suffix={securityScore == null ? undefined : '/ 100'}
        icon={<ShieldCheck className="h-4 w-4" strokeWidth={2} />}
      />
      <HeroMetric label="System Health" value={systemHealth.label} badge={{ label: systemHealth.label, tone: systemHealth.tone }} />
      <HeroMetric
        label="Live Fusion Inputs"
        value={fusionInputs == null ? '-' : `${fusionInputs.live} / ${fusionInputs.total}`}
        suffix={fusionInputs == null ? undefined : 'reporting'}
        icon={<Activity className="h-4 w-4" strokeWidth={2} />}
      />
      <HeroMetric label="Last Updated" value={lastUpdated} />
      <HeroMetric
        label="Municipal Status"
        value={municipalStatus.label}
        badge={{ label: municipalStatus.label, tone: municipalStatus.tone }}
      />
      <HeroMetric
        label="Critical Alerts"
        value={criticalAlerts == null ? '-' : String(criticalAlerts)}
        badge={
          criticalAlerts == null
            ? { label: 'Unavailable', tone: 'neutral' }
            : {
                label: criticalAlerts > 0 ? 'Attention' : 'Clear',
                tone: criticalAlerts > 0 ? 'danger' : 'success',
              }
        }
      />
    </div>
  </section>
);

function HeroMetric({
  label,
  value,
  suffix,
  badge,
  icon,
}: {
  label: string;
  value: string;
  suffix?: string;
  badge?: { label: string; tone: RiskTone };
  icon?: React.ReactNode;
}) {
  return (
    <div className="rounded-[14px] bg-[var(--am-bg-muted)] p-3.5">
      <div className="flex items-center justify-between gap-2">
        <p className="text-[14px] font-semibold uppercase tracking-[0.06em] text-[var(--am-text-tertiary)]">
          {label}
        </p>
        {icon ? <span className="text-[var(--am-accent)]">{icon}</span> : null}
      </div>
      <div className="mt-2 flex items-baseline gap-1">
        <p className="text-[22px] font-semibold tracking-[-0.02em] tabular-nums text-[var(--am-text)]">{value}</p>
        {suffix ? <span className="text-[15px] text-[var(--am-text-tertiary)]">{suffix}</span> : null}
      </div>
      {badge ? (
        <div className="mt-2">
          <Badge tone={badge.tone === 'neutral' ? 'accent' : badge.tone}>{badge.label}</Badge>
        </div>
      ) : null}
    </div>
  );
}
