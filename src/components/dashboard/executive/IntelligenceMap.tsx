import React, { useCallback, useMemo, useState } from 'react';
import { SharedAssetMap } from '../../maps/SharedAssetMap';
import { SectionTitle } from './ExecutiveKpis';
import { useWaterAssets } from '../../../hooks/useWaterAssets';
import type { WaterAsset, WaterAssetType } from '../../../services/geospatial';
import type { MapLayer, SelectedRegion } from './derive';
import { SkeletonMap } from '../../ui/Skeleton';

type Props = {
  selected: SelectedRegion;
  onSelect: (loc: SelectedRegion) => void;
  /** Optional live telemetry pins merged into the national layer */
  extraAssets?: WaterAsset[];
};

const LAYER_TO_TYPES: Record<MapLayer, WaterAssetType[]> = {
  reservoirs: ['reservoir', 'dam'],
  stress: ['water_stress_region'],
  leakage: ['leak_zone'],
  demand: ['demand_region'],
  climate: ['water_stress_region', 'demand_region'],
  decisions: ['reservoir'],
};

const LAYERS: { id: MapLayer; label: string }[] = [
  { id: 'reservoirs', label: 'Reservoirs' },
  { id: 'stress', label: 'Water Stress' },
  { id: 'leakage', label: 'Leakage' },
  { id: 'demand', label: 'Demand' },
  { id: 'climate', label: 'Climate Risk' },
  { id: 'decisions', label: 'Decisions' },
];

export const IntelligenceMap: React.FC<Props> = ({ selected, onSelect, extraAssets = [] }) => {
  const [layers, setLayers] = useState<Record<MapLayer, boolean>>({
    reservoirs: true,
    stress: true,
    leakage: true,
    demand: false,
    climate: false,
    decisions: false,
  });

  const activeTypes = useMemo(() => {
    const set = new Set<WaterAssetType>();
    (Object.keys(layers) as MapLayer[]).forEach((key) => {
      if (layers[key]) LAYER_TO_TYPES[key].forEach((t) => set.add(t));
    });
    // Always include groundwater when stress is on for richer coverage
    if (layers.stress) set.add('groundwater_station');
    return Array.from(set);
  }, [layers]);

  const { assets, loading } = useWaterAssets({
    types: activeTypes.length ? activeTypes : ['reservoir'],
  });

  const merged = useMemo(() => {
    const byId = new Map<string, WaterAsset>();
    [...assets, ...extraAssets].forEach((a) => byId.set(a.id, a));
    return Array.from(byId.values());
  }, [assets, extraAssets]);

  const toggle = (id: MapLayer) => setLayers((prev) => ({ ...prev, [id]: !prev[id] }));

  const handleSelect = useCallback(
    (asset: WaterAsset) => {
      onSelect({
        id: asset.id,
        name: asset.name,
        type: asset.type,
        severity: asset.risk_level || undefined,
        meta: asset.state || undefined,
        lat: asset.lat,
        lng: asset.lng,
      });
    },
    [onSelect],
  );

  return (
    <section className="rounded-[var(--am-radius-xl)] bg-[var(--am-bg-elevated)] p-5 shadow-[var(--am-shadow-md)]">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
        <SectionTitle
          title="National / Regional Intelligence Map"
          subtitle="Shared geospatial catalogue. Layer filters only. Select a pin to focus KPIs."
        />
        {selected ? (
          <button
            type="button"
            onClick={() => onSelect(null)}
            className="text-[15px] font-semibold text-[var(--am-accent)] hover:underline"
          >
            Clear focus · {selected.name}
          </button>
        ) : null}
      </div>

      <div className="mt-4 flex flex-wrap gap-2">
        {LAYERS.map((l) => (
          <button
            key={l.id}
            type="button"
            onClick={() => toggle(l.id)}
            className={`rounded-full px-3 py-1.5 text-[15px] font-semibold transition-colors ${
              layers[l.id]
                ? 'bg-[var(--am-accent-soft)] text-[var(--am-accent)]'
                : 'bg-[var(--am-bg-muted)] text-[var(--am-text-tertiary)]'
            }`}
          >
            {l.label}
          </button>
        ))}
      </div>

      <div className="mt-4">
        {loading && !merged.length ? (
          <SkeletonMap height={440} />
        ) : (
          <SharedAssetMap
            assets={merged}
            selectedId={selected?.id}
            onSelect={handleSelect}
            height={440}
            showLegend
            variant="dashboard"
          />
        )}
      </div>
    </section>
  );
};
