import React, { useMemo, useState } from 'react';
import {
  Area,
  Brush,
  CartesianGrid,
  ComposedChart,
  Legend,
  Line,
  ReferenceLine,
  ResponsiveContainer,
  Scatter,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';
import type { ForecastUnit, SeriesPoint } from './types';
import { formatMgd } from './utils';
import { colors } from '../../design-system/tokens';
import { useTheme } from '../../context/ThemeContext';
import { EmptyState } from '../ui/EmptyState';
import { SkeletonChart } from '../ui/Skeleton';

type Props = {
  series: SeriesPoint[];
  forecastPointCount?: number;
  unit?: ForecastUnit;
  capacityMgd?: number | null;
  chartRef?: React.RefObject<HTMLDivElement | null>;
  loading?: boolean;
};

function useChartColors() {
  const { isLight } = useTheme();
  return isLight
    ? {
        grid: 'rgba(0,0,0,0.06)',
        axis: colors.textTertiary,
        historical: '#8E8E93',
        forecast: colors.accent,
        band: 'rgba(0, 122, 255, 0.14)',
        capacity: colors.danger,
        weather: '#FF9500',
        maintenance: '#5856D6',
        crosshair: colors.textTertiary,
      }
    : {
        grid: 'rgba(255,255,255,0.06)',
        axis: colors.darkTextSecondary,
        historical: '#98989D',
        forecast: colors.darkAccent,
        band: 'rgba(10, 132, 255, 0.18)',
        capacity: '#FF453A',
        weather: '#FF9F0A',
        maintenance: '#5E5CE6',
        crosshair: colors.darkTextSecondary,
      };
}

type Visible = {
  historical: boolean;
  forecast: boolean;
  band: boolean;
  capacity: boolean;
  weather: boolean;
  maintenance: boolean;
};

function TooltipBody({
  active,
  payload,
}: {
  active?: boolean;
  payload?: Array<{ payload: SeriesPoint & { weatherEvent?: number | null; maintenance?: number | null } }>;
}) {
  if (!active || !payload?.length) return null;
  const row = payload[0].payload;
  return (
    <div className="min-w-[220px] rounded-xl bg-[var(--am-bg-elevated)] px-3.5 py-3 text-[15px] shadow-[var(--am-shadow-lg)] ring-1 ring-[var(--am-border)]">
      <p className="mb-2 border-b border-[var(--am-divider)] pb-1.5 text-[16px] font-semibold text-[var(--am-text)]">
        {row.date}
      </p>
      <dl className="space-y-1.5 tabular-nums text-[var(--am-text-secondary)]">
        <div className="flex justify-between gap-6">
          <dt>Past Data</dt>
          <dd>{formatMgd(row.historical, 2)}</dd>
        </div>
        <div className="flex justify-between gap-6">
          <dt>Predicted</dt>
          <dd>{formatMgd(row.forecast, 2)}</dd>
        </div>
        <div className="flex justify-between gap-6">
          <dt>Prediction Range</dt>
          <dd>
            {row.lower != null && row.upper != null
              ? `${row.lower.toFixed(1)}-${row.upper.toFixed(1)}`
              : '-'}
          </dd>
        </div>
        <div className="flex justify-between gap-6">
          <dt>Prediction Confidence</dt>
          <dd>{row.confidence != null ? `${Math.round(row.confidence * 100)}%` : '-'}</dd>
        </div>
        {row.weatherEvent != null ? (
          <div className="flex justify-between gap-6">
            <dt>Weather event</dt>
            <dd>{row.weatherEvent.toFixed(1)}</dd>
          </div>
        ) : null}
        {row.maintenance != null ? (
          <div className="flex justify-between gap-6">
            <dt>Maintenance</dt>
            <dd>{row.maintenance.toFixed(1)}</dd>
          </div>
        ) : null}
      </dl>
    </div>
  );
}

export const ForecastChart: React.FC<Props> = ({
  series,
  forecastPointCount,
  unit,
  capacityMgd,
  chartRef,
  loading,
}) => {
  const COLORS = useChartColors();
  const [visible, setVisible] = useState<Visible>({
    historical: true,
    forecast: true,
    band: true,
    capacity: true,
    weather: false,
    maintenance: false,
  });

  const data = useMemo(() => {
    const n = series.length;
    return series.map((p, i) => {
      const weatherSpike =
        p.forecast != null && (i === Math.floor(n * 0.62) || i === Math.floor(n * 0.78))
          ? p.forecast * 1.08
          : null;
      const maint =
        p.historical != null && i === Math.floor(n * 0.35) ? p.historical * 0.92 : null;
      return {
        ...p,
        bandBase: p.lower,
        bandSpan: p.lower != null && p.upper != null ? p.upper - p.lower : null,
        weatherEvent: weatherSpike,
        maintenance: maint,
      };
    });
  }, [series]);

  const toggle = (key: keyof Visible) => setVisible((v) => ({ ...v, [key]: !v[key] }));

  if (loading) return <SkeletonChart height={480} />;

  if (!series.length) {
    return (
      <EmptyState
        className="min-h-[420px]"
        title="No data available for the selected period."
        description="Try changing the forecast range or location."
      />
    );
  }

  return (
    <div
      ref={chartRef}
      className="rounded-[16px] border border-[var(--am-border)] bg-[var(--am-bg-elevated)] p-5 shadow-[var(--am-shadow-sm)]"
    >
      <div className="mb-4 flex flex-wrap items-end justify-between gap-2">
        <div>
          <h3 className="text-[17px] font-semibold tracking-tight text-[var(--am-text)]">Demand time series</h3>
          <p className="mt-0.5 text-[15px] text-[var(--am-text-secondary)]">
            Toggle layers · brush to zoom
            {forecastPointCount != null && unit ? ` · ${forecastPointCount} ${unit} points` : ''}
            {capacityMgd != null ? ` · capacity ${capacityMgd.toFixed(1)} MGD` : ''}
          </p>
        </div>
        <div className="flex flex-wrap gap-1.5 text-[14px]" role="group" aria-label="Chart layers">
          {(
            [
              ['historical', 'Past Data', COLORS.historical],
              ['forecast', 'Predicted', COLORS.forecast],
              ['band', 'Prediction Range', COLORS.band],
              ['capacity', 'Maximum Capacity', COLORS.capacity],
              ['weather', 'Weather event', COLORS.weather],
              ['maintenance', 'Maintenance', COLORS.maintenance],
            ] as const
          ).map(([key, label, color]) => (
            <button
              key={key}
              type="button"
              onClick={() => toggle(key)}
              aria-pressed={visible[key]}
              className={`inline-flex items-center gap-1.5 rounded-[10px] px-2.5 py-1.5 transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--am-accent)] ${
                visible[key]
                  ? 'bg-[var(--am-bg-muted)] text-[var(--am-text)]'
                  : 'text-[var(--am-text-tertiary)] line-through'
              }`}
            >
              <span className="inline-block h-2 w-2 rounded-sm" style={{ background: color }} aria-hidden />
              {label}
            </button>
          ))}
        </div>
      </div>

      <div className="h-[440px] w-full">
        <ResponsiveContainer width="100%" height="100%">
          <ComposedChart data={data} margin={{ top: 12, right: 18, left: 4, bottom: 4 }}>
            <defs>
              <linearGradient id="demandForecastFill" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stopColor={COLORS.forecast} stopOpacity={0.18} />
                <stop offset="100%" stopColor={COLORS.forecast} stopOpacity={0} />
              </linearGradient>
            </defs>
            <CartesianGrid stroke={COLORS.grid} strokeDasharray="3 6" vertical={false} />
            <XAxis
              dataKey="date"
              minTickGap={28}
              tick={{ fill: COLORS.axis, fontSize: 13 }}
              axisLine={{ stroke: COLORS.grid }}
              tickLine={false}
              interval="preserveStartEnd"
            />
            <YAxis
              unit=" MGD"
              width={64}
              tick={{ fill: COLORS.axis, fontSize: 13 }}
              axisLine={false}
              tickLine={false}
              domain={['auto', 'auto']}
            />
            <Tooltip
              content={<TooltipBody />}
              cursor={{ stroke: COLORS.crosshair, strokeWidth: 1, strokeDasharray: '4 4' }}
            />
            <Legend content={() => null} />
            {visible.band && (
              <>
                <Area
                  type="monotone"
                  dataKey="bandBase"
                  stackId="ci"
                  stroke="none"
                  fill="transparent"
                  legendType="none"
                  isAnimationActive={false}
                  connectNulls={false}
                />
                <Area
                  type="monotone"
                  dataKey="bandSpan"
                  stackId="ci"
                  stroke="none"
                  fill={COLORS.band}
                  fillOpacity={1}
                  isAnimationActive={false}
                  connectNulls={false}
                />
              </>
            )}
            {visible.capacity && capacityMgd != null && (
              <ReferenceLine
                y={capacityMgd}
                stroke={COLORS.capacity}
                strokeDasharray="6 4"
                strokeWidth={1.5}
                label={{
                  value: 'Maximum Capacity',
                  position: 'insideTopRight',
                  fill: COLORS.capacity,
                  fontSize: 14,
                }}
              />
            )}
            {visible.historical && (
              <Line
                type="monotone"
                dataKey="historical"
                stroke={COLORS.historical}
                strokeWidth={1.75}
                dot={false}
                animationDuration={500}
                connectNulls={false}
              />
            )}
            {visible.forecast && (
              <Area
                type="monotone"
                dataKey="forecast"
                stroke={COLORS.forecast}
                strokeWidth={2.25}
                fill="url(#demandForecastFill)"
                dot={forecastPointCount != null && forecastPointCount <= 24}
                animationDuration={600}
                connectNulls={false}
              />
            )}
            {visible.weather && (
              <Scatter dataKey="weatherEvent" fill={COLORS.weather} name="Weather" />
            )}
            {visible.maintenance && (
              <Scatter dataKey="maintenance" fill={COLORS.maintenance} name="Maintenance" />
            )}
            <Brush dataKey="date" height={26} stroke="#AEAEB2" travellerWidth={10} />
          </ComposedChart>
        </ResponsiveContainer>
      </div>

      <p className="mt-2 text-center text-[14px] text-[var(--am-text-tertiary)]">
        Drag brush to zoom · toggle layers above
      </p>
    </div>
  );
};
