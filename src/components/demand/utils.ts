import type { ForecastUnit, SeriesPoint, TimeRangeKey } from './types';
import { HORIZON_MAX } from './types';

export function unitToDays(value: number, unit: ForecastUnit): number {
  const mult = { days: 1, weeks: 7, months: 30, years: 365 }[unit];
  return value * mult;
}

export function validateHorizon(value: number, unit: ForecastUnit): string | null {
  if (!Number.isFinite(value) || value < 1) return 'Enter a value of at least 1.';
  const max = HORIZON_MAX[unit];
  if (value > max) return `Maximum for ${unit} is ${max}.`;
  return null;
}

export function formatMgd(n: number | null | undefined, digits = 1): string {
  if (n == null || Number.isNaN(n)) return '-';
  return `${n.toFixed(digits)} MGD`;
}

export function formatPct(n: number | null | undefined, digits = 1): string {
  if (n == null || Number.isNaN(n)) return '-';
  return `${n.toFixed(digits)}%`;
}

export function formatDateLabel(iso: string): string {
  const d = new Date(`${iso}T00:00:00`);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleDateString(undefined, { day: '2-digit', month: 'short' });
}

export function filterSeriesByRange(series: SeriesPoint[], range: TimeRangeKey): SeriesPoint[] {
  if (!series.length || range === 'ALL') return series;
  // Period labels for weeks/months/years are not ISO dates. Keep full series
  const sample = series[series.length - 1]?.date || '';
  if (!/^\d{4}-\d{2}-\d{2}/.test(sample)) return series;

  const days = { '1M': 30, '3M': 90, '6M': 180, '1Y': 365 }[range];
  const last = series[series.length - 1];
  const end = new Date(`${last.date}T00:00:00`).getTime();
  if (Number.isNaN(end)) return series;
  const start = end - days * 86400000;
  return series.filter((p) => {
    const t = new Date(`${p.date}T00:00:00`).getTime();
    return !Number.isNaN(t) && t >= start;
  });
}

export function seriesToCsv(series: SeriesPoint[]): string {
  const header = [
    'date',
    'historical_mgd',
    'forecast_mgd',
    'lower_mgd',
    'upper_mgd',
    'confidence',
    'risk',
    'daily_change_mgd',
    'rolling_avg_mgd',
  ];
  const rows = series.map((p) =>
    [
      p.date,
      p.historical ?? '',
      p.forecast ?? '',
      p.lower ?? '',
      p.upper ?? '',
      p.confidence ?? '',
      p.risk ?? '',
      p.daily_change ?? '',
      p.rolling_avg ?? '',
    ].join(','),
  );
  return [header.join(','), ...rows].join('\n');
}

export function downloadText(filename: string, content: string, mime = 'text/csv;charset=utf-8'): void {
  const blob = new Blob([content], { type: mime });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}

/** Export the first SVG inside a container as PNG. */
export async function exportChartPng(container: HTMLElement | null, filename: string): Promise<void> {
  if (!container) return;
  const svg = container.querySelector('svg');
  if (!svg) return;
  const clone = svg.cloneNode(true) as SVGSVGElement;
  const bbox = svg.getBoundingClientRect();
  const width = Math.max(800, Math.ceil(bbox.width));
  const height = Math.max(360, Math.ceil(bbox.height));
  clone.setAttribute('width', String(width));
  clone.setAttribute('height', String(height));
  const xml = new XMLSerializer().serializeToString(clone);
  const svgBlob = new Blob([xml], { type: 'image/svg+xml;charset=utf-8' });
  const url = URL.createObjectURL(svgBlob);
  const img = new Image();
  await new Promise<void>((resolve, reject) => {
    img.onload = () => resolve();
    img.onerror = () => reject(new Error('PNG export failed'));
    img.src = url;
  });
  const canvas = document.createElement('canvas');
  canvas.width = width;
  canvas.height = height;
  const ctx = canvas.getContext('2d');
  if (!ctx) return;
  ctx.fillStyle = '#ffffff';
  ctx.fillRect(0, 0, width, height);
  ctx.drawImage(img, 0, 0, width, height);
  URL.revokeObjectURL(url);
  const png = canvas.toDataURL('image/png');
  const a = document.createElement('a');
  a.href = png;
  a.download = filename;
  a.click();
}
