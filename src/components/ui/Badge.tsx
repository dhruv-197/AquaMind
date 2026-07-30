import React from 'react';

export type BadgeTone = 'neutral' | 'accent' | 'success' | 'warning' | 'danger' | 'info';

const toneClass: Record<BadgeTone, string> = {
  neutral: 'bg-[var(--am-bg-muted)] text-[var(--am-text-secondary)]',
  accent: 'bg-[var(--am-accent-soft)] text-[var(--am-accent)]',
  success: 'bg-[var(--am-success-soft)] text-[var(--am-success)]',
  warning: 'bg-[var(--am-warning-soft)] text-[var(--am-warning)]',
  danger: 'bg-[var(--am-danger-soft)] text-[var(--am-danger)]',
  info: 'bg-[rgba(90,200,250,0.14)] text-[#0A84FF]',
};

export type BadgeProps = {
  children: React.ReactNode;
  tone?: BadgeTone;
  className?: string;
  dot?: boolean;
};

export const Badge: React.FC<BadgeProps> = ({ children, tone = 'neutral', className = '', dot }) => (
  <span
    className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-[14px] font-semibold tracking-wide ${toneClass[tone]} ${className}`}
  >
    {dot ? <span className="h-1.5 w-1.5 rounded-full bg-current opacity-80" aria-hidden /> : null}
    {children}
  </span>
);

/** Unified status vocabulary across AquaMind. */
export type StatusKind =
  | 'healthy'
  | 'moderate'
  | 'high'
  | 'critical'
  | 'ready'
  | 'training'
  | 'offline'
  | 'success'
  | 'warning'
  | 'danger'
  | 'accent'
  | 'neutral';

const STATUS_MAP: Record<StatusKind, { label: string; tone: BadgeTone }> = {
  healthy: { label: 'Healthy', tone: 'success' },
  moderate: { label: 'Moderate', tone: 'warning' },
  high: { label: 'High', tone: 'warning' },
  critical: { label: 'Critical', tone: 'danger' },
  ready: { label: 'Ready', tone: 'success' },
  training: { label: 'Training', tone: 'info' },
  offline: { label: 'Offline', tone: 'neutral' },
  success: { label: 'Success', tone: 'success' },
  warning: { label: 'Warning', tone: 'warning' },
  danger: { label: 'Danger', tone: 'danger' },
  accent: { label: 'Active', tone: 'accent' },
  neutral: { label: 'Neutral', tone: 'neutral' },
};

export function statusFromLabel(raw?: string | null): StatusKind {
  const s = (raw || '').toLowerCase().trim();
  if (s.includes('critical') || s.includes('offline')) return s.includes('offline') ? 'offline' : 'critical';
  if (s.includes('train')) return 'training';
  if (s.includes('ready') || s.includes('healthy') || s.includes('low') || s === 'ok') return s.includes('ready') ? 'ready' : 'healthy';
  if (s.includes('high') || s.includes('warn')) return s.includes('high') ? 'high' : 'warning';
  if (s.includes('moderate') || s.includes('medium')) return 'moderate';
  return 'neutral';
}

export const StatusBadge: React.FC<{ status?: string | null; kind?: StatusKind; className?: string }> = ({
  status,
  kind,
  className = '',
}) => {
  const resolved = kind || statusFromLabel(status);
  const meta = STATUS_MAP[resolved];
  return (
    <Badge tone={meta.tone} dot className={className}>
      {status ? String(status) : meta.label}
    </Badge>
  );
};

export default Badge;
