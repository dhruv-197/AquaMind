/**
 * Shared API contracts for dashboard-critical AquaMind surfaces.
 *
 * Prefer these types in new frontend code. Legacy fields remain optional so
 * older backend builds keep type-checking. Provenance vocabulary mirrors
 * `fastapi_app/core/data_quality.py` / `DataQualityMetadata`.
 */

/** Standard success envelope used by most FastAPI routes. */
export type ApiEnvelope<T> = {
  success: boolean;
  message?: string;
  timestamp?: string;
  data: T;
};

/** How a value was produced. Mirrors fastapi_app/core/data_quality.Method. */
export type DataMethod =
  | 'trained_model'
  | 'database_telemetry'
  | 'weather_provider'
  | 'engineering_estimate'
  | 'rules_engine'
  | 'vision_model'
  | 'remote_ai'
  | 'fallback';

export type DataQualityLevel = 'high' | 'medium' | 'low' | 'unknown';
export type DataFreshness = 'fresh' | 'recent' | 'stale' | 'unknown';
/** Keeps a valid zero distinct from "we could not get this at all". */
export type DataAvailability = 'available' | 'stale' | 'missing' | 'unavailable';

/**
 * Internal normalized provenance contract returned per component.
 * Intended for Details panels, tooltips, reports, and audit views.
 */
export type DataQualityMetadata = {
  source: string;
  method: DataMethod | string;
  /** Normalized 0.0–1.0, or null when the component is unavailable. */
  confidence: number | null;
  data_quality: DataQualityLevel | string;
  freshness?: DataFreshness | string;
  availability?: DataAvailability | string;
  is_stale?: boolean;
  observed_at: string | null;
  generated_at: string;
  data_age_seconds: number | null;
  model_version: string | null;
  unit?: string;
  note?: string;
};

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

export type WaterIntelligenceComponent =
  | 'water_stress'
  | 'shortage'
  | 'leak'
  | 'groundwater'
  | 'demand'
  | 'climate';

export type ShortageComponent = {
  predicted_risk_score?: number | null;
  predicted_risk_stage?: number | null;
  risk_label?: string | null;
  confidence?: number | null;
  forecast_storage_pct?: number | null;
  reservoir_capacity_pct?: number | null;
  recommended_mitigation?: string | null;
  technical_accuracy_note?: string | null;
  model_scope?: string | null;
  multi_horizon?: MultiHorizonForecast | null;
  evaluation?: Record<string, unknown> | null;
  [key: string]: unknown;
};

export type LeakComponent = {
  is_leak_detected?: boolean | null;
  leak_probability?: number | null;
  severity?: string | null;
  estimated_water_loss_lpm?: number | null;
  daily_loss_mld?: number | null;
  note?: string | null;
  model_scope?: string | null;
  test_f1?: number | null;
  field_validation_status?: string | null;
  evaluation?: Record<string, unknown> | null;
  [key: string]: unknown;
};

export type GroundwaterComponent = {
  projected_depth_m?: number | null;
  current_depth_m?: number | null;
  drawdown_rate_m?: number | null;
  aquifer_status?: string | null;
  depletion_trend?: string | null;
  latitude?: number | null;
  longitude?: number | null;
  confidence?: number | null;
  model_scope?: string | null;
  evaluation?: Record<string, unknown> | null;
  [key: string]: unknown;
};

export type DemandComponent = {
  forecasted_demand_mgd?: number | null;
  forecasted_demand_mld?: number | null;
  predicted_demand_mgd?: number | null;
  daily_demand_mgd?: number | null;
  baseline_consumption_mgd?: number | null;
  peak_surge_risk?: string | null;
  confidence?: number | null;
  model_scope?: string | null;
  test_mae_mgd?: number | null;
  evaluation?: Record<string, unknown> | null;
  [key: string]: unknown;
};

export type ClimateComponent = {
  rainfall_deficit_pct?: number | null;
  temperature_c?: number | null;
  spi3_proxy?: number | null;
  heatwave_warning?: boolean | null;
  climate_source?: string | null;
  observed_at?: string | null;
  [key: string]: unknown;
};

export type FusionContext = {
  reservoirs_sampled?: number | null;
  aquifers_sampled?: number | null;
  active_alerts?: number | null;
  population_at_risk?: number | null;
  leak_source?: string | null;
  weather_temp_c?: number | null;
  [key: string]: unknown;
};

export type MultiHorizonForecast = {
  day_1_storage_pct?: number | null;
  day_7_storage_pct?: number | null;
  day_30_storage_pct?: number | null;
  method?: string | null;
  note?: string | null;
};

export type WaterIntelligenceData = {
  water_stress: WaterStressIndex;
  shortage: ShortageComponent;
  leak: LeakComponent;
  groundwater: GroundwaterComponent;
  demand: DemandComponent;
  climate: ClimateComponent;
  context?: FusionContext | null;
  metadata?: Partial<Record<WaterIntelligenceComponent, DataQualityMetadata>>;
};

export type RecommendationItem = {
  id: string;
  priority: string;
  category: string;
  title: string;
  action_description: string;
  estimated_impact?: string;
  target_sector?: string;
  description?: string;
};

export type RecommendationData = {
  region_id?: string;
  overall_health_index?: number | null;
  recommendations: RecommendationItem[];
  policy_guidelines?: string[];
};

export type ReportItem = {
  report_id: string;
  /** Legacy alias — prefer report_id. */
  id?: string;
  title: string;
  date_generated: string;
  author: string;
  category: string;
  summary: string;
  key_metrics?: Record<string, unknown>;
  status: string;
};

export type ReportListData = {
  total_reports: number;
  filter_applied?: string | null;
  reports: ReportItem[];
};

export type AIRecommendationEngineData = {
  recommendations: string[];
  expected_saving: string;
  text_summary: string;
  source?: string | null;
  provider?: string | null;
  inputs?: Record<string, unknown> | null;
  metadata?: Partial<DataQualityMetadata> & Record<string, unknown>;
};

/** UI-facing executive briefing built from the AI recommendation engine. */
export type ExecutiveBriefing = {
  title: string;
  summary: string;
  keyFindings?: string[];
  actionPlan?: string[];
  expected_saving?: string;
  source?: string;
};

export type VisionAnalysisResult = {
  success?: boolean;
  message?: string;
  timestamp?: string;
  provider?: string;
  analysis_mode?: string;
  vision_mode?: string;
  asset_label?: string | null;
  comparison?: Record<string, unknown> | null;
  history_count?: number;
  confidence?: number | null;
  reservoir_health?: number | null;
  overall_risk?: string | null;
  data?: Record<string, unknown> | null;
  metadata?: Record<string, unknown> | null;
  /** FastAPI error payloads sometimes surface here on non-envelope failures. */
  detail?: string | unknown;
  [key: string]: unknown;
};

export type CopilotChatData = {
  answer?: string;
  response?: string;
  text?: string;
  summarized?: boolean;
  source?: string;
  suggestions?: string[];
};

/** Display helper: never render null/undefined as a believable zero. */
export function displayMetric(
  value: number | null | undefined,
  opts?: { digits?: number; suffix?: string; empty?: string }
): string {
  if (value == null || Number.isNaN(Number(value))) {
    return opts?.empty ?? '—';
  }
  const digits = opts?.digits ?? 1;
  return `${Number(value).toFixed(digits)}${opts?.suffix ?? ''}`;
}
