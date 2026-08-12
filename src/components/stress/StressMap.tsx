import React, { useCallback, useMemo } from 'react';
import { SharedAssetMap } from '../maps/SharedAssetMap';
import { useWaterAssets } from '../../hooks/useWaterAssets';
import type { MapRegion } from './types';
import type { WaterAsset } from '../../services/geospatial';
import { SkeletonMap } from '../ui/Skeleton';

type Props = {
  regions: MapRegion[];
  selectedId?: string | null;
  onSelect: (id: string) => void;
};

/** Convert prediction GIS regions into WaterAsset pins for the shared map. */
function regionsToAssets(regions: MapRegion[]): WaterAsset[] {
  return regions
    .filter((r) => Number.isFinite(r.lat) && Number.isFinite(r.lng))
    .map((r) => ({
      id: r.region_id,
      type: 'water_stress_region' as const,
      name: r.name,
      state: r.region_type || undefined,
      lat: r.lat,
      lng: r.lng,
      risk_level: (r.risk_label || '').toLowerCase() || 'moderate',
      confidence: r.confidence ?? null,
      current_storage_pct: null,
      forecast_storage_pct: r.water_stress_index ?? null,
      capacity_mcm: null,
      last_updated: null,
      meta: { source: 'stress_prediction', population: r.population },
    }));
}

export const StressMap: React.FC<Props> = ({ regions, selectedId, onSelect }) => {
  const { assets: national, loading } = useWaterAssets({
    types: [
      'reservoir',
      'dam',
      'groundwater_station',
      'demand_region',
      'water_stress_region',
      'leak_zone',
    ],
  });

  const predictionAssets = useMemo(() => regionsToAssets(regions), [regions]);

  // Same national catalogue density as Dashboard / Reservoir / Demand maps.
  // Live fusion pins overlay so predicted WSI colors stay visible.
  const merged = useMemo(() => {
    const byId = new Map<string, WaterAsset>();
    national.forEach((a) => byId.set(a.id, a));
    predictionAssets.forEach((a) => byId.set(a.id, a));
    return Array.from(byId.values());
  }, [national, predictionAssets]);

  const handleSelect = useCallback(
    (asset: WaterAsset) => {
      // Every pin id is a valid fusion target (sample region or geospatial asset).
      onSelect(asset.id);
    },
    [onSelect],
  );

  if (loading && !merged.length) return <SkeletonMap height={380} />;

  return (
    <SharedAssetMap
      assets={merged}
      selectedId={selectedId}
      onSelect={handleSelect}
      height={380}
      title="Water Stress Map"
      subtitle="National assets · click any pin to reload predicted stress and past vs forecast for that site"
      variant="stress"
    />
  );
};
