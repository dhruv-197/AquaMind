import React from 'react';
import type { DecisionWorkspaceData } from './types';
import { KpiCard } from '../ui/KpiCard';

type Props = {
  outcomes?: DecisionWorkspaceData['expected_outcomes'] | null;
  priority?: string | null;
  actionCount?: number;
};

function formatInr(n?: number | null) {
  if (n == null || Number.isNaN(n)) return '-';
  if (Math.abs(n) >= 1_000_000) return `₹${(n / 1_000_000).toFixed(1)}M`;
  if (Math.abs(n) >= 1_000) return `₹${(n / 1_000).toFixed(0)}K`;
  return `₹${n.toFixed(0)}`;
}

function priorityTone(priority?: string | null) {
  const p = (priority || '').toUpperCase();
  if (p.includes('CRITICAL') || p.includes('HIGH')) return 'danger' as const;
  if (p.includes('MEDIUM') || p.includes('MODERATE')) return 'warning' as const;
  if (p.includes('LOW')) return 'success' as const;
  return 'accent' as const;
}

export const DecisionKpiCards: React.FC<Props> = ({ outcomes, priority, actionCount }) => {
  return (
    <section className="grid grid-cols-2 gap-3 lg:grid-cols-3 xl:grid-cols-6">
      <KpiCard
        label="Priority level"
        value={(priority || '-').replace('_', ' ').toUpperCase()}
        subtitle="Top action urgency"
        tooltip="Urgency of the highest-ranked recommended action."
        status={priority ? { label: 'Priority', tone: priorityTone(priority) } : undefined}
      />
      <KpiCard
        label="Water saved"
        value={
          outcomes?.estimated_water_saved_mcm == null
            ? '-'
            : `${outcomes.estimated_water_saved_mcm.toFixed(1)} MCM`
        }
        subtitle="Across ranked plan"
        tooltip="Estimated water volume protected if recommended actions are applied."
      />
      <KpiCard
        label="Population protected"
        value={
          outcomes?.population_protected == null ? '-' : outcomes.population_protected.toLocaleString()
        }
        subtitle="At-risk population covered"
        tooltip="People who may benefit if the recommended actions are carried out."
      />
      <KpiCard
        label="Risk reduction"
        value={
          outcomes?.average_risk_reduction == null ? '-' : `${outcomes.average_risk_reduction.toFixed(0)}`
        }
        subtitle="Avg score (0-100)"
        tooltip="Average expected reduction in operational risk across the action plan."
      />
      <KpiCard
        label="Estimated cost"
        value={formatInr(outcomes?.estimated_cost_inr)}
        subtitle="Implementation cost"
        tooltip="Indicative cost to implement the recommended action set."
      />
      <KpiCard
        label="Actions queued"
        value={String(actionCount ?? outcomes?.actions_count ?? '-')}
        subtitle="In optimized plan"
        tooltip="Number of prioritized actions in the current recommendation set."
      />
    </section>
  );
};
