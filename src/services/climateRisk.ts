import { apiGet, apiPost } from './apiClient';

export type LandClass = 'urban' | 'peri_urban' | 'agricultural' | 'rural';

export interface ClimatePreset {
  id: string;
  label: string;
  lat: number;
  lon: number;
  land_class: LandClass;
  notes: string;
}

export interface ClimateRiskResult {
  success: boolean;
  provenance: {
    queried_at: string;
    location: { lat: number; lon: number; label?: string | null };
    sources: { name: string; url: string; cached?: boolean }[];
    methods: (string | null | undefined)[];
    limitations: string[];
  };
  climate: {
    spi3_proxy: Record<string, unknown>;
    rainfall_deficit: Record<string, unknown>;
    heatwave: Record<string, unknown>;
    evapotranspiration: Record<string, unknown>;
    soil_moisture: Record<string, unknown>;
    precip_series_mm: { date: string; value: number }[];
    forecast_precip_mm: { date: string; value: number }[];
    forecast_tmax_c: { date: string; value: number }[];
  };
  drought_implication: {
    shortage_climate_stress_0_100: number;
    groundwater_climate_stress_0_100: number;
    drivers: string[];
    summary: string;
  };
  flood: Record<string, unknown>;
  waterlogging: Record<string, unknown>;
  recommendations: {
    priority: number;
    action: string;
    rationale: string;
    module: string;
    href: string;
    queue_score: number;
  }[];
  priority_queue: {
    asset: string;
    type: string;
    score: number;
    action: string;
    href: string;
  }[];
  links: Record<string, string>;
}

export async function fetchClimatePresets(): Promise<ClimatePreset[]> {
  const data = await apiGet<{ presets?: ClimatePreset[] }>('/climate-risk/presets');
  return data?.presets ?? [];
}

export async function analyzeClimateRisk(input: {
  lat: number;
  lon: number;
  label?: string;
  land_class?: LandClass;
}): Promise<ClimateRiskResult> {
  return apiPost<ClimateRiskResult>('/climate-risk/analyze', input);
}
