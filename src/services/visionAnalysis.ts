/** Typed AquaLens vision analysis client. */
import { apiGet, apiUpload, type ApiRequestInit } from './apiClient';
import type { VisionAnalysisResult } from '../types/apiContracts';
import type { VisionHistoryItem } from '../components/vision/VisionHistoryTimeline';

export async function analyzeVisionImage(
  formData: FormData,
  init?: ApiRequestInit
): Promise<VisionAnalysisResult> {
  return apiUpload<VisionAnalysisResult>('/api/vision/analyze', formData, init);
}

export async function fetchVisionHistory(
  params: { asset_label?: string; vision_mode?: string; limit?: number; force_refresh?: boolean } = {},
  init?: ApiRequestInit,
): Promise<{ success: boolean; total: number; history: VisionHistoryItem[] }> {
  const qs = new URLSearchParams();
  if (params.asset_label) qs.set('asset_label', params.asset_label);
  if (params.vision_mode) qs.set('vision_mode', params.vision_mode);
  if (params.limit != null) qs.set('limit', String(params.limit));
  if (params.force_refresh) qs.set('force_refresh', 'true');
  const suffix = qs.toString() ? `?${qs.toString()}` : '';
  return apiGet(`/api/vision/history${suffix}`, init);
}
