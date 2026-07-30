/**
 * AquaMind design tokens. Apple-inspired enterprise system.
 * Prefer CSS variables (index.css) in components; use these for JS (charts, inline).
 */

export const colors = {
  bg: '#F5F5F7',
  bgElevated: '#FFFFFF',
  bgMuted: '#EFEFF2',
  bgHover: '#E8E8ED',

  text: '#1D1D1F',
  textSecondary: '#6E6E73',
  textTertiary: '#8E8E93',
  textInverse: '#FFFFFF',

  border: 'rgba(0, 0, 0, 0.06)',
  borderStrong: 'rgba(0, 0, 0, 0.12)',
  divider: 'rgba(0, 0, 0, 0.08)',

  accent: '#007AFF',
  accentHover: '#0066D6',
  accentSoft: 'rgba(0, 122, 255, 0.10)',

  success: '#34C759',
  successSoft: 'rgba(52, 199, 89, 0.12)',
  warning: '#FF9500',
  warningSoft: 'rgba(255, 149, 0, 0.12)',
  danger: '#FF3B30',
  dangerSoft: 'rgba(255, 59, 48, 0.12)',

  /* Dark theme (calm, not neon) */
  darkBg: '#000000',
  darkBgElevated: '#1C1C1E',
  darkBgMuted: '#2C2C2E',
  darkText: '#F5F5F7',
  darkTextSecondary: '#98989D',
  darkBorder: 'rgba(255, 255, 255, 0.08)',
  darkAccent: '#0A84FF',
} as const;

export const spacing = {
  0: 0,
  1: 4,
  2: 8,
  3: 12,
  4: 16,
  5: 20,
  6: 24,
  7: 32,
  8: 40,
  9: 48,
  10: 64,
} as const;

export const radius = {
  sm: 8,
  md: 12,
  lg: 16,
  xl: 20,
  '2xl': 24,
  full: 9999,
} as const;

export const elevation = {
  none: 'none',
  sm: '0 1px 2px rgba(0, 0, 0, 0.04), 0 1px 3px rgba(0, 0, 0, 0.06)',
  md: '0 4px 12px rgba(0, 0, 0, 0.06), 0 1px 3px rgba(0, 0, 0, 0.04)',
  lg: '0 12px 32px rgba(0, 0, 0, 0.08), 0 2px 6px rgba(0, 0, 0, 0.04)',
  hover: '0 16px 40px rgba(0, 0, 0, 0.10), 0 4px 12px rgba(0, 0, 0, 0.05)',
} as const;

export const motion = {
  fast: '150ms',
  normal: '200ms',
  slow: '250ms',
  ease: 'cubic-bezier(0.25, 0.1, 0.25, 1)',
} as const;

export const typography = {
  fontSans:
    '-apple-system, BlinkMacSystemFont, "SF Pro Text", "SF Pro Display", "Segoe UI", system-ui, sans-serif',
  fontMono: 'ui-monospace, "SF Mono", Menlo, Monaco, Consolas, monospace',
  title: { size: '30px', weight: 700, tracking: '-0.02em', lineHeight: 1.15 },
  section: { size: '18px', weight: 600, tracking: '-0.01em', lineHeight: 1.3 },
  body: { size: '17px', weight: 400, tracking: '-0.01em', lineHeight: 1.5 },
  caption: { size: '15px', weight: 400, tracking: '0', lineHeight: 1.4 },
  micro: { size: '14px', weight: 500, tracking: '0.02em', lineHeight: 1.35 },
  kpi: { size: '32px', weight: 600, tracking: '-0.03em', lineHeight: 1.1 },
} as const;

export type RiskTone = 'success' | 'warning' | 'danger' | 'accent' | 'neutral';

export function riskTone(level?: string | null): RiskTone {
  const r = (level || '').toUpperCase();
  if (r.includes('CRITICAL') || r.includes('HIGH') || r === 'DANGER') return 'danger';
  if (r.includes('MODERATE') || r.includes('MEDIUM') || r.includes('WARN')) return 'warning';
  if (r.includes('HEALTHY') || r.includes('LOW') || r.includes('OK')) return 'success';
  return 'neutral';
}
