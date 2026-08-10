/**
 * Sparkline data derived from real series only.
 *
 * A KPI sparkline is a claim about history. Padding one with invented leading
 * points draws a trend that was never measured, so every helper here returns
 * `undefined` rather than fabricate a shape — and `KpiCard` omits the sparkline
 * when it gets `undefined`.
 */

/** Any forecast/telemetry point that carries the fields our KPI cards chart. */
export type SparklineSeriesPoint = {
  historical?: number | null;
  forecast?: number | null;
  confidence?: number | null;
};

export type SparklineKey = 'historical' | 'forecast' | 'confidence';

const MAX_POINTS = 14;
const MIN_POINTS = 2;

/**
 * Pull one numeric channel out of a series for a KPI sparkline.
 *
 * Returns `undefined` unless at least two finite observations exist, so a card
 * with thin data renders no line instead of a misleading one.
 */
export function sparklineFrom(
  series: readonly SparklineSeriesPoint[] | null | undefined,
  key: SparklineKey,
  maxPoints: number = MAX_POINTS,
): number[] | undefined {
  if (!series || series.length === 0) return undefined;

  const values: number[] = [];
  for (const point of series) {
    const raw = point?.[key];
    if (typeof raw === 'number' && Number.isFinite(raw)) values.push(raw);
  }

  if (values.length < MIN_POINTS) return undefined;

  // Keep the most recent window: a KPI sparkline reads as "lately", not "ever".
  const window = values.length > maxPoints ? values.slice(values.length - maxPoints) : values;

  // A flat line has no trend to show and renders as a meaningless straight bar.
  const first = window[0];
  if (window.every((v) => v === first)) return undefined;

  return window;
}
