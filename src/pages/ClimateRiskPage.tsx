import React, { useEffect, useMemo, useState } from 'react';
import { CloudRain, Loader2, MapPin } from 'lucide-react';
import { PageTitleIcon } from '../components/ui/PageTitleIcon';
import { GlassCard } from '../components/common/GlassCard';
import {
  ClimateCharts,
  ClimateKpiCards,
  WaterloggingPanel,
  plainClimateSummary,
} from '../components/climate/ClimatePanels';
import {
  analyzeClimateRisk,
  fetchClimatePresets,
  type ClimatePreset,
  type ClimateRiskResult,
  type LandClass,
} from '../services/climateRisk';
import { FilteredAssetMap } from '../components/maps';
import { QuickSummary } from '../components/ui/QuickSummary';

type Stage = 'idle' | 'loading' | 'done' | 'error';

function buildClimateSummary(result: ClimateRiskResult): string[] {
  const flood = result.flood as Record<string, unknown>;
  const deficit = result.climate.rainfall_deficit as Record<string, unknown>;
  const heat = result.climate.heatwave as Record<string, unknown>;
  const pond = result.waterlogging as Record<string, unknown>;
  const drought = result.drought_implication;

  const lines: string[] = [];
  const floodClass = String(flood.risk_class ?? 'unknown').replace(/_/g, ' ');
  lines.push(`Flood risk for this location is currently ${floodClass}.`);

  if (deficit.deficit_pct != null) {
    const pct = Number(deficit.deficit_pct);
    lines.push(
      pct > 15
        ? `Rainfall is ${Math.round(pct)}% below normal. Drought conditions need attention.`
        : pct < -10
          ? `Rainfall is running above normal for this period.`
          : `Rainfall is near normal for the selected period.`,
    );
  }

  if (heat.active) {
    lines.push('A heatwave is active and may increase demand and leak inspection priority.');
  } else {
    lines.push('No major heatwave is active at this location.');
  }

  if (pond.duration_band && String(pond.duration_band) !== 'none') {
    lines.push(`Waterlogging risk band: ${String(pond.duration_band).replace(/_/g, ' ')}.`);
  }

  if (drought?.summary) {
    lines.push(drought.summary);
  }

  return lines.slice(0, 4);
}

export const ClimateRiskPage: React.FC = () => {
  const [presets, setPresets] = useState<ClimatePreset[]>([]);
  const [presetId, setPresetId] = useState<string>('');
  const [lat, setLat] = useState('28.6139');
  const [lon, setLon] = useState('77.2090');
  const [label, setLabel] = useState('Delhi NCT');
  const [landClass, setLandClass] = useState<LandClass>('urban');
  const [stage, setStage] = useState<Stage>('idle');
  const [error, setError] = useState('');
  const [result, setResult] = useState<ClimateRiskResult | null>(null);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const list = await fetchClimatePresets();
        if (cancelled) return;
        setPresets(list);
        if (list[0]) {
          setPresetId(list[0].id);
          setLat(String(list[0].lat));
          setLon(String(list[0].lon));
          setLabel(list[0].label);
          setLandClass(list[0].land_class);
        }
      } catch {
        /* presets optional - manual lat/lon still works */
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  const applyPreset = (id: string) => {
    setPresetId(id);
    const p = presets.find((x) => x.id === id);
    if (!p) return;
    setLat(String(p.lat));
    setLon(String(p.lon));
    setLabel(p.label);
    setLandClass(p.land_class);
  };

  const handleAnalyze = async () => {
    const latN = Number(lat);
    const lonN = Number(lon);
    if (Number.isNaN(latN) || Number.isNaN(lonN)) {
      setError('Enter valid latitude and longitude.');
      setStage('error');
      return;
    }
    setStage('loading');
    setError('');
    setResult(null);
    try {
      const data = await analyzeClimateRisk({
        lat: latN,
        lon: lonN,
        label: label || undefined,
        land_class: landClass,
      });
      setResult(data);
      setStage('done');
    } catch (err) {
      setStage('error');
      setError(
        err instanceof Error
          ? err.message
          : 'Could not run climate risk analysis. Please try again.',
      );
    }
  };

  const summaryLines = useMemo(
    () => (result && stage === 'done' ? buildClimateSummary(result) : []),
    [result, stage],
  );

  return (
    <div className="space-y-5 pb-8">
      <header className="overflow-hidden rounded-[16px] border border-[var(--am-border)] bg-[var(--am-bg-elevated)] px-5 py-5 shadow-[var(--am-shadow-sm)]">
        <div className="flex items-start gap-3">
          <PageTitleIcon icon={CloudRain} />
          <div>
            <h1 className="text-[30px] font-bold tracking-[-0.02em] text-[var(--am-text)]">
              Climate Risk Overview
            </h1>
            <p className="mt-1.5 max-w-2xl text-[17px] leading-relaxed text-[var(--am-text-secondary)]">
              Monitor rainfall, drought, flood, and waterlogging conditions for the selected location.
            </p>
            <p className="mt-2 text-[15px] leading-relaxed text-[var(--am-text-tertiary)]">
              Technical: Predictions use historical weather, rainfall archives, and river discharge
              forecasts for the chosen coordinates.
            </p>
          </div>
        </div>
      </header>

      <GlassCard hoverEffect={false} className="!rounded-[16px]">
        <div className="mb-1 flex items-center gap-2 text-[16px] font-semibold text-[var(--am-text)]">
          <MapPin className="h-4 w-4 text-[var(--am-accent)]" aria-hidden />
          Current Climate Overview
        </div>
        <p className="mb-4 text-[16px] text-[var(--am-text-secondary)]">
          Interactive map showing rainfall, drought, flood, and water stress conditions.
        </p>
        <div className="mb-4">
          <FilteredAssetMap
            types={['water_stress_region', 'demand_region']}
            title="Climate risk map"
            subtitle="Select a region to focus analysis"
            height={280}
            variant="climate"
            onSelect={(id) => {
              setLabel(id);
            }}
          />
        </div>
        <div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-4">
          <div>
            <label className="mb-1 block text-[14px] font-semibold uppercase tracking-wide text-[var(--am-text-tertiary)]">
              Location preset
            </label>
            <select
              value={presetId}
              onChange={(e) => applyPreset(e.target.value)}
              className="w-full rounded-xl border border-[var(--am-border)] bg-[var(--am-bg-muted)] px-3 py-2.5 text-[15px] text-[var(--am-text)]"
            >
              {presets.length === 0 && <option value="">Manual coordinates</option>}
              {presets.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.label}
                </option>
              ))}
            </select>
            {presets.find((p) => p.id === presetId)?.notes && (
              <p className="mt-1 text-[14px] text-[var(--am-text-tertiary)]">
                {presets.find((p) => p.id === presetId)?.notes}
              </p>
            )}
          </div>
          <div>
            <label className="mb-1 block text-[14px] font-semibold uppercase tracking-wide text-[var(--am-text-tertiary)]">
              Latitude
            </label>
            <input
              value={lat}
              onChange={(e) => setLat(e.target.value)}
              className="w-full rounded-xl border border-[var(--am-border)] bg-[var(--am-bg-muted)] px-3 py-2.5 font-mono text-[15px] text-[var(--am-text)]"
            />
          </div>
          <div>
            <label className="mb-1 block text-[14px] font-semibold uppercase tracking-wide text-[var(--am-text-tertiary)]">
              Longitude
            </label>
            <input
              value={lon}
              onChange={(e) => setLon(e.target.value)}
              className="w-full rounded-xl border border-[var(--am-border)] bg-[var(--am-bg-muted)] px-3 py-2.5 font-mono text-[15px] text-[var(--am-text)]"
            />
          </div>
          <div>
            <label className="mb-1 block text-[14px] font-semibold uppercase tracking-wide text-[var(--am-text-tertiary)]">
              Land type
            </label>
            <select
              value={landClass}
              onChange={(e) => setLandClass(e.target.value as LandClass)}
              className="w-full rounded-xl border border-[var(--am-border)] bg-[var(--am-bg-muted)] px-3 py-2.5 text-[15px] text-[var(--am-text)]"
            >
              <option value="urban">Urban</option>
              <option value="peri_urban">Peri-urban</option>
              <option value="agricultural">Agricultural</option>
              <option value="rural">Rural</option>
            </select>
          </div>
        </div>
        <div className="mt-4 flex flex-wrap items-center gap-3">
          <input
            value={label}
            onChange={(e) => setLabel(e.target.value)}
            placeholder="Location label"
            className="min-w-[200px] rounded-xl border border-[var(--am-border)] bg-[var(--am-bg-muted)] px-3 py-2.5 text-[15px] text-[var(--am-text)]"
          />
          <button
            type="button"
            onClick={handleAnalyze}
            disabled={stage === 'loading'}
            className="inline-flex min-h-11 items-center gap-2 rounded-xl bg-[var(--am-accent)] px-4 py-2.5 text-[15px] font-semibold text-white hover:bg-[var(--am-accent-hover)] disabled:opacity-60 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--am-accent)]"
          >
            {stage === 'loading' ? (
              <Loader2 className="h-4 w-4 animate-spin" aria-hidden />
            ) : (
              <CloudRain className="h-4 w-4" aria-hidden />
            )}
            {stage === 'loading' ? 'Analyzing climate…' : 'Analyze climate risk'}
          </button>
        </div>
        {error && (
          <p className="mt-3 rounded-xl border border-rose-500/30 bg-rose-950/30 px-3 py-2 text-[15px] text-rose-400">
            {error}
          </p>
        )}
      </GlassCard>

      {result && stage === 'done' && (
        <div className="space-y-5">
          <QuickSummary
            lines={summaryLines}
            technicalNote="Climate summary combines rainfall archives, short-range precipitation forecasts, river discharge risk, and indicative waterlogging estimates."
          />
          <ClimateKpiCards result={result} />
          <ClimateCharts result={result} />
          <WaterloggingPanel result={result} />
          <GlassCard hoverEffect={false} className="!rounded-[16px]">
            <h3 className="text-[17px] font-semibold text-[var(--am-text)]">Climate Summary</h3>
            <p className="mt-1 text-[16px] text-[var(--am-text-secondary)]">
              Key implications for operations and planning.
            </p>
            <p className="mt-3 text-[16px] leading-relaxed text-[var(--am-text)]">
              {plainClimateSummary(result.drought_implication?.summary)}
            </p>
            {result.drought_implication?.drivers?.length ? (
              <p className="mt-2 text-[15px] text-[var(--am-text-tertiary)]">
                Drivers: {result.drought_implication.drivers.join(' · ')}
              </p>
            ) : null}
            <p className="mt-3 border-t border-[var(--am-divider)] pt-2.5 text-[15px] text-[var(--am-text-tertiary)]">
              Technical: Summary combines rainfall deficit, heat stress, river discharge risk, and
              indicative waterlogging estimates for the selected coordinates.
            </p>
          </GlassCard>
        </div>
      )}

      {stage === 'idle' && !result && (
        <div className="rounded-[16px] border border-dashed border-[var(--am-border)] px-6 py-10 text-center">
          <p className="text-[17px] font-medium text-[var(--am-text)]">
            No data available for the selected period.
          </p>
          <p className="mt-1.5 text-[16px] text-[var(--am-text-secondary)]">
            Choose a location preset or enter coordinates, then run Analyze climate risk.
          </p>
        </div>
      )}
    </div>
  );
};

export default ClimateRiskPage;
