import type {
  RecommendationData,
  ReportListData,
} from '../types/apiContracts';
import { apiGet, apiPost, type ApiRequestInit } from './apiClient';

export const fetchJson = apiGet;
export const postJson = apiPost;

export type ApiSensor = {
  id: string;
  name: string;
  type: string;
  status: string;
  value: number;
  unit: string;
  batteryLevel: number;
  pipeId?: string;
  lastUpdated?: string;
  location: { lat: number; lng: number; address: string; zone: string };
};

export type ApiAlert = {
  id: string;
  sensorId?: string;
  locationName: string;
  lat: number;
  lng: number;
  zone: string;
  pipeMaterial: string;
  pipeAgeYears: number;
  detectedFlowDropPercent: number;
  anomalyScore: number;
  estimatedWaterLossLpm: number;
  severity: string;
  status: string;
  timestamp?: string;
  aiDiagnostics: string;
};

export type ApiShortageRisk = {
  id: string;
  name: string;
  capacity: number;
  currentLevel: number;
  coordinates: [number, number];
  estimatedDaysRemaining: number;
  severity: string;
};

export type ApiAquifer = {
  id: string;
  name: string;
  depthToWaterM: number;
  depletionRateMYear: number;
  rechargeRateMYear: number;
  storageVolumeMcm: number;
  safeYieldMcm: number;
  projectedDepletionYear: number;
  soilMoistureIndex: number;
  lat: number;
  lng: number;
  state?: string;
  dataSource?: string;
  observedAt?: string;
};

export type ApiWeather = {
  location: string;
  temperature_c: number;
  humidity_pct: number;
  precipitation_mm: number;
  rainfall_deficit_pct: number;
  heatwave_warning: boolean;
  uv_index: number;
  evapotranspiration_rate_mm: number;
  forecast_5_day?: Array<Record<string, unknown>>;
};

export async function loadSensors(init?: ApiRequestInit): Promise<ApiSensor[]> {
  const body = await fetchJson<{ success: boolean; sensors?: ApiSensor[] }>('/telemetry/sensors', init);
  return body.sensors || [];
}

export async function loadAlerts(init?: ApiRequestInit): Promise<ApiAlert[]> {
  const body = await fetchJson<{ success: boolean; alerts?: ApiAlert[] }>('/analytics/leakages', init);
  return body.alerts || [];
}

export async function loadShortageRisks(init?: ApiRequestInit): Promise<ApiShortageRisk[]> {
  const body = await fetchJson<{ success: boolean; risks?: ApiShortageRisk[] }>(
    '/analytics/shortage-risks',
    init
  );
  return body.risks || [];
}

export async function loadGroundwater(init?: ApiRequestInit): Promise<ApiAquifer[]> {
  const body = await fetchJson<{ success: boolean; aquifers?: ApiAquifer[] }>(
    '/analytics/groundwater',
    init
  );
  return body.aquifers || [];
}

export async function loadWeather(init?: ApiRequestInit): Promise<ApiWeather | null> {
  const body = await fetchJson<{ success: boolean; data?: ApiWeather }>('/weather', init);
  return body.data || null;
}

export async function loadReports(init?: ApiRequestInit): Promise<ReportListData> {
  const body = await fetchJson<{ success: boolean; data?: ReportListData }>('/reports', init);
  return body.data || { total_reports: 0, reports: [] };
}

export async function loadRecommendations(
  regionId = 'REG-1',
  forceRefresh = false,
  init?: ApiRequestInit
): Promise<RecommendationData> {
  const qs = new URLSearchParams({
    region_id: regionId,
    force_refresh: forceRefresh ? 'true' : 'false',
  });
  const body = await fetchJson<{ success: boolean; data?: RecommendationData }>(
    `/recommendation?${qs.toString()}`,
    init
  );
  return body.data || { recommendations: [], overall_health_index: null };
}

/** Composite Water Stress Index component (auditable weight + contribution). */
export type WaterStressComponent = import('../types/apiContracts').WaterStressComponent;
export type WaterStressDriver = import('../types/apiContracts').WaterStressDriver;
export type WaterStressIndex = import('../types/apiContracts').WaterStressIndex;

/** How a value was produced. Mirrors fastapi_app/core/data_quality.Method. */
export type DataMethod = import('../types/apiContracts').DataMethod;
export type DataQualityLevel = import('../types/apiContracts').DataQualityLevel;
export type DataFreshness = import('../types/apiContracts').DataFreshness;
export type DataAvailability = import('../types/apiContracts').DataAvailability;
export type DataQualityMetadata = import('../types/apiContracts').DataQualityMetadata;
export type NormalizedMeasurement = DataQualityMetadata & {
  value: number | null;
  unit: string;
};
export type WaterIntelligenceComponent = import('../types/apiContracts').WaterIntelligenceComponent;

export type WaterIntelligencePayload = import('../types/apiContracts').WaterIntelligenceData;

/** Metadata for one component, or null when the backend did not supply it. */
export function componentMetadata(
  payload: WaterIntelligencePayload | null | undefined,
  component: WaterIntelligenceComponent
): DataQualityMetadata | null {
  return payload?.metadata?.[component] ?? null;
}

/** Human-readable data age for Details panels. Never invents a timestamp. */
export function formatDataAge(metadata: DataQualityMetadata | null | undefined): string {
  const age = metadata?.data_age_seconds;
  if (metadata == null || age == null) return 'Observation time unknown';
  if (age < 90) return 'Updated just now';
  if (age < 3600) return `Updated ${Math.round(age / 60)} min ago`;
  if (age < 86400) return `Updated ${Math.round(age / 3600)} h ago`;
  return `Updated ${Math.round(age / 86400)} d ago`;
}

/** True only when the backend positively reports the component as usable. */
export function isComponentUsable(metadata: DataQualityMetadata | null | undefined): boolean {
  return metadata?.availability === 'available';
}

export type WaterIntelligenceOverrides = {
  reservoir_capacity_pct?: number;
  rainfall_deficit_pct?: number;
  temperature_c?: number;
  daily_demand_mgd?: number;
  day_of_month?: number;
  leak_probability?: number;
  estimated_water_loss_lpm?: number;
  is_leak_detected?: boolean;
  current_depth_m?: number;
  depletion_rate_m_year?: number;
  population_thousands?: number;
  industrial_activity_idx?: number;
  is_weekend?: number;
  is_heatwave?: number;
  spi3_proxy?: number;
  heatwave_warning?: boolean;
};

/**
 * Live WSI from DB + sklearn models.
 * GET /analytics/water-stress
 */
export async function fetchWaterStress(init?: ApiRequestInit): Promise<WaterIntelligencePayload> {
  const body = await fetchJson<{ success: boolean; data: WaterIntelligencePayload }>(
    '/analytics/water-stress',
    init
  );
  if (!body.data?.water_stress) {
    throw new Error('Water stress response missing data.water_stress');
  }
  return body.data;
}

/**
 * Fused prediction with optional overrides.
 * POST /predict/water-intelligence
 *
 * Example:
 *   const data = await predictWaterIntelligence({
 *     reservoir_capacity_pct: 34.2,
 *     rainfall_deficit_pct: -20,
 *     spi3_proxy: -1.2,
 *   });
 *   console.log(data.water_stress.water_stress_index, data.water_stress.stage);
 *   console.log(data.water_stress.drivers); // top stress contributors
 */
export async function predictWaterIntelligence(
  overrides: WaterIntelligenceOverrides = {}
): Promise<WaterIntelligencePayload> {
  const body = await postJson<{ success: boolean; data: WaterIntelligencePayload }>(
    '/predict/water-intelligence',
    overrides
  );
  if (!body.data?.water_stress) {
    throw new Error('Water intelligence response missing data.water_stress');
  }
  return body.data;
}
