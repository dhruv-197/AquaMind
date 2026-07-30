import { apiGet, apiPost } from './apiClient';

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

export async function loadSensors(): Promise<ApiSensor[]> {
  const body = await fetchJson<{ success: boolean; sensors?: ApiSensor[] }>('/telemetry/sensors');
  return body.sensors || [];
}

export async function loadAlerts(): Promise<ApiAlert[]> {
  const body = await fetchJson<{ success: boolean; alerts?: ApiAlert[] }>('/analytics/leakages');
  return body.alerts || [];
}

export async function loadShortageRisks(): Promise<ApiShortageRisk[]> {
  const body = await fetchJson<{ success: boolean; risks?: ApiShortageRisk[] }>('/analytics/shortage-risks');
  return body.risks || [];
}

export async function loadGroundwater(): Promise<ApiAquifer[]> {
  const body = await fetchJson<{ success: boolean; aquifers?: ApiAquifer[] }>('/analytics/groundwater');
  return body.aquifers || [];
}

export async function loadWeather(): Promise<ApiWeather | null> {
  const body = await fetchJson<{ success: boolean; data?: ApiWeather }>('/weather');
  return body.data || null;
}

export async function loadReports() {
  const body = await fetchJson<{ success: boolean; data?: any }>('/reports');
  return body.data || { total_reports: 0, reports: [] };
}

export async function loadRecommendations(regionId = 'REG-1', forceRefresh = false) {
  const qs = new URLSearchParams({
    region_id: regionId,
    force_refresh: forceRefresh ? 'true' : 'false',
  });
  const body = await fetchJson<{ success: boolean; data?: any }>(`/recommendation?${qs.toString()}`);
  return body.data || { recommendations: [], overall_health_index: null };
}

/** Composite Water Stress Index component (auditable weight + contribution). */
export type WaterStressComponent = {
  score: number;
  weight: number;
  contribution: number;
  detail: string;
};

export type WaterStressDriver = {
  component: string;
  contribution: number;
  detail: string;
};

export type WaterStressIndex = {
  water_stress_index: number;
  stage: string;
  components: Record<string, WaterStressComponent>;
  weights: Record<string, number>;
  drivers: WaterStressDriver[];
  data_sources: Record<string, string>;
  method: string;
  note: string;
};

export type WaterIntelligencePayload = {
  water_stress: WaterStressIndex;
  shortage: Record<string, unknown>;
  leak: Record<string, unknown>;
  groundwater: Record<string, unknown>;
  demand: Record<string, unknown>;
  climate: Record<string, unknown>;
  context?: Record<string, unknown>;
};

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
export async function fetchWaterStress(): Promise<WaterIntelligencePayload> {
  const body = await fetchJson<{ success: boolean; data: WaterIntelligencePayload }>(
    '/analytics/water-stress'
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
