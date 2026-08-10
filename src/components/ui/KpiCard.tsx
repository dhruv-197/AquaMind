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

function shortStatusLabel(raw: string): string {
  const s = raw.trim();
  if (!s) return s;
  // Prefer compact title-case so badges never crowd the title row.
  return s
    .toLowerCase()
    .split(/[\s_]+/)
    .map((w) => w.charAt(0).toUpperCase() + w.slice(1))
    .join(' ');
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
      className={`am-kpi group relative rounded-[16px] border border-[var(--am-border)] bg-[var(--am-bg-elevated)] p-5 shadow-[var(--am-shadow-sm)] transition-all duration-200 hover:border-[var(--am-border-strong,var(--am-border))] hover:shadow-[var(--am-shadow-md)] ${className}`}
    >
      <div
        className="pointer-events-none absolute inset-x-0 top-0 h-0.5 rounded-t-[16px] opacity-80"
        style={{ background: stroke }}
        aria-hidden
      />

      {/* Row 1: title + fixed info icon (never shares space with badge) */}
      <div className="flex min-h-6 items-center gap-2">
        <p className="min-w-0 flex-1 truncate text-[14px] font-semibold uppercase tracking-[0.06em] text-[var(--am-text-secondary)]">
          {label}
        </p>
        <div className="ml-auto flex h-6 w-6 shrink-0 items-center justify-center">
          {tooltip ? <InfoTooltip content={tooltip} label={`About ${label}`} /> : null}
        </div>
      </div>

      {/* Row 2: status badge alone — cannot overlap the title */}
      <div className="mt-1.5 flex min-h-[1.5rem] items-center">
        {status ? (
          <StatusBadge
            status={shortStatusLabel(status.label)}
            className="max-w-full truncate whitespace-nowrap text-[12px]"
          />
        ) : (
          <span className="inline-block h-6" aria-hidden />
        )}
      </div>

      <div className="mt-3 flex items-end justify-between gap-3">
        <AnimatedValue value={value} />
        {sparkline ? <Sparkline values={sparkline} stroke={stroke} /> : null}
      </div>

      <div className="mt-3 flex min-h-[18px] flex-wrap items-center gap-x-2 gap-y-1">
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
