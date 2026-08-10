import React, { useCallback, useEffect, useState } from 'react';
import { Activity, RefreshCw, Loader2, CheckCircle2, AlertTriangle, XCircle } from 'lucide-react';
import { GlassCard } from '../common/GlassCard';
import { Button } from '../ui/Button';
import { Badge } from '../ui/Badge';
import {
  fetchReadiness,
  readinessErrorMessage,
  type ModelArtifactCheck,
  type ReadinessOverallStatus,
  type ReadinessPayload,
} from '../../services/readiness';

type Props = {
  isLight: boolean;
};

function overallTone(status: ReadinessOverallStatus): 'success' | 'warning' | 'danger' | 'neutral' {
  if (status === 'ready') return 'success';
  if (status === 'degraded') return 'warning';
  return 'danger';
}

function overallLabel(status: ReadinessOverallStatus): string {
  if (status === 'ready') return 'Ready';
  if (status === 'degraded') return 'Degraded';
  return 'Not ready';
}

function StatusIcon({ status }: { status: ReadinessOverallStatus | string }) {
  if (status === 'ready' || status === 'configured' || status === 'loaded') {
    return <CheckCircle2 className="h-3.5 w-3.5 text-[var(--am-success)]" />;
  }
  if (status === 'degraded' || status === 'partial' || status === 'fallback' || status === 'not_loaded') {
    return <AlertTriangle className="h-3.5 w-3.5 text-[var(--am-warning)]" />;
  }
  return <XCircle className="h-3.5 w-3.5 text-[var(--am-danger)]" />;
}

function Row({
  label,
  value,
  detail,
  monoRow,
  muted,
}: {
  label: string;
  value: string;
  detail?: string;
  monoRow: string;
  muted: string;
}) {
  return (
    <div className={`flex items-start justify-between gap-3 rounded-lg px-2.5 py-2 font-mono text-[13px] ${monoRow}`}>
      <span className="min-w-0 truncate text-[var(--am-text-secondary)]">{label}</span>
      <span className="shrink-0 text-right">
        <span className="inline-flex items-center gap-1.5 font-semibold text-[var(--am-text)]">
          <StatusIcon status={value} />
          {value.replace(/_/g, ' ')}
        </span>
        {detail ? <span className={`mt-0.5 block text-[12px] ${muted}`}>{detail}</span> : null}
      </span>
    </div>
  );
}

export const ReadinessPanel: React.FC<Props> = ({ isLight }) => {
  const [payload, setPayload] = useState<ReadinessPayload | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  const monoRow = isLight
    ? 'bg-slate-50 border border-slate-200'
    : 'bg-slate-900 border border-slate-800';
  const muted = isLight ? 'text-slate-500' : 'text-slate-400';
  const accent = isLight ? 'text-sky-700' : 'text-cyan-400';

  const load = useCallback(async (signal?: AbortSignal) => {
    setLoading(true);
    setError(null);
    try {
      const next = await fetchReadiness({ signal });
      setPayload(next);
    } catch (err) {
      if (err instanceof DOMException && err.name === 'AbortError') return;
      setPayload(null);
      setError(readinessErrorMessage(err));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    const controller = new AbortController();
    void load(controller.signal);
    return () => controller.abort();
  }, [load]);

  const models: Record<string, ModelArtifactCheck> = payload?.checks.model_artifacts.models ?? {};
  const modelSummary = Object.entries(models)
    .map(([name, info]) => {
      const short = name.replace(/_/g, ' ');
      if (info.loaded) return `${short}: loaded`;
      if (info.available) return `${short}: on disk`;
      return `${short}: missing`;
    })
    .join(' · ');

  const vision = payload?.checks.vision_provider;
  const visionDetail = vision
    ? `Gemini ${vision.providers.gemini} · OpenRouter ${vision.providers.openrouter} · DashScope ${vision.providers.dashscope}`
    : undefined;

  const checkedAt = payload?.timestamp
    ? new Date(payload.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' })
    : null;

  return (
    <GlassCard className="md:col-span-2">
      <div className={`mb-4 flex flex-wrap items-center justify-between gap-3 font-bold text-[15px] ${accent}`}>
        <span className="inline-flex items-center gap-2">
          <Activity className="h-4 w-4" /> Technical readiness
        </span>
        <div className="flex items-center gap-2">
          {payload ? <Badge tone={overallTone(payload.status)}>{overallLabel(payload.status)}</Badge> : null}
          <Button variant="secondary" size="sm" onClick={() => void load()} loading={loading}>
            <RefreshCw className="mr-1.5 h-3.5 w-3.5" />
            Refresh
          </Button>
        </div>
      </div>

      <p className={`mb-4 text-[14px] leading-relaxed ${muted}`}>
        Pre-demo check for database, local models, and optional providers. Secrets and filesystem
        paths are never shown here.
      </p>

      {loading && !payload ? (
        <div className={`inline-flex items-center gap-2 text-[14px] ${muted}`}>
          <Loader2 className="h-4 w-4 animate-spin" /> Checking readiness...
        </div>
      ) : null}

      {error ? (
        <div className="rounded-xl bg-[var(--am-warning-soft)] px-4 py-3 text-[14px] text-[var(--am-warning)]">
          {error}
        </div>
      ) : null}

      {payload ? (
        <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
          <Row
            label="Database"
            value={payload.checks.database.status}
            detail={`${payload.checks.database.latency_ms} ms · ${payload.environment}`}
            monoRow={monoRow}
            muted={muted}
          />
          <Row
            label="Model artifacts"
            value={payload.checks.model_artifacts.status}
            detail={modelSummary || undefined}
            monoRow={monoRow}
            muted={muted}
          />
          <Row
            label="Weather provider"
            value={payload.checks.weather_provider.status}
            detail={payload.checks.weather_provider.provider}
            monoRow={monoRow}
            muted={muted}
          />
          <Row
            label="Vision providers"
            value={payload.checks.vision_provider.status}
            detail={visionDetail}
            monoRow={monoRow}
            muted={muted}
          />
          <Row
            label="CLIPSeg"
            value={payload.checks.clipseg.status}
            detail={payload.checks.clipseg.note}
            monoRow={monoRow}
            muted={muted}
          />
          <Row
            label="Demo mode"
            value={payload.checks.demo_mode.enabled ? 'enabled' : 'disabled'}
            detail={
              payload.checks.demo_mode.force_fixtures ? 'Fixtures forced for offline rehearsal' : undefined
            }
            monoRow={monoRow}
            muted={muted}
          />
        </div>
      ) : null}

      {checkedAt ? (
        <p className={`mt-3 text-[13px] ${muted}`}>Last checked {checkedAt}</p>
      ) : null}
    </GlassCard>
  );
};

export default ReadinessPanel;
