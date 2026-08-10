/** Frontend API helpers for Water Stress Intelligence fusion layer. */
import { apiGet, apiPost, type ApiRequestInit } from './apiClient';
import type { StressScenario, StressStatus, StressWorkspaceData } from '../components/stress/types';

export async function fetchStressStatus(init?: ApiRequestInit): Promise<StressStatus> {
  return apiGet<StressStatus>('/api/v1/predictions/stress/status', init);
}

export async function predictStress(
  body: {
    region_id?: string;
    horizon_days?: number;
    reservoir_id?: string;
    include_all_regions?: boolean;
    scenario?: StressScenario;
  },
  init?: ApiRequestInit,
): Promise<{ success: boolean; message: string; data: StressWorkspaceData }> {
  return apiPost(
    '/api/v1/predictions/stress/predict',
    {
      region_id: body.region_id,
      horizon_days: body.horizon_days ?? 30,
      reservoir_id: body.reservoir_id,
      include_all_regions: body.include_all_regions ?? true,
      scenario: body.scenario,
    },
    init,
  );
}

export async function simulateStress(
  body: {
    region_id?: string;
    horizon_days?: number;
    reservoir_id?: string;
    scenario?: StressScenario;
    preset_id?: string;
    include_all_regions?: boolean;
  },
  init?: ApiRequestInit,
): Promise<{ success: boolean; message: string; data: StressWorkspaceData }> {
  return apiPost(
    '/api/v1/predictions/stress/simulate',
    {
      region_id: body.region_id,
      horizon_days: body.horizon_days ?? 30,
      reservoir_id: body.reservoir_id,
      scenario: body.scenario || {},
      preset_id: body.preset_id,
      include_all_regions: body.include_all_regions ?? true,
    },
    init,
  );
}
