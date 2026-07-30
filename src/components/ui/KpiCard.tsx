import React, { useEffect, useState } from 'react';
import { TrendingDown, TrendingUp, Minus } from 'lucide-react';
import { StatusBadge } from './Badge';
import { InfoTooltip } from './InfoTooltip';
import type { RiskTone } from '../../design-system/tokens';

export type KpiCardProps = {
  label: string;
  value: string;
  subtitle?: string;
  /** One-sentence explanation shown on the info icon */
  tooltip?: string;
  trend?: { direction: 'up' | 'down' | 'flat'; label?: string };
  status?: { label: string; tone?: RiskTone };
  sparkline?: number[];
  /** Comparison vs previous period, e.g. "+2.4% vs prior 7d" */
  comparison?: string;
  className?: string;
  /** Soft accent wash for visual differentiation */
  accent?: 'blue' | 'green' | 'orange' | 'red' | 'violet' | 'neutral';
};

function Sparkline({ values, stroke }: { values: number[]; stroke: string }) {
  if (values.length < 2) return null;
  const min = Math.min(...values);
  const max = Math.max(...values);
  const span = max - min || 1;
  const w = 80;
  const h = 32;
  const pts = values
    .map((v, i) => {
      const x = (i / (values.length - 1)) * w;
      const y = h - ((v - min) / span) * (h - 4) - 2;
      return `${x},${y}`;
    })
    .join(' ');
  const area = `0,${h} ${pts} ${w},${h}`;
  return (
    <svg width={w} height={h} viewBox={`0 0 ${w} ${h}`} className="shrink-0" aria-hidden>
      <polygon fill={stroke} fillOpacity="0.12" points={area} />
      <polyline
        fill="none"
        stroke={stroke}
        strokeWidth="1.75"
        strokeLinecap="round"
        strokeLinejoin="round"
        points={pts}
      />
    </svg>
  );
}

const accentStroke: Record<NonNullable<KpiCardProps['accent']>, string> = {
  blue: '#007AFF',
  green: '#34C759',
  orange: '#FF9500',
  red: '#FF3B30',
  violet: '#5856D6',
  neutral: '#8E8E93',
};

function AnimatedValue({ value }: { value: string }) {
  const [show, setShow] = useState(false);
  useEffect(() => {
    setShow(false);
    const t = requestAnimationFrame(() => setShow(true));
    return () => cancelAnimationFrame(t);
  }, [value]);
  return (
    <p
      className={`am-kpi-value text-[32px] font-semibold leading-none tracking-[-0.03em] text-[var(--am-text)] tabular-nums transition-opacity duration-300 ${
        show ? 'opacity-100' : 'opacity-40'
      }`}
    >
      {value}
    </p>
  );
}

export const KpiCard: React.FC<KpiCardProps> = ({
  label,
  value,
  subtitle,
  tooltip,
  trend,
  status,
  sparkline,
  comparison,
  className = '',
  accent = 'blue',
}) => {
  const TrendIcon =
    trend?.direction === 'up' ? TrendingUp : trend?.direction === 'down' ? TrendingDown : Minus;
  const stroke = accentStroke[accent];

  return (
    <div
      className={`am-kpi group relative overflow-hidden rounded-[16px] border border-[var(--am-border)] bg-[var(--am-bg-elevated)] p-5 shadow-[var(--am-shadow-sm)] transition-all duration-200 hover:border-[var(--am-border-strong,var(--am-border))] hover:shadow-[var(--am-shadow-md)] ${className}`}
    >
      <div
        className="pointer-events-none absolute inset-x-0 top-0 h-0.5 opacity-80"
        style={{ background: stroke }}
        aria-hidden
      />
      <div className="flex items-start justify-between gap-3">
        <div className="flex min-w-0 items-center gap-1.5">
          <p className="text-[14px] font-semibold uppercase tracking-[0.06em] text-[var(--am-text-secondary)]">
            {label}
          </p>
          {tooltip ? <InfoTooltip content={tooltip} label={`About ${label}`} /> : null}
        </div>
        {status ? <StatusBadge status={status.label} /> : null}
      </div>

      <div className="mt-3 flex items-end justify-between gap-3">
        <AnimatedValue value={value} />
        {sparkline ? <Sparkline values={sparkline} stroke={stroke} /> : null}
      </div>

      <div className="mt-3 flex flex-wrap items-center gap-x-2 gap-y-1 min-h-[18px]">
        {trend ? (
          <span
            className={`inline-flex items-center gap-1 text-[15px] font-medium ${
              trend.direction === 'up'
                ? 'text-[var(--am-danger)]'
                : trend.direction === 'down'
                  ? 'text-[var(--am-success)]'
                  : 'text-[var(--am-text-secondary)]'
            }`}
          >
            <TrendIcon className="h-3.5 w-3.5" strokeWidth={2.25} />
            {trend.label}
          </span>
        ) : null}
        {comparison ? (
          <span className="text-[15px] text-[var(--am-text-tertiary)]">{comparison}</span>
        ) : null}
        {subtitle ? <span className="text-[15px] text-[var(--am-text-tertiary)]">{subtitle}</span> : null}
      </div>
    </div>
  );
};

export default KpiCard;
