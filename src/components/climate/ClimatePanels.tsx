import React from 'react';
import { Link } from 'react-router-dom';
import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';
import { AlertTriangle, CloudRain, Droplets, ExternalLink, Waves } from 'lucide-react';
import { GlassCard } from '../common/GlassCard';
import { InfoTooltip } from '../ui/InfoTooltip';
import type { ClimateRiskResult } from '../../services/climateRisk';

function num(v: unknown, digits = 1): string {
  if (v === null || v === undefined || Number.isNaN(Number(v))) return '-';
  return Number(v).toFixed(digits);
}

function riskTone(risk: string | undefined): string {
  switch (risk) {
    case 'extreme':
    case 'high':
    case 'extremely_dry':
    case 'severely_dry':
      return 'text-rose-400';
    case 'elevated':
    case 'moderately_dry':
    case 'watch':
      return 'text-amber-400';
    case 'low':
    case 'near_normal':
    case 'none':
      return 'text-emerald-400';
    default:
      return 'text-slate-300';
  }
}

/** Soften API climate copy for operators (hide implementation footnotes). */
export function plainClimateSummary(raw: string | undefined | null): string {
  if (!raw) {
    return 'Climate conditions for this location have been analyzed. Review rainfall, flood, and waterlogging panels above.';
  }
  return String(raw)
    .replace(/\s*\([^)]*models?\s+not\s+retrained[^)]*\)/gi, '')
    .replace(/\s*\([^)]*display\s*\+\s*rules[^)]*\)/gi, '')
    .replace(/\s*\([^)]*v1[^)]*\)/gi, '')
    .replace(/Open-?Meteo/gi, 'weather archive')
    .replace(/GloFAS/gi, 'river discharge forecast')
    .replace(/\s{2,}/g, ' ')
    .replace(/\s+\./g, '.')
    .trim();
}

export const ClimateKpiCards: React.FC<{ result: ClimateRiskResult }> = ({ result }) => {
  const spi = result.climate.spi3_proxy as Record<string, unknown>;
  const deficit = result.climate.rainfall_deficit as Record<string, unknown>;
  const heat = result.climate.heatwave as Record<string, unknown>;
  const et = result.climate.evapotranspiration as Record<string, unknown>;
  const flood = result.flood as Record<string, unknown>;
  const pond = result.waterlogging as Record<string, unknown>;

  const cards = [
    {
      label: 'Drought Indicator',
      value: num(spi.spi3_proxy, 2),
      sub: String(spi.class ?? '-').replace(/_/g, ' '),
      icon: CloudRain,
      tip: 'Measures how dry recent months are compared with long-term rainfall patterns.',
    },
    {
      label: 'Rainfall deficit',
      value: deficit.deficit_pct == null ? '-' : `${num(deficit.deficit_pct, 0)}%`,
      sub: `${num(deficit.recent_mm, 0)} mm / ${num(deficit.normal_mm, 0)} mm normal`,
      icon: Droplets,
      tip: 'How far recent rainfall is below or above the normal amount for this location.',
    },
    {
      label: 'Heatwave',
      value: heat.active ? 'Active' : 'Quiet',
      sub: `Intensity ${num(heat.intensity_score, 1)} · inspection priority ×${num(heat.leak_priority_multiplier, 2)}`,
      icon: AlertTriangle,
      tip: 'Whether extreme heat is active and may increase demand and inspection needs.',
    },
    {
      label: 'Evaporation (7-day)',
      value: et.et0_recent_mm_day == null ? '-' : `${num(et.et0_recent_mm_day, 1)} mm/d`,
      sub: et.et0_anomaly_pct == null ? 'Reference evaporation rate' : `${num(et.et0_anomaly_pct, 0)}% vs archive`,
      icon: Waves,
      tip: 'How quickly water is evaporating, which affects reservoir and soil moisture.',
    },
    {
      label: 'Flood Risk',
      value: String(flood.risk_class ?? '-').replace(/_/g, ' '),
      sub: `Peak ${num(flood.peak_m3s, 1)} m³/s · p${num(flood.percentile, 0)}`,
      icon: Waves,
      tone: riskTone(String(flood.risk_class)),
      tip: 'River discharge risk for the selected location based on forecasted flow levels.',
    },
    {
      label: 'Waterlogging Depth',
      value: pond.potential_depth_mm == null ? '-' : `${num(pond.potential_depth_mm, 0)} mm`,
      sub: `Duration ${String(pond.duration_band ?? '-')} · ~${num(pond.exposure_radius_km, 0)} km area`,
      icon: Droplets,
      tip: 'Indicative ponding depth and how long standing water may persist after heavy rain.',
    },
  ];

  return (
    <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-3">
      {cards.map((c) => (
        <GlassCard key={c.label} className="!rounded-[16px] !p-4" hoverEffect={false}>
          <div className="flex items-start justify-between gap-3">
            <div className="min-w-0">
              <div className="flex items-center gap-1.5">
                <p className="text-[16px] font-semibold uppercase tracking-wider text-[var(--am-text-tertiary)]">
                  {c.label}
                </p>
                <InfoTooltip content={c.tip} label={`About ${c.label}`} />
              </div>
              <p className={`mt-1 text-2xl font-bold ${c.tone ?? 'text-[var(--am-text)]'}`}>{c.value}</p>
              <p className="mt-1 text-[14px] text-[var(--am-text-secondary)]">{c.sub}</p>
            </div>
            <c.icon className="h-5 w-5 shrink-0 text-[var(--am-accent)]" aria-hidden />
          </div>
        </GlassCard>
      ))}
    </div>
  );
};

export const ClimateCharts: React.FC<{ result: ClimateRiskResult }> = ({ result }) => {
  const precip = result.climate.precip_series_mm.slice(-60);
  const forecastP = result.climate.forecast_precip_mm || [];
  const floodSeries = ((result.flood.series as { date: string; river_discharge_m3s: number }[]) || []).slice(-30);
  const tip = {
    background: 'var(--am-bg-elevated)',
    border: '1px solid var(--am-border)',
    borderRadius: 12,
    fontSize: 14,
    color: 'var(--am-text)',
    boxShadow: 'var(--am-shadow-md)',
  };

  return (
    <div className="grid grid-cols-1 gap-4 xl:grid-cols-2">
      <GlassCard hoverEffect={false} className="!rounded-[16px]">
        <h3 className="text-[17px] font-semibold text-[var(--am-text)]">Rainfall History</h3>
        <p className="mb-3 text-[14px] text-[var(--am-text-tertiary)]">
          Technical: Historical daily rainfall · mm/day
        </p>
        <div className="h-56">
          {!precip.length ? (
            <div className="flex h-full flex-col items-center justify-center gap-1 text-center">
              <p className="text-[16px] font-medium text-[var(--am-text)]">No data available for the selected period.</p>
              <p className="text-[15px] text-[var(--am-text-tertiary)]">Try changing the forecast range or location.</p>
            </div>
          ) : (
          <ResponsiveContainer width="100%" height="100%">
            <AreaChart data={precip}>
              <defs>
                <linearGradient id="climRain" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor="#007AFF" stopOpacity={0.28} />
                  <stop offset="100%" stopColor="#007AFF" stopOpacity={0} />
                </linearGradient>
              </defs>
              <CartesianGrid stroke="var(--am-divider)" strokeDasharray="3 6" vertical={false} />
              <XAxis dataKey="date" tick={{ fill: 'var(--am-text-tertiary)', fontSize: 14 }} minTickGap={24} axisLine={false} tickLine={false} />
              <YAxis tick={{ fill: 'var(--am-text-tertiary)', fontSize: 14 }} unit=" mm" width={48} axisLine={false} tickLine={false} />
              <Tooltip contentStyle={tip} />
              <Area type="monotone" dataKey="value" name="Rainfall (mm)" stroke="#007AFF" strokeWidth={1.75} fill="url(#climRain)" animationDuration={600} />
            </AreaChart>
          </ResponsiveContainer>
          )}
        </div>
      </GlassCard>

      <GlassCard hoverEffect={false} className="!rounded-[16px]">
        <h3 className="text-[17px] font-semibold text-[var(--am-text)]">Rainfall Forecast</h3>
        <p className="mb-3 text-[14px] text-[var(--am-text-tertiary)]">
          Technical: Short-range daily precipitation · mm/day
        </p>
        <div className="h-56">
          {!forecastP.length ? (
            <div className="flex h-full flex-col items-center justify-center gap-1 text-center">
              <p className="text-[16px] font-medium text-[var(--am-text)]">No data available for the selected period.</p>
              <p className="text-[15px] text-[var(--am-text-tertiary)]">Try changing the forecast range or location.</p>
            </div>
          ) : (
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={forecastP}>
              <CartesianGrid stroke="var(--am-divider)" strokeDasharray="3 6" vertical={false} />
              <XAxis dataKey="date" tick={{ fill: 'var(--am-text-tertiary)', fontSize: 14 }} minTickGap={16} axisLine={false} tickLine={false} />
              <YAxis tick={{ fill: 'var(--am-text-tertiary)', fontSize: 14 }} unit=" mm" width={48} axisLine={false} tickLine={false} />
              <Tooltip contentStyle={tip} />
              <Bar dataKey="value" name="Predicted rainfall (mm)" fill="#5AC8FA" radius={[6, 6, 0, 0]} />
            </BarChart>
          </ResponsiveContainer>
          )}
        </div>
      </GlassCard>

      <GlassCard hoverEffect={false} className="!rounded-[16px] xl:col-span-2">
        <h3 className="text-[17px] font-semibold text-[var(--am-text)]">Flood Risk</h3>
        <p className="mb-3 text-[14px] text-[var(--am-text-tertiary)]">
          Technical: River discharge forecast · m³/s. Flow risk, not inundation area
        </p>
        <div className="h-56">
          {!floodSeries.length ? (
            <div className="flex h-full flex-col items-center justify-center gap-1 text-center">
              <p className="text-[16px] font-medium text-[var(--am-text)]">No data available for the selected period.</p>
              <p className="text-[15px] text-[var(--am-text-tertiary)]">Try changing the forecast range or location.</p>
            </div>
          ) : (
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={floodSeries}>
              <CartesianGrid stroke="var(--am-divider)" strokeDasharray="3 6" vertical={false} />
              <XAxis dataKey="date" tick={{ fill: 'var(--am-text-tertiary)', fontSize: 14 }} minTickGap={20} axisLine={false} tickLine={false} />
              <YAxis tick={{ fill: 'var(--am-text-tertiary)', fontSize: 14 }} unit=" m³/s" width={64} axisLine={false} tickLine={false} />
              <Tooltip contentStyle={tip} />
              <Legend />
              <Line
                type="monotone"
                dataKey="river_discharge_m3s"
                name="River discharge (m³/s)"
                stroke="#FF3B30"
                dot={false}
                strokeWidth={2}
                animationDuration={600}
              />
            </LineChart>
          </ResponsiveContainer>
          )}
        </div>
      </GlassCard>
    </div>
  );
};

export const WaterloggingPanel: React.FC<{ result: ClimateRiskResult }> = ({ result }) => {
  const w = result.waterlogging as Record<string, unknown>;
  const duration = String(w.duration_band ?? 'none').replace(/_/g, ' ');
  const depth = num(w.potential_depth_mm, 0);
  const hours = num(w.duration_hours_est, 1);
  const radius = num(w.exposure_radius_km, 0);

  return (
    <GlassCard hoverEffect={false} className="!rounded-[16px]">
      <h3 className="text-[17px] font-semibold text-[var(--am-text)]">Waterlogging Risk</h3>
      <p className="mt-1 text-[16px] text-[var(--am-text-secondary)]">
        Indicative ponding risk after heavy rainfall near the selected location.
      </p>
      <div className="mt-4 grid grid-cols-2 gap-3 text-[15px] md:grid-cols-4">
        <div>
          <p className="text-[16px] font-semibold uppercase tracking-wide text-[var(--am-text-tertiary)]">
            Waterlogging depth
          </p>
          <p className="mt-1 text-lg font-bold text-[var(--am-accent)]">{depth} mm</p>
        </div>
        <div>
          <p className="text-[16px] font-semibold uppercase tracking-wide text-[var(--am-text-tertiary)]">
            Duration band
          </p>
          <p className={`mt-1 text-lg font-bold ${riskTone(String(w.duration_band))}`}>{duration}</p>
        </div>
        <div>
          <p className="text-[16px] font-semibold uppercase tracking-wide text-[var(--am-text-tertiary)]">
            Est. Hours
          </p>
          <p className="mt-1 text-lg font-bold text-[var(--am-text)]">{hours} h</p>
        </div>
        <div>
          <p className="text-[16px] font-semibold uppercase tracking-wide text-[var(--am-text-tertiary)]">
            Exposure radius
          </p>
          <p className="mt-1 text-lg font-bold text-[var(--am-text)]">~{radius} km</p>
        </div>
      </div>
      <p className="mt-4 border-t border-[var(--am-divider)] pt-3 text-[15px] leading-relaxed text-[var(--am-text-tertiary)]">
        Technical: Estimated from recent rainfall intensity, soil moisture, and land type. This is an
        indicative water-balance estimate. Not a surveyed flood map or hydrodynamic model.
      </p>
    </GlassCard>
  );
};

export const RecommendationsPanel: React.FC<{ result: ClimateRiskResult }> = ({ result }) => (
  <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
    <GlassCard hoverEffect={false}>
      <h3 className="text-[15px] font-bold text-white mb-3">Government / ops recommendations</h3>
      <div className="space-y-3">
        {result.recommendations.map((r) => (
          <div key={r.action} className="rounded-xl border border-slate-800 bg-slate-950/50 p-3">
            <div className="flex items-center justify-between gap-2 mb-1">
              <span className="text-[16px] font-mono uppercase text-cyan-400">P{r.priority} · {r.module}</span>
              <Link to={r.href} className="text-[16px] text-slate-400 hover:text-cyan-300 inline-flex items-center gap-1">
                Open <ExternalLink className="w-3 h-3" />
              </Link>
            </div>
            <p className="text-[15px] font-semibold text-white">{r.action}</p>
            <p className="text-[14px] text-slate-400 mt-1">{r.rationale}</p>
          </div>
        ))}
      </div>
    </GlassCard>

    <GlassCard hoverEffect={false}>
      <h3 className="text-[15px] font-bold text-white mb-3">Priority queue</h3>
      <div className="space-y-2">
        {result.priority_queue.map((q) => (
          <Link
            key={`${q.type}-${q.action}`}
            to={q.href}
            className="flex items-center justify-between gap-3 rounded-xl border border-slate-800 bg-slate-950/40 px-3 py-2.5 hover:border-cyan-500/40 transition-colors"
          >
            <div className="min-w-0">
              <p className="text-[14px] font-semibold text-white truncate">{q.action}</p>
              <p className="text-[16px] text-slate-500">{q.asset} · {q.type}</p>
            </div>
            <span className="text-[15px] font-bold text-cyan-300 shrink-0">{num(q.score, 0)}</span>
          </Link>
        ))}
      </div>
      <div className="mt-4 rounded-xl border border-slate-800 p-3">
        <p className="text-[16px] uppercase text-slate-500 mb-1">Drought implication (display only)</p>
        <p className="text-[14px] text-slate-300">{plainClimateSummary(result.drought_implication.summary)}</p>
        <p className="text-[14px] text-slate-400 mt-2">
          Shortage stress {num(result.drought_implication.shortage_climate_stress_0_100, 0)}/100 · GW stress{' '}
          {num(result.drought_implication.groundwater_climate_stress_0_100, 0)}/100
        </p>
        {result.drought_implication.drivers.length > 0 && (
          <p className="text-[14px] text-slate-500 mt-1">{result.drought_implication.drivers.join(' · ')}</p>
        )}
      </div>
    </GlassCard>
  </div>
);

export const ProvenanceFooter: React.FC<{ result: ClimateRiskResult }> = ({ result }) => (
  <GlassCard hoverEffect={false} className="!p-4">
    <h3 className="text-[14px] font-bold uppercase tracking-wider text-slate-400 mb-2">Data provenance</h3>
    <p className="text-[14px] text-slate-500 mb-2">Queried at {result.provenance.queried_at}</p>
    <ul className="space-y-1 mb-3">
      {result.provenance.sources.map((s) => (
        <li key={s.name} className="text-[14px] text-slate-300">
          <a href={s.url} target="_blank" rel="noreferrer" className="text-cyan-400 hover:underline">
            {s.name}
          </a>
          {s.cached ? ' · served from cache' : ' · live fetch'}
        </li>
      ))}
    </ul>
    <p className="text-[16px] font-semibold text-amber-400/90 mb-1">Limitations</p>
    <ul className="space-y-0.5">
      {result.provenance.limitations.map((l) => (
        <li key={l} className="text-[14px] text-slate-500">
          · {l}
        </li>
      ))}
    </ul>
  </GlassCard>
);
