import { colors } from './tokens';

/** Shared Recharts theme. Apple-like, no gradients, no neon. */
export const chartTheme = {
  colors: {
    primary: colors.accent,
    secondary: '#5856D6',
    tertiary: '#5AC8FA',
    success: colors.success,
    warning: colors.warning,
    danger: colors.danger,
    muted: colors.textTertiary,
    historical: '#8E8E93',
    forecast: colors.accent,
    confidence: 'rgba(0, 122, 255, 0.12)',
    grid: 'rgba(0, 0, 0, 0.06)',
    axis: colors.textTertiary,
  },
  dark: {
    primary: colors.darkAccent,
    secondary: '#5E5CE6',
    tertiary: '#64D2FF',
    success: '#30D158',
    warning: '#FF9F0A',
    danger: '#FF453A',
    muted: colors.darkTextSecondary,
    historical: '#98989D',
    forecast: colors.darkAccent,
    confidence: 'rgba(10, 132, 255, 0.18)',
    grid: 'rgba(255, 255, 255, 0.06)',
    axis: colors.darkTextSecondary,
  },
  fontFamily:
    '-apple-system, BlinkMacSystemFont, "SF Pro Text", "Segoe UI", system-ui, sans-serif',
  tooltip: {
    light: {
      background: '#FFFFFF',
      border: '1px solid rgba(0,0,0,0.08)',
      color: colors.text,
      radius: 12,
      shadow: '0 8px 24px rgba(0,0,0,0.12)',
    },
    dark: {
      background: '#1C1C1E',
      border: '1px solid rgba(255,255,255,0.1)',
      color: colors.darkText,
      radius: 12,
      shadow: '0 8px 24px rgba(0,0,0,0.4)',
    },
  },
  height: {
    sm: 220,
    md: 320,
    lg: 400,
    xl: 480,
  },
} as const;

export function getChartPalette(isLight: boolean) {
  return isLight ? chartTheme.colors : chartTheme.dark;
}
