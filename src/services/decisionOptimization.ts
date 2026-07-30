/** API helpers for Decision Optimization Engine. */
import { apiGet, apiPost } from './apiClient';
import type { DecisionStatus, DecisionWorkspaceData } from '../components/decision/types';

export async function fetchDecisionStatus(): Promise<DecisionStatus> {
  return apiGet<DecisionStatus>('/api/v1/decision/status');
}

export async function recommendDecisions(body?: {
  region_id?: string;
  reservoir_id?: string;
  horizon_days?: number;
  max_actions?: number;
}): Promise<{ success: boolean; message: string; data: DecisionWorkspaceData }> {
  return apiPost('/api/v1/decision/recommend', {
    region_id: body?.region_id,
    reservoir_id: body?.reservoir_id,
    horizon_days: body?.horizon_days ?? 30,
    max_actions: body?.max_actions ?? 12,
    include_upstream: true,
  });
}

export async function compareStrategies(body?: {
  region_id?: string;
  reservoir_id?: string;
  horizon_days?: number;
  max_actions?: number;
  aggressiveness?: number;
}): Promise<{ success: boolean; message: string; data: DecisionWorkspaceData }> {
  return apiPost('/api/v1/decision/compare', {
    region_id: body?.region_id,
    reservoir_id: body?.reservoir_id,
    horizon_days: body?.horizon_days ?? 30,
    max_actions: body?.max_actions ?? 8,
    aggressiveness: body?.aggressiveness ?? 1.0,
  });
}
