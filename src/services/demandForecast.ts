/** Frontend API helpers for Water Demand Forecast (XGBoost production model). */
import { apiGet, apiPost } from './apiClient';
import type { DemandWorkspaceData, ForecastUnit } from '../components/demand/types';

export type DemandStatus = {
  success: boolean;
  trained: boolean;
  model_name: string;
  model_version: string;
  last_trained_at?: string | null;
  backend?: string | null;
  capacity_mgd?: number | null;
  supported_horizons: number[];
  training_rows?: number | null;
  message: string;
};

export type DemandMetricsResponse = {
  success: boolean;
  trained: boolean;
  metrics: Record<string, unknown>;
  message: string;
};

export type DemandPredictData = DemandWorkspaceData;

export async function fetchDemandStatus(): Promise<DemandStatus> {
  return apiGet<DemandStatus>('/api/v1/predictions/demand/status');
}

export async function fetchDemandMetrics(): Promise<DemandMetricsResponse> {
  return apiGet<DemandMetricsResponse>('/api/v1/predictions/demand/metrics');
}

export async function trainDemandModel(body?: {
  use_sample?: boolean;
  validation_split?: number;
  model_version?: string;
  capacity_mgd?: number;
}): Promise<{
  success: boolean;
  message: string;
  trained: boolean;
  model_version: string;
  metrics: Record<string, unknown>;
}> {
  return apiPost('/api/v1/predictions/demand/train', {
    use_sample: true,
    validation_split: 0.2,
    model_version: '1.0.0',
    ...body,
  });
}

export async function predictDemand(body: {
  value: number;
  unit: ForecastUnit;
  capacity_mgd?: number;
  include_history_days?: number;
}): Promise<{ success: boolean; message: string; data: DemandPredictData }> {
  return apiPost('/api/v1/predictions/demand/predict', {
    value: body.value,
    unit: body.unit,
    capacity_mgd: body.capacity_mgd,
    include_history_days: body.include_history_days ?? 365,
  });
}
