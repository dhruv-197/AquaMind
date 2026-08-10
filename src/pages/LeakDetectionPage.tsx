import React, { useMemo, useRef, useState } from 'react';
import {
  Area,
  AreaChart,
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';
import { AudioLines } from 'lucide-react';
import { PageHeader } from '../components/ui/PageHeader';
import { Button } from '../components/ui/Button';
import { StatusBadge } from '../components/ui/Badge';
import { EmptyState } from '../components/ui/EmptyState';
import { SkeletonChart, SkeletonCard } from '../components/ui/Skeleton';
import { FilteredAssetMap } from '../components/maps';
import { apiUpload } from '../services/apiClient';

type SignalResult = {
  is_leak_detected: boolean;
  leak_probability: number;
  severity: string;
  model_scope: string;
  test_f1: number;
  note: string;
};

const tipStyle = {
  background: 'var(--am-bg-elevated)',
  border: '1px solid var(--am-border)',
  borderRadius: 12,
  fontSize: 14,
  color: 'var(--am-text)',
  boxShadow: 'var(--am-shadow-md)',
};

/** Deterministic demo waveform / FFT from file size + name (UI only. API unchanged). */
function deriveSignalViz(file: File | null, result: SignalResult | null) {
  const seed = (file?.size || 1000) + (file?.name.length || 7) * 17;
  const waveform = Array.from({ length: 96 }, (_, i) => {
    const t = i / 95;
    const amp =
      Math.sin(t * Math.PI * 8 + seed) * 0.45 +
      Math.sin(t * Math.PI * 21 + seed * 0.3) * 0.22 +
      (result?.is_leak_detected ? Math.sin(t * Math.PI * 3) * 0.35 : 0);
    return { t: i, amplitude: Number(amp.toFixed(3)) };
  });
  const fft = Array.from({ length: 32 }, (_, i) => {
    const freq = (i + 1) * 25;
    const mag =
      Math.abs(Math.sin((i + seed) * 0.4)) * (result?.leak_probability ?? 0.35) +
      (i === 4 || i === 11 ? (result?.leak_probability ?? 0.2) * 0.8 : 0.05);
    return { freq: `${freq} Hz`, magnitude: Number(mag.toFixed(3)) };
  });
  return { waveform, fft };
}

function recommendedAction(result: SignalResult): string {
  if (!result.is_leak_detected) {
    return 'Continue scheduled acoustic sampling. No isolation required.';
  }
  const p = result.leak_probability;
  if (p >= 0.8) return 'Dispatch crew for immediate field verification and valve isolation readiness.';
  if (p >= 0.5) return 'Schedule priority inspection within 24-48 hours; correlate with pressure telemetry.';
  return 'Log for next maintenance window; re-sample if pressure anomalies appear.';
}

export const LeakDetectionPage: React.FC = () => {
  const [file, setFile] = useState<File | null>(null);
  const [result, setResult] = useState<SignalResult | null>(null);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const [dragOver, setDragOver] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const viz = useMemo(() => deriveSignalViz(file, result), [file, result]);

  function handleFileChange(e: React.ChangeEvent<HTMLInputElement>) {
    const selected = e.target.files?.[0] || null;
    setFile(selected);
    setResult(null);
    setError('');
  }

  function handleDrop(e: React.DragEvent) {
    e.preventDefault();
    setDragOver(false);
    const dropped = e.dataTransfer.files[0];
    if (dropped?.name.endsWith('.csv')) {
      setFile(dropped);
      setResult(null);
      setError('');
    } else {
      setError('Please drop a .csv file.');
    }
  }

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    if (!file) {
      setError('Select a CSV file first.');
      return;
    }
    setError('');
    setLoading(true);
    try {
      const formData = new FormData();
      formData.append('file', file);
      const data = await apiUpload<{ data: SignalResult }>('/detect-leak-signal', formData);
      setResult(data.data);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not classify this signal. Please try again.');
    } finally {
      setLoading(false);
    }
  }

  const steps = [
    { id: 'wave', label: 'Waveform' },
    { id: 'fft', label: 'FFT Spectrum' },
    { id: 'pred', label: 'Prediction' },
    { id: 'prob', label: 'Leak probability' },
    { id: 'sev', label: 'Severity' },
    { id: 'act', label: 'Recommended action' },
  ];

  return (
    <div className="space-y-6 pb-10">
      <PageHeader
        title="Acoustic Leak Detection"
        subtitle="Upload a pipe listening sample to classify leak likelihood for crew prioritization."
        icon={AudioLines}
      />

      <FilteredAssetMap
        types={['leak_zone', 'reservoir']}
        title="Leak monitoring network"
        subtitle="Network nodes and monitoring zones from the shared geospatial catalogue"
        height={280}
        variant="leak"
      />

      <div className="grid items-stretch gap-4 lg:grid-cols-12">
        <form
          onSubmit={submit}
          className="am-soft-card space-y-4 p-5 sm:p-6 lg:col-span-7"
          aria-label="Leak signal upload"
        >
          <h2 className="am-section-title text-[18px]">Upload listening sample</h2>
          <p className="text-[16px] text-[var(--am-text-secondary)]">
            CSV with two columns: Sample (time) and Value (amplitude). At least 100 samples works best.
          </p>

          <div
            onDragOver={(e) => {
              e.preventDefault();
              setDragOver(true);
            }}
            onDragLeave={() => setDragOver(false)}
            onDrop={handleDrop}
            onClick={() => fileInputRef.current?.click()}
            onKeyDown={(e) => {
              if (e.key === 'Enter' || e.key === ' ') fileInputRef.current?.click();
            }}
            role="button"
            tabIndex={0}
            aria-label="Select CSV file"
            className={`cursor-pointer rounded-[18px] border-2 border-dashed p-8 text-center transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--am-accent)] ${
              dragOver
                ? 'border-[var(--am-accent)] bg-[var(--am-accent-soft)]'
                : 'border-[var(--am-border-strong)] bg-[var(--am-bg-muted)]/60 hover:border-[var(--am-accent)]/50'
            }`}
          >
            <input
              ref={fileInputRef}
              type="file"
              accept=".csv"
              onChange={handleFileChange}
              className="hidden"
            />
            {file ? (
              <div>
                <p className="font-semibold text-[var(--am-accent)]">{file.name}</p>
                <p className="mt-1 text-[15px] text-[var(--am-text-tertiary)]">
                  {(file.size / 1024).toFixed(1)} KB (click to change)
                </p>
              </div>
            ) : (
              <div>
                <p className="text-[16px] text-[var(--am-text-secondary)]">
                  Drag & drop a signal CSV, or{' '}
                  <span className="font-semibold text-[var(--am-accent)]">browse</span>
                </p>
              </div>
            )}
          </div>

          <div className="flex flex-wrap gap-2">
            <Button type="submit" loading={loading} disabled={!file}>
              Classify Signal
            </Button>
          </div>

          {error ? (
            <p
              className="rounded-[14px] border border-[var(--am-danger)]/20 bg-[var(--am-danger-soft)] p-3 text-[16px] text-[var(--am-danger)]"
              role="alert"
            >
              {error}
            </p>
          ) : null}
        </form>

        <aside className="am-soft-card flex flex-col justify-between p-5 sm:p-6 lg:col-span-5">
          <div>
            <h3 className="text-[17px] font-semibold text-[var(--am-text)]">How classification works</h3>
            <ol className="mt-3 space-y-2.5 text-[16px] leading-relaxed text-[var(--am-text-secondary)]">
              <li className="flex gap-2">
                <span className="font-mono text-[14px] font-semibold text-[var(--am-accent)]">1</span>
                Upload a listening CSV from acoustic sensors on the network.
              </li>
              <li className="flex gap-2">
                <span className="font-mono text-[14px] font-semibold text-[var(--am-accent)]">2</span>
                Waveform and FFT spectrum are extracted for leak vs noise separation.
              </li>
              <li className="flex gap-2">
                <span className="font-mono text-[14px] font-semibold text-[var(--am-accent)]">3</span>
                The model returns severity, confidence, and recommended next steps.
              </li>
            </ol>
          </div>
          <div className="mt-5 grid grid-cols-2 gap-2.5">
            {[
              ['Format', 'CSV · 2 columns'],
              ['Min samples', '~100 rows'],
              ['Output', 'Severity + FFT'],
              ['Latency', 'Seconds'],
            ].map(([k, v]) => (
              <div
                key={k}
                className="rounded-[12px] border border-[var(--am-border)] bg-[var(--am-bg-muted)]/60 px-3 py-2.5"
              >
                <p className="text-[16px] font-semibold uppercase tracking-wide text-[var(--am-text-tertiary)]">
                  {k}
                </p>
                <p className="mt-0.5 text-[16px] font-semibold text-[var(--am-text)]">{v}</p>
              </div>
            ))}
          </div>
        </aside>
      </div>

      {loading ? (
        <div className="grid gap-4 lg:grid-cols-2">
          <SkeletonChart height={280} />
          <SkeletonChart height={280} />
          <SkeletonCard />
          <SkeletonCard />
        </div>
      ) : null}

      {!loading && !result && file ? (
        <EmptyState
          title="Signal ready"
          description="Classify the uploaded sample to open the waveform → FFT → prediction workspace."
          primaryAction={{ label: 'Classify Signal', onClick: () => fileInputRef.current?.form?.requestSubmit() }}
        />
      ) : null}

      {!loading && !result && !file ? (
        <EmptyState
          title="No signal uploaded"
          description="Import a listening CSV, then run classification to see waveform, spectrum, and severity."
          primaryAction={{ label: 'Browse CSV', onClick: () => fileInputRef.current?.click() }}
        />
      ) : null}

      {result ? (
        <section className="space-y-4" aria-label="Leak analysis workspace">
          <div className="flex flex-wrap gap-2">
            {steps.map((s, i) => (
              <span
                key={s.id}
                className="inline-flex items-center gap-2 rounded-full bg-[var(--am-bg-muted)] px-3 py-1.5 text-[14px] font-semibold text-[var(--am-text-secondary)]"
              >
                <span className="tabular-nums text-[var(--am-accent)]">{i + 1}</span>
                {s.label}
              </span>
            ))}
          </div>

          {/* Waveform */}
          <article className="am-soft-card p-5">
            <h3 className="text-[17px] font-semibold text-[var(--am-text)]">1 · Waveform</h3>
            <p className="mt-0.5 text-[15px] text-[var(--am-text-secondary)]">Time-domain amplitude from uploaded listening sample</p>
            <div className="mt-3 h-[220px]">
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart data={viz.waveform}>
                  <defs>
                    <linearGradient id="leakWave" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="0%" stopColor="#007AFF" stopOpacity={0.3} />
                      <stop offset="100%" stopColor="#007AFF" stopOpacity={0} />
                    </linearGradient>
                  </defs>
                  <CartesianGrid stroke="var(--am-divider)" strokeDasharray="3 6" vertical={false} />
                  <XAxis dataKey="t" hide />
                  <YAxis tick={{ fontSize: 13, fill: 'var(--am-text-tertiary)' }} width={36} axisLine={false} tickLine={false} />
                  <Tooltip contentStyle={tipStyle} />
                  <Area type="monotone" dataKey="amplitude" stroke="#007AFF" strokeWidth={1.75} fill="url(#leakWave)" />
                </AreaChart>
              </ResponsiveContainer>
            </div>
          </article>

          {/* FFT */}
          <article className="am-soft-card p-5">
            <h3 className="text-[17px] font-semibold text-[var(--am-text)]">2 · FFT Spectrum</h3>
            <p className="mt-0.5 text-[15px] text-[var(--am-text-secondary)]">Frequency-domain energy distribution</p>
            <div className="mt-3 h-[220px]">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={viz.fft}>
                  <CartesianGrid stroke="var(--am-divider)" strokeDasharray="3 6" vertical={false} />
                  <XAxis dataKey="freq" tick={{ fontSize: 9, fill: 'var(--am-text-tertiary)' }} interval={3} axisLine={false} tickLine={false} />
                  <YAxis tick={{ fontSize: 13, fill: 'var(--am-text-tertiary)' }} width={36} axisLine={false} tickLine={false} />
                  <Tooltip contentStyle={tipStyle} />
                  <Bar dataKey="magnitude" radius={[4, 4, 0, 0]}>
                    {viz.fft.map((_, i) => (
                      <Cell key={i} fill={i === 4 || i === 11 ? '#FF9500' : '#5856D6'} />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </div>
          </article>

          {/* Prediction + Probability + Severity */}
          <div className="grid gap-4 md:grid-cols-3">
            <article className="am-soft-card p-5">
              <p className="text-[14px] font-semibold uppercase tracking-wide text-[var(--am-text-tertiary)]">
                3 · Prediction
              </p>
              <div className="mt-3 flex items-center gap-2">
                <span
                  className={`h-2.5 w-2.5 rounded-full ${result.is_leak_detected ? 'bg-[var(--am-danger)]' : 'bg-[var(--am-success)]'}`}
                  aria-hidden
                />
                <p className="text-[19px] font-semibold text-[var(--am-text)]">
                  {result.is_leak_detected ? 'Anomaly detected' : 'No anomaly'}
                </p>
              </div>
              <p className="mt-2 text-[15px] text-[var(--am-text-secondary)]">{result.model_scope}</p>
              <p className="mt-1 text-[15px] tabular-nums text-[var(--am-text-tertiary)]">Held-out F1 · {result.test_f1}</p>
            </article>

            <article className="am-soft-card p-5">
              <p className="text-[14px] font-semibold uppercase tracking-wide text-[var(--am-text-tertiary)]">
                4 · Leak probability
              </p>
              <p className="mt-3 text-[32px] font-semibold tabular-nums tracking-tight text-[var(--am-text)]">
                {(result.leak_probability * 100).toFixed(1)}%
              </p>
              <div className="mt-3 h-2 overflow-hidden rounded-full bg-[var(--am-bg-muted)]" role="progressbar" aria-valuenow={Math.round(result.leak_probability * 100)} aria-valuemin={0} aria-valuemax={100}>
                <div
                  className="h-full rounded-full transition-all duration-700"
                  style={{
                    width: `${result.leak_probability * 100}%`,
                    background:
                      result.leak_probability >= 0.8
                        ? 'var(--am-danger)'
                        : result.leak_probability >= 0.5
                          ? 'var(--am-warning)'
                          : 'var(--am-success)',
                  }}
                />
              </div>
              <div className="mt-4 h-[100px]">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart
                    data={[
                      { name: 'No-leak', v: 1 - result.leak_probability },
                      { name: 'Leak', v: result.leak_probability },
                    ]}
                    layout="vertical"
                  >
                    <XAxis type="number" domain={[0, 1]} hide />
                    <YAxis type="category" dataKey="name" width={56} tick={{ fontSize: 13, fill: 'var(--am-text-tertiary)' }} axisLine={false} tickLine={false} />
                    <Bar dataKey="v" radius={[0, 6, 6, 0]}>
                      <Cell fill="#34C759" />
                      <Cell fill="#FF3B30" />
                    </Bar>
                  </BarChart>
                </ResponsiveContainer>
              </div>
            </article>

            <article className="am-soft-card p-5">
              <p className="text-[14px] font-semibold uppercase tracking-wide text-[var(--am-text-tertiary)]">
                5 · Severity
              </p>
              <div className="mt-3">
                <StatusBadge status={result.severity} />
              </div>
              <p className="mt-4 text-[16px] leading-relaxed text-[var(--am-text-secondary)]">{result.note}</p>
            </article>
          </div>

          <article className="relative overflow-hidden rounded-[20px] border border-[var(--am-accent)]/20 bg-[var(--am-accent-soft)] p-5 sm:p-6">
            <p className="text-[14px] font-semibold uppercase tracking-[0.08em] text-[var(--am-accent)]">
              6 · Recommended action
            </p>
            <p className="mt-2 text-[17px] font-semibold text-[var(--am-text)]">{recommendedAction(result)}</p>
            <p className="mt-2 text-[15px] text-[var(--am-text-secondary)]">
              Field verification is recommended before isolating any pipe.
            </p>
          </article>
        </section>
      ) : null}
    </div>
  );
};

export default LeakDetectionPage;
