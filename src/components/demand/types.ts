/** Shared types for the Demand Forecast workspace. */

export type ForecastUnit = 'days' | 'weeks' | 'months' | 'years';

export type TimeRangeKey = '1M' | '3M' | '6M' | '1Y' | 'ALL';

export type SeriesPoint = {
  date: string;
  historical: number | null;
  forecast: number | null;
  lower: number | null;
  upper: number | null;
  confidence: number | null;
  risk: string | null;
  daily_change: number | null;
  rolling_avg: number | null;
  period_label?: string;
  period_index?: number;
  granularity?: ForecastUnit;
  period_change?: number | null;
};

export type ForecastSummaryData = {
  predicted_peak_demand_mgd?: number;
  predicted_minimum_mgd?: number;
  average_forecast_mgd?: number;
  growth_pct?: number;
  capacity_utilization_pct?: number | null;
  expected_shortage_risk?: string;
  expected_shortage_date?: string | null;
  confidence?: number;
  peak_date?: string;
  horizon_periods?: number;
  horizon_unit?: ForecastUnit;
  point_count?: number;
};

export type ForecastReliability = {
  reliability_tier?: string;
  confidence?: number;
  warning?: string | null;
  reliable_day_limit?: number;
  horizon_days?: number;
};

export type ForecastModelInfo = {
  model_version?: string;
  last_trained_at?: string | null;
  training_dataset_size?: number | null;
  backend?: string;
};

export type DemandWorkspaceData = {
  trained: boolean;
  message?: string;
  model_name?: string;
  model_version?: string;
  generated_at?: string;
  confidence_score?: number;
  risk_level?: string;
  risk_label?: string;
  last_trained_at?: string | null;
  capacity_mgd?: number;
  today_predicted_demand_mgd?: number;
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
  chart_series?: { date: string; prediction: number; confidence: number }[];
  summary?: ForecastSummaryData;
  insights?: string[];
  metrics?: Record<string, number | null | undefined>;
  model?: ForecastModelInfo;
};

export type HorizonState = {
  unit: ForecastUnit;
  value: number;
};

export const HORIZON_MAX: Record<ForecastUnit, number> = {
  days: 7,
  weeks: 1,
  months: 1,
  years: 1,
};

/** Max one-week horizon. Keep UI presets short. */
export const PRESETS: { label: string; unit: ForecastUnit; value: number }[] = [
  { label: 'Tomorrow', unit: 'days', value: 1 },
  { label: '3 Days', unit: 'days', value: 3 },
  { label: '7 Days', unit: 'days', value: 7 },
];
