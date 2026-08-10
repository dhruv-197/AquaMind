/** Frontend API helpers for Reservoir Level Forecast (XGBoost production model). */
import { apiGet, apiPost, type ApiRequestInit } from './apiClient';
import type { ForecastUnit, ReservoirWorkspaceData } from '../components/reservoir/types';

export type ReservoirStatus = {
  success: boolean;
  trained: boolean;
  model_name: string;
  model_version: string;
  last_trained_at?: string | null;
  backend?: string | null;
  capacity_mcm?: number | null;
  supported_horizons: number[];
  training_rows?: number | null;
  reservoirs: ReservoirWorkspaceData['reservoirs'];
  message: string;
};

export type ReservoirMetricsResponse = {
  success: boolean;
  trained: boolean;
  metrics: Record<string, unknown>;
  message: string;
};

export async function fetchReservoirStatus(init?: ApiRequestInit): Promise<ReservoirStatus> {
  return apiGet<ReservoirStatus>('/api/v1/predictions/reservoir/status', init);
}

export async function fetchReservoirMetrics(init?: ApiRequestInit): Promise<ReservoirMetricsResponse> {
  return apiGet<ReservoirMetricsResponse>('/api/v1/predictions/reservoir/metrics', init);
}

export async function trainReservoirModel(body?: {
  use_sample?: boolean;
  validation_split?: number;
  model_version?: string;
  capacity_mcm?: number;
}): Promise<{
  success: boolean;
  message: string;
  trained: boolean;
  model_version: string;
  metrics: Record<string, unknown>;
}> {
  return apiPost('/api/v1/predictions/reservoir/train', {
    use_sample: true,
    validation_split: 0.2,
    model_version: '1.0.0',
    ...body,
  });
}

export async function predictReservoir(body: {
  value: number;
  unit: ForecastUnit;
  reservoir_id?: string;
  asset_id?: string;
  capacity_mcm?: number;
  include_history_days?: number;
}): Promise<{ success: boolean; message: string; data: ReservoirWorkspaceData }> {
  return apiPost('/api/v1/predictions/reservoir/predict', {
    value: body.value,
    unit: body.unit,
    reservoir_id: body.reservoir_id,
    asset_id: body.asset_id,
    capacity_mcm: body.capacity_mcm,
    include_history_days: body.include_history_days ?? 365,
  });
}
