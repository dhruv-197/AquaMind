import React, { useMemo } from 'react';
import {
  Area,
  Brush,
  CartesianGrid,
  ComposedChart,
  Line,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
  BarChart,
  Bar,
  Legend,
  LabelList,
  ReferenceLine,
} from 'recharts';
import type { StressSeriesPoint, StressWorkspaceData } from './types';

type Props = {
  series: StressSeriesPoint[];
  comparison?: StressWorkspaceData['regional_comparison'];
  hasScenario?: boolean;
  loading?: boolean;
};

const COLORS = {
  grid: 'rgba(0,0,0,0.06)',
  axis: '#8E8E93',
  historical: '#8E8E93',
  forecast: '#007AFF',
  baselineForecast: '#AEAEB2',
  band: 'rgba(0, 122, 255, 0.14)',
  baselineBar: '#AEAEB2',
  scenarioBar: '#FF9500',
  deltaUp: '#FF3B30',
  deltaDown: '#34C759',
};

function DeltaLabel(props: {
  x?: number;
  y?: number;
  width?: number;
  value?: number;
}) {
  const { x = 0, y = 0, width = 0, value } = props;
  if (value == null || Math.abs(value) < 0.05) return null;
  const text = `${value > 0 ? '+' : ''}${value.toFixed(1)}`;
  const fill = value > 0 ? COLORS.deltaUp : COLORS.deltaDown;
  return (
    <text
      x={x + width / 2}
      y={y - 6}
      fill={fill}
      textAnchor="middle"
      fontSize={11}
      fontWeight={700}
      fontFamily="ui-monospace, monospace"
    >
      {text}
    </text>
  );
}

export const StressCharts: React.FC<Props> = ({
  series,
  comparison,
  hasScenario,
  loading,
}) => {
  const data = useMemo(
    () =>
      series.map((p) => ({
        ...p,
        bandBase: p.lower,
        bandSpan: p.lower != null && p.upper != null ? p.upper - p.lower : null,
      })),
    [series],
  );

  const comparisonRows = useMemo(() => {
    if (!comparison?.length) return [];
    return comparison.map((row) => {
      const baseline = row.baseline_wsi ?? row.wsi;
      const delta = row.delta_wsi ?? round1(row.wsi - baseline);
      return {
        ...row,
        baseline_wsi: round1(baseline),
        wsi: round1(row.wsi),
        delta_wsi: round1(delta),
        shortName: shortenName(row.name),
      };
    });
  }, [comparison]);

  const showScenarioCompare = Boolean(
    hasScenario || comparisonRows.some((r) => Math.abs(r.delta_wsi) >= 0.05),
  );

  const yDomain = useMemo(() => {
    if (!comparisonRows.length) return [0, 100] as [number, number];
    const vals = comparisonRows.flatMap((r) => [r.baseline_wsi, r.wsi]);
    const min = Math.min(...vals);
    const max = Math.max(...vals);
    // Zoom into the data range so scenario deltas are visually obvious
    const pad = Math.max(8, (max - min) * 0.35);
    return [Math.max(0, Math.floor(min - pad)), Math.min(100, Math.ceil(max + pad))] as [
      number,
      number,
    ];
  }, [comparisonRows]);

  if (loading) {
    return (
      <div className="flex h-[420px] items-center justify-center rounded-xl border border-slate-200 bg-white text-[15px] text-slate-500 shadow-sm dark:border-slate-700 dark:bg-slate-950">
        Generating stress forecast...
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm dark:border-slate-700 dark:bg-slate-950">
        <h3 className="text-[15px] font-semibold text-slate-900 dark:text-slate-100">
          Past Data vs Predicted stress
        </h3>
        <p className="mt-0.5 text-[14px] text-slate-500">
          {showScenarioCompare
            ? 'Solid = scenario forecast · Dashed = baseline forecast'
            : 'Water Stress Index with prediction range'}
        </p>
        <div className="mt-3 h-[320px] w-full">
          {!series.length ? (
            <div className="flex h-full flex-col items-center justify-center gap-1 text-[15px] text-slate-500">
              <p>No data available for the selected period.</p>
            </div>
          ) : (
            <ResponsiveContainer width="100%" height="100%">
              <ComposedChart data={data} margin={{ top: 8, right: 12, left: 0, bottom: 0 }}>
                <CartesianGrid stroke={COLORS.grid} strokeDasharray="4 4" vertical={false} />
                <XAxis
                  dataKey="date"
                  minTickGap={28}
                  tick={{ fill: COLORS.axis, fontSize: 14 }}
                  tickLine={false}
                />
                <YAxis
                  domain={[0, 100]}
                  width={40}
                  tick={{ fill: COLORS.axis, fontSize: 14 }}
                  tickLine={false}
                  axisLine={false}
                />
                <Tooltip
                  contentStyle={{ fontSize: 13, borderRadius: 8 }}
                  formatter={(value: number, name: string) => [
                    typeof value === 'number' ? value.toFixed(1) : value,
                    name === 'baseline_forecast'
                      ? 'Baseline forecast'
                      : name === 'forecast'
                        ? 'Scenario forecast'
                        : name,
                  ]}
                />
                <Area
                  type="monotone"
                  dataKey="bandBase"
                  stackId="ci"
                  stroke="none"
                  fill="transparent"
                  isAnimationActive={false}
                />
                <Area
                  type="monotone"
                  dataKey="bandSpan"
                  stackId="ci"
                  stroke="none"
                  fill={COLORS.band}
                  fillOpacity={0.35}
                  isAnimationActive={false}
                />
                <Line
                  type="monotone"
                  dataKey="historical"
                  stroke={COLORS.historical}
                  strokeWidth={2}
                  dot={false}
                  isAnimationActive={false}
                  name="Past Data"
                />
                {showScenarioCompare ? (
                  <Line
                    type="monotone"
                    dataKey="baseline_forecast"
                    stroke={COLORS.baselineForecast}
                    strokeWidth={2}
                    strokeDasharray="6 4"
                    dot={false}
                    isAnimationActive={false}
                    name="Baseline forecast"
                    connectNulls={false}
                  />
                ) : null}
                <Line
                  type="monotone"
                  dataKey="forecast"
                  stroke={COLORS.forecast}
                  strokeWidth={2.5}
                  dot={false}
                  isAnimationActive={false}
                  name={showScenarioCompare ? 'Scenario forecast' : 'Predicted'}
                />
                <Brush dataKey="date" height={24} stroke="#94a3b8" fill="#f8fafc" />
              </ComposedChart>
            </ResponsiveContainer>
          )}
        </div>
      </div>

      <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm dark:border-slate-700 dark:bg-slate-950">
        <div className="flex flex-wrap items-end justify-between gap-2">
          <div>
            <h3 className="text-[15px] font-semibold text-slate-900 dark:text-slate-100">
              Regional comparison
            </h3>
            <p className="mt-0.5 text-[14px] text-slate-500">
              {showScenarioCompare
                ? 'Grouped bars: baseline vs scenario · labels show Δ WSI'
                : 'WSI across wards, zones, and districts'}
            </p>
          </div>
          {showScenarioCompare ? (
            <div className="flex items-center gap-3 text-[14px] text-slate-500">
              <span className="inline-flex items-center gap-1.5">
                <span className="inline-block h-2.5 w-2.5 rounded-sm bg-slate-400" />
                Baseline
              </span>
              <span className="inline-flex items-center gap-1.5">
                <span className="inline-block h-2.5 w-2.5 rounded-sm bg-orange-500" />
                Scenario
              </span>
            </div>
          ) : null}
        </div>
        <div className="mt-3 h-[280px] w-full">
          {!comparisonRows.length ? (
            <div className="flex h-full flex-col items-center justify-center gap-1 text-[15px] text-slate-500">
              <p>No data available for the selected period.</p>
            </div>
          ) : (
            <ResponsiveContainer width="100%" height="100%">
              <BarChart
                data={comparisonRows}
                margin={{ top: 28, right: 8, left: 0, bottom: 28 }}
                barCategoryGap="18%"
                barGap={4}
              >
                <CartesianGrid stroke={COLORS.grid} strokeDasharray="4 4" vertical={false} />
                <XAxis
                  dataKey="shortName"
                  tick={{ fill: COLORS.axis, fontSize: 14 }}
                  interval={0}
                  angle={-18}
                  textAnchor="end"
                  height={48}
                />
                <YAxis
                  domain={yDomain}
                  width={40}
                  tick={{ fill: COLORS.axis, fontSize: 14 }}
                  label={{
                    value: 'WSI',
                    angle: -90,
                    position: 'insideLeft',
                    style: { fill: COLORS.axis, fontSize: 14 },
                  }}
                />
                <Tooltip
                  contentStyle={{ fontSize: 13, borderRadius: 8 }}
                  formatter={(value: number, name: string) => {
                    const label =
                      name === 'baseline_wsi'
                        ? 'Baseline WSI'
                        : name === 'wsi'
                          ? 'Scenario WSI'
                          : name;
                    return [typeof value === 'number' ? value.toFixed(1) : value, label];
                  }}
                  labelFormatter={(label, payload) => {
                    const row = payload?.[0]?.payload as { name?: string; delta_wsi?: number } | undefined;
                    const delta = row?.delta_wsi;
                    const deltaTxt =
                      delta == null || Math.abs(delta) < 0.05
                        ? ''
                        : ` · Δ ${delta > 0 ? '+' : ''}${delta.toFixed(1)}`;
                    return `${row?.name || label}${deltaTxt}`;
                  }}
                />
                <Legend content={() => null} />
                {showScenarioCompare ? (
                  <>
                    <Bar
                      dataKey="baseline_wsi"
                      name="Baseline"
                      fill={COLORS.baselineBar}
                      radius={[4, 4, 0, 0]}
                      maxBarSize={36}
                      isAnimationActive
                      animationDuration={500}
                    />
                    <Bar
                      dataKey="wsi"
                      name="Scenario"
                      fill={COLORS.scenarioBar}
                      radius={[4, 4, 0, 0]}
                      maxBarSize={36}
                      isAnimationActive
                      animationDuration={500}
                    >
                      <LabelList dataKey="delta_wsi" content={<DeltaLabel />} />
                    </Bar>
                  </>
                ) : (
                  <Bar
                    dataKey="wsi"
                    name="WSI"
                    fill={COLORS.scenarioBar}
                    radius={[4, 4, 0, 0]}
                    maxBarSize={48}
                  />
                )}
                <ReferenceLine y={61} stroke="#dc2626" strokeDasharray="4 4" strokeOpacity={0.45} />
              </BarChart>
            </ResponsiveContainer>
          )}
        </div>
        {showScenarioCompare ? (
          <p className="mt-1 text-center text-[14px] text-slate-400">
            Red dashed line = High stress threshold (61) · Axis zooms to data range so shifts stand out
          </p>
        ) : null}
      </div>
    </div>
  );
};

function round1(n: number) {
  return Math.round(n * 10) / 10;
}

function shortenName(name: string) {
  return name.replace('Municipality', 'Muni.').replace('District', 'Dist.');
}
