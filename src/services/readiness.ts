/**
 * Technical readiness API types and loader.
 *
 * Used by Settings only - never by the main operations dashboard.
 */
import { apiGet, ApiError } from './apiClient';

export type ReadinessOverallStatus = 'ready' | 'degraded' | 'not_ready';
export type DatabaseCheckStatus = 'ready' | 'failed';
export type ModelArtifactsStatus = 'ready' | 'partial' | 'failed';
export type ProviderConfigStatus = 'configured' | 'fallback' | 'unavailable';
export type ClipsegCheckStatus = 'loaded' | 'available' | 'not_loaded' | 'unavailable';

export type ModelArtifactCheck = {
  available: boolean;
  loaded: boolean;
  model_version: string | null;
  error_category?: string;
};

export type ReadinessChecks = {
  database: {
    status: DatabaseCheckStatus;
    latency_ms: number;
  };
  model_artifacts: {
    status: ModelArtifactsStatus;
    models: Record<string, ModelArtifactCheck>;
  };
  weather_provider: {
    status: ProviderConfigStatus;
    provider?: string;
  };
  vision_provider: {
    status: ProviderConfigStatus;
    providers: {
      gemini: ProviderConfigStatus | 'unavailable' | 'configured';
      openrouter: ProviderConfigStatus | 'unavailable' | 'configured';
      dashscope: ProviderConfigStatus | 'unavailable' | 'configured';
    };
  };
  clipseg: {
    status: ClipsegCheckStatus;
    dependencies_installed?: boolean;
    note?: string;
  };
  demo_mode: {
    enabled: boolean;
    force_fixtures?: boolean;
  };
};

export type ReadinessPayload = {
  status: ReadinessOverallStatus;
  environment: string;
  timestamp: string;
  checks: ReadinessChecks;
};

function isObject(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null;
}

/** Narrow an unknown JSON body to the readiness contract. */
export function parseReadinessPayload(body: unknown): ReadinessPayload {
  if (!isObject(body)) {
    throw new Error('Readiness response was not an object.');
  }
  const status = body.status;
  if (status !== 'ready' && status !== 'degraded' && status !== 'not_ready') {
    throw new Error('Readiness response is missing a valid overall status.');
  }
  if (!isObject(body.checks)) {
    throw new Error('Readiness response is missing checks.');
  }
  return body as ReadinessPayload;
}

export async function fetchReadiness(init?: { signal?: AbortSignal }): Promise<ReadinessPayload> {
  const body = await apiGet<unknown>('/readiness', {
    signal: init?.signal,
    timeoutMs: 8_000,
  });
  return parseReadinessPayload(body);
}

export function readinessErrorMessage(error: unknown): string {
  if (error instanceof ApiError) {
    if (error.kind === 'unauthorized') {
      return 'Sign in again to view technical readiness.';
    }
    if (error.kind === 'timeout') {
      return 'Readiness check timed out.';
    }
    if (error.kind === 'network') {
      return 'Unable to reach AquaMind AI API for readiness.';
    }
    return error.message;
  }
  return error instanceof Error ? error.message : 'Unable to load readiness.';
}
