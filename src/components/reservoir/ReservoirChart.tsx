import React, { useMemo, useState } from 'react';
import {
  Area,
  Brush,
  CartesianGrid,
  ComposedChart,
  Legend,
  Line,
  ReferenceArea,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';
import type { ForecastUnit, SeriesPoint } from './types';
import { formatPct } from '../demand/utils';

type Props = {
  series: SeriesPoint[];
  forecastPointCount?: number;
  unit?: ForecastUnit;
  chartRef?: React.RefObject<HTMLDivElement | null>;
  loading?: boolean;
};

const COLORS = {
  grid: 'rgba(0,0,0,0.06)',
  axis: '#8E8E93',
  historical: '#8E8E93',
  forecast: '#007AFF',
  band: 'rgba(0, 122, 255, 0.14)',
  capacity: '#8E8E93',
  critical: '#FF3B30',
  safe: 'rgba(52, 199, 89, 0.18)',
  crosshair: '#8E8E93',
};

type Visible = {
  historical: boolean;
  forecast: boolean;
  band: boolean;
  capacity: boolean;
  critical: boolean;
  safe: boolean;
};

function TooltipBody({
  active,
  payload,
}: {
  active?: boolean;
  payload?: Array<{ payload: SeriesPoint }>;
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
          <dd>{formatPct(row.historical, 1)}</dd>
        </div>
        <div className="flex justify-between gap-6">
          <dt>Predicted</dt>
          <dd>{formatPct(row.forecast, 1)}</dd>
        </div>
        <div className="flex justify-between gap-6">
          <dt>Prediction Range</dt>
          <dd>
            {row.lower != null && row.upper != null
              ? `${row.lower.toFixed(1)}-${row.upper.toFixed(1)}%`
              : '-'}
          </dd>
        </div>
        <div className="flex justify-between gap-6">
          <dt>Prediction Confidence</dt>
          <dd>{row.confidence != null ? `${Math.round(row.confidence * 100)}%` : '-'}</dd>
        </div>
        <div className="flex justify-between gap-6">
          <dt>Risk</dt>
          <dd>{row.risk || '-'}</dd>
        </div>
      </dl>
    </div>
  );
}

export const ReservoirChart: React.FC<Props> = ({
  series,
  forecastPointCount,
  unit,
  chartRef,
  loading,
}) => {
  const [visible, setVisible] = useState<Visible>({
    historical: true,
    forecast: true,
    band: true,
    capacity: true,
    critical: true,
    safe: true,
  });

  const data = useMemo(
    () =>
      series.map((p) => ({
        ...p,
        bandBase: p.lower,
        bandSpan: p.lower != null && p.upper != null ? p.upper - p.lower : null,
      })),
    [series],
  );

  const toggle = (key: keyof Visible) => setVisible((v) => ({ ...v, [key]: !v[key] }));

  if (loading) {
    return (
      <div className="flex h-[480px] items-center justify-center rounded-xl border border-slate-200 bg-white text-[15px] text-slate-500 shadow-sm dark:border-slate-700 dark:bg-slate-950">
        Generating reservoir forecast…
      </div>
    );
  }

  if (!series.length) {
    return (
      <div className="flex h-[480px] flex-col items-center justify-center gap-1 rounded-xl border border-dashed border-slate-300 bg-slate-50 text-[15px] text-slate-500 dark:border-slate-700 dark:bg-slate-950">
        <p>No data available for the selected period.</p>
        <p className="text-[14px] text-slate-400">Try changing the forecast range or location.</p>
      </div>
    );
  }

  return (
    <div
      ref={chartRef}
      className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm dark:border-slate-700 dark:bg-slate-950"
    >
      <div className="mb-3 flex flex-wrap items-end justify-between gap-2">
        <div>
          <h3 className="text-[15px] font-semibold text-slate-900 dark:text-slate-100">
            Reservoir storage time series
          </h3>
          <p className="mt-0.5 text-[14px] text-slate-500">
            Past Data + Predicted
            {forecastPointCount != null && unit
              ? ` · ${forecastPointCount} ${unit} forecast points`
              : ''}
          </p>
        </div>
        <div className="flex flex-wrap gap-1.5 text-[14px]">
          {(
            [
              ['historical', 'Past Data', COLORS.historical],
              ['forecast', 'Predicted', COLORS.forecast],
              ['band', 'Prediction Range', COLORS.band],
              ['capacity', 'Maximum Capacity', COLORS.capacity],
              ['critical', 'Critical (20%)', COLORS.critical],
              ['safe', 'Safe zone', COLORS.safe],
            ] as const
          ).map(([key, label, color]) => (
            <button
              key={key}
              type="button"
              onClick={() => toggle(key)}
              className={`inline-flex items-center gap-1.5 rounded-md border px-2 py-1 ${
                visible[key]
                  ? 'border-slate-200 bg-white text-slate-700 dark:border-slate-600 dark:bg-slate-900 dark:text-slate-100'
                  : 'border-slate-100 text-slate-400 line-through dark:border-slate-800'
              }`}
            >
              <span className="inline-block h-2 w-2 rounded-sm" style={{ background: color }} />
              {label}
            </button>
          ))}
        </div>
      </div>

      <div className="h-[440px] w-full">
        <ResponsiveContainer width="100%" height="100%">
          <ComposedChart data={data} margin={{ top: 12, right: 18, left: 4, bottom: 4 }}>
            <CartesianGrid stroke={COLORS.grid} strokeDasharray="4 4" vertical={false} />
            <XAxis
              dataKey="date"
              minTickGap={28}
              tick={{ fill: COLORS.axis, fontSize: 14 }}
              axisLine={{ stroke: '#dbe3ea' }}
              tickLine={false}
              interval="preserveStartEnd"
            />
            <YAxis
              unit="%"
              width={48}
              domain={[0, 100]}
              tick={{ fill: COLORS.axis, fontSize: 14 }}
              axisLine={false}
              tickLine={false}
            />
            <Tooltip
              content={<TooltipBody />}
              cursor={{ stroke: COLORS.crosshair, strokeWidth: 1, strokeDasharray: '4 4' }}
            />
            <Legend content={() => null} />
            {visible.safe && (
              // Recharts ReferenceArea typing omits fill in some versions
              <ReferenceArea
                y1={60}
                y2={100}
                {...({ fill: COLORS.safe, fillOpacity: 0.12 } as object)}
                ifOverflow="extendDomain"
              />
            )}
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
                  fillOpacity={0.35}
                  isAnimationActive={false}
                  connectNulls={false}
                />
              </>
            )}
            {visible.capacity && (
              <ReferenceLine
                y={100}
                stroke={COLORS.capacity}
                strokeDasharray="6 4"
                strokeWidth={1.25}
                label={{ value: 'Maximum Capacity', position: 'insideTopRight', fill: COLORS.capacity, fontSize: 14 }}
              />
            )}
            {visible.critical && (
              <ReferenceLine
                y={20}
                stroke={COLORS.critical}
                strokeDasharray="4 4"
                strokeWidth={1.5}
                label={{ value: 'Critical', position: 'insideBottomRight', fill: COLORS.critical, fontSize: 14 }}
              />
            )}
            {visible.historical && (
              <Line
                type="monotone"
                dataKey="historical"
                stroke={COLORS.historical}
                strokeWidth={2}
                dot={false}
                isAnimationActive={false}
                connectNulls={false}
              />
            )}
            {visible.forecast && (
              <Line
                type="monotone"
                dataKey="forecast"
                stroke={COLORS.forecast}
                strokeWidth={2.25}
                dot={forecastPointCount != null && forecastPointCount <= 24}
                isAnimationActive={false}
                connectNulls={false}
              />
            )}
            <Brush dataKey="date" height={26} stroke="#94a3b8" fill="#f8fafc" travellerWidth={10} />
          </ComposedChart>
        </ResponsiveContainer>
      </div>

      <p className="mt-2 text-center text-[14px] text-slate-400">
        Drag brush to zoom · safe zone &gt;60% · critical &lt;20%
      </p>
    </div>
  );
};
