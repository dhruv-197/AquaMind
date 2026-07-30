import React from 'react';
import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  Brush,
  CartesianGrid,
  Cell,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';
import { SectionTitle } from './ExecutiveKpis';

type SeriesPoint = { label: string; value: number; fill?: string };

type Props = {
  demand: SeriesPoint[];
  reservoir: SeriesPoint[];
  climate: SeriesPoint[];
};

const tipStyle = {
  background: 'var(--am-bg-elevated)',
  border: '1px solid var(--am-border)',
  borderRadius: 12,
  fontSize: 14,
  color: 'var(--am-text)',
  boxShadow: 'var(--am-shadow-md)',
};

function ChartEmpty() {
  return (
    <div className="flex h-full flex-col items-center justify-center gap-1 px-4 text-center">
      <p className="text-[16px] font-medium text-[var(--am-text)]">
        No data available for the selected period.
      </p>
      <p className="text-[15px] text-[var(--am-text-tertiary)]">
        Try changing the forecast range or location.
      </p>
    </div>
  );
}

function ChartCard({
  title,
  subtitle,
  children,
  onToggle,
  active,
  empty,
}: {
  title: string;
  subtitle?: string;
  children: React.ReactNode;
  onToggle?: () => void;
  active?: boolean;
  empty?: boolean;
}) {
  return (
    <div className="rounded-[16px] border border-[var(--am-border)] bg-[var(--am-bg-muted)]/60 p-4">
      <div className="mb-3 flex items-center justify-between gap-2">
        <div className="min-w-0">
          <h3 className="text-[16px] font-semibold text-[var(--am-text)]">{title}</h3>
          {subtitle ? (
            <p className="mt-0.5 text-[10.5px] text-[var(--am-text-tertiary)]">{subtitle}</p>
          ) : null}
        </div>
        {onToggle ? (
          <button
            type="button"
            onClick={onToggle}
            className={`min-h-9 rounded-md px-2 text-[14px] font-semibold focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--am-accent)] ${
              active ? 'text-[var(--am-accent)]' : 'text-[var(--am-text-tertiary)]'
            }`}
          >
            {active ? 'Visible' : 'Hidden'}
          </button>
        ) : null}
      </div>
      <div className="h-[240px]">
        {active === false ? null : empty ? <ChartEmpty /> : children}
      </div>
    </div>
  );
}

export const ExecutiveAnalytics: React.FC<Props> = ({ demand, reservoir, climate }) => {
  const [show, setShow] = React.useState({
    demand: true,
    reservoir: true,
    climate: true,
  });

  return (
    <section className="am-soft-card p-5 sm:p-6">
      <SectionTitle
        title="Operations Analytics"
        subtitle="Demand, storage, and rainfall outlook for planning briefings."
      />
      <div className="mt-4 grid grid-cols-1 gap-3 xl:grid-cols-3">
        <ChartCard
          title="Water demand (predicted)"
          subtitle="Live forecast series"
          active={show.demand}
          onToggle={() => setShow((s) => ({ ...s, demand: !s.demand }))}
          empty={!demand.length}
        >
          <ResponsiveContainer width="100%" height="100%">
            <AreaChart data={demand}>
              <defs>
                <linearGradient id="amDemandFill" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor="#007AFF" stopOpacity={0.28} />
                  <stop offset="100%" stopColor="#007AFF" stopOpacity={0} />
                </linearGradient>
              </defs>
              <CartesianGrid stroke="var(--am-divider)" strokeDasharray="3 6" vertical={false} />
              <XAxis
                dataKey="label"
                tick={{ fontSize: 13, fill: 'var(--am-text-tertiary)' }}
                axisLine={false}
                tickLine={false}
              />
              <YAxis
                tick={{ fontSize: 13, fill: 'var(--am-text-tertiary)' }}
                axisLine={false}
                tickLine={false}
                width={36}
              />
              <Tooltip contentStyle={tipStyle} />
              <Area
                type="monotone"
                dataKey="value"
                stroke="#007AFF"
                strokeWidth={2}
                fill="url(#amDemandFill)"
                animationDuration={600}
              />
              <Brush dataKey="label" height={18} stroke="#AEAEB2" travellerWidth={8} />
            </AreaChart>
          </ResponsiveContainer>
        </ChartCard>

        <ChartCard
          title="Reservoir storage"
          active={show.reservoir}
          onToggle={() => setShow((s) => ({ ...s, reservoir: !s.reservoir }))}
          empty={!reservoir.length}
        >
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={reservoir}>
              <CartesianGrid stroke="var(--am-divider)" strokeDasharray="3 6" vertical={false} />
              <XAxis
                dataKey="label"
                tick={{ fontSize: 14, fill: 'var(--am-text-tertiary)' }}
                axisLine={false}
                tickLine={false}
              />
              <YAxis
                domain={[0, 100]}
                tick={{ fontSize: 13, fill: 'var(--am-text-tertiary)' }}
                axisLine={false}
                tickLine={false}
                width={36}
              />
              <Tooltip contentStyle={tipStyle} />
              <Bar dataKey="value" radius={[6, 6, 0, 0]} animationDuration={500}>
                {reservoir.map((e, i) => (
                  <Cell key={i} fill={e.fill || '#007AFF'} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </ChartCard>

        <ChartCard
          title="Rainfall forecast"
          subtitle="Millimeters"
          active={show.climate}
          onToggle={() => setShow((s) => ({ ...s, climate: !s.climate }))}
          empty={!climate.length}
        >
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={climate}>
              <CartesianGrid stroke="var(--am-divider)" strokeDasharray="3 6" vertical={false} />
              <XAxis
                dataKey="label"
                tick={{ fontSize: 13, fill: 'var(--am-text-tertiary)' }}
                axisLine={false}
                tickLine={false}
              />
              <YAxis
                tick={{ fontSize: 13, fill: 'var(--am-text-tertiary)' }}
                axisLine={false}
                tickLine={false}
                width={36}
              />
              <Tooltip contentStyle={tipStyle} />
              <Line type="monotone" dataKey="value" stroke="#5856D6" strokeWidth={2} dot={false} />
            </LineChart>
          </ResponsiveContainer>
        </ChartCard>
      </div>
    </section>
  );
};
