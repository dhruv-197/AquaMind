/** Shared types for the Reservoir Forecast workspace. */
import type { ForecastUnit, SeriesPoint, TimeRangeKey, ForecastReliability, ForecastModelInfo, HorizonState } from '../demand/types';

export type { ForecastUnit, SeriesPoint, TimeRangeKey, ForecastReliability, ForecastModelInfo, HorizonState };
export { HORIZON_MAX, PRESETS } from '../demand/types';

export type ReservoirInfo = {
  reservoir_id: string;
  reservoir_name: string;
  capacity_mcm?: number | null;
  current_storage_pct?: number | null;
  location_lat?: number | null;
  location_lng?: number | null;
  observed_at?: string | null;
};

export type ReservoirSummaryData = {
  current_storage_pct?: number | null;
  forecasted_storage_pct?: number | null;
  forecasted_storage_mcm?: number | null;
  remaining_usable_storage_mcm?: number | null;
  peak_storage_pct?: number | null;
  minimum_storage_pct?: number | null;
  average_forecast_pct?: number | null;
  storage_change_pct?: number | null;
  days_to_critical?: number | null;
  remaining_days?: number | null;
  risk_label?: string | null;
  confidence?: number | null;
  peak_date?: string | null;
  minimum_date?: string | null;
  horizon_periods?: number;
  horizon_unit?: ForecastUnit;
  point_count?: number;
  capacity_mcm?: number | null;
};

export type ExecutiveRecommendation = {
  id: string;
  text: string;
  priority?: string;
  risk_level?: string;
  risk_label?: string;
};

export type ReservoirWorkspaceData = {
  trained: boolean;
  message?: string;
  model_name?: string;
  model_version?: string;
  generated_at?: string;
  confidence_score?: number;
  risk_level?: string;
  risk_label?: string;
  last_trained_at?: string | null;
  capacity_mcm?: number;
  reservoir_id?: string;
  reservoir_name?: string;
  current_storage_pct?: number;
  forecasted_storage_pct?: number;
  forecasted_storage_mcm?: number;
  remaining_usable_storage_mcm?: number;
  horizon?: {
    value: number;
    unit: ForecastUnit;
    days: number;
    point_count?: number;
    granularity?: ForecastUnit;
    note?: string;
  };
  reliability?: ForecastReliability;
  series?: SeriesPoint[];
  forecast_series?: SeriesPoint[];
  summary?: ReservoirSummaryData;
  insights?: string[];
  executive_recommendations?: ExecutiveRecommendation[];
  metrics?: Record<string, number | null | undefined>;
  model?: ForecastModelInfo;
  reservoirs?: ReservoirInfo[];
};
