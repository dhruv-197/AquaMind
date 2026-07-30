/** Shared national Water Assets geospatial client. */
import { apiGet } from './apiClient';

export type WaterAssetType =
  | 'reservoir'
  | 'dam'
  | 'groundwater_station'
  | 'demand_region'
  | 'water_stress_region'
  | 'leak_zone';

export type WaterAsset = {
  id: string;
  type: WaterAssetType;
  name: string;
  state?: string | null;
  lat: number;
  lng: number;
  capacity_mcm?: number | null;
  current_storage_pct?: number | null;
  forecast_storage_pct?: number | null;
  risk_level?: string | null;
  confidence?: number | null;
  last_updated?: string | null;
  meta?: Record<string, unknown>;
};

export type WaterAssetsResponse = {
  success: boolean;
  version: string;
  updated_at?: string | null;
  counts: Record<string, number>;
  total: number;
  assets: WaterAsset[];
  message: string;
};

export type GeospatialQuery = {
  types?: WaterAssetType[] | WaterAssetType;
  state?: string;
  risk_level?: string;
  bbox?: [number, number, number, number];
  q?: string;
  limit?: number;
  offset?: number;
};

const request = apiGet;

export async function fetchWaterAssets(query: GeospatialQuery = {}): Promise<WaterAssetsResponse> {
  const params = new URLSearchParams();
  if (query.types) {
    const types = Array.isArray(query.types) ? query.types : [query.types];
    params.set('types', types.join(','));
  }
  if (query.state) params.set('state', query.state);
  if (query.risk_level) params.set('risk_level', query.risk_level);
  if (query.bbox) params.set('bbox', query.bbox.join(','));
  if (query.q) params.set('q', query.q);
  if (query.limit != null) params.set('limit', String(query.limit));
  if (query.offset != null) params.set('offset', String(query.offset));
  const qs = params.toString();
  return request<WaterAssetsResponse>(`/api/v1/geospatial/assets${qs ? `?${qs}` : ''}`);
}

export async function fetchNationalReservoirs(query: Omit<GeospatialQuery, 'types'> = {}) {
  return fetchWaterAssets({ ...query, types: 'reservoir' });
}

export async function fetchWaterAsset(assetId: string): Promise<WaterAsset> {
  const body = await request<{ success: boolean; asset: WaterAsset }>(
    `/api/v1/geospatial/assets/${encodeURIComponent(assetId)}`
  );
  return body.asset;
}

/** Map risk level → Apple palette marker color. */
export function riskMarkerColor(risk?: string | null, selected = false): string {
  if (selected) return '#007AFF';
  const r = (risk || '').toLowerCase();
  if (r === 'critical') return '#FF3B30';
  if (r === 'high' || r === 'high risk') return '#FF9500';
  if (r === 'moderate' || r === 'medium') return '#FFCC00';
  if (r === 'healthy' || r === 'low') return '#34C759';
  return '#8E8E93';
}

export function riskFromStorage(pct?: number | null): string {
  if (pct == null) return 'moderate';
  if (pct < 20) return 'critical';
  if (pct < 40) return 'high';
  if (pct < 60) return 'moderate';
  return 'healthy';
}
