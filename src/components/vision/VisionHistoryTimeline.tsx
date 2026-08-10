import React, { useMemo } from 'react';

export type VisionHistoryItem = {
  id: string;
  asset_label?: string | null;
  vision_mode?: string | null;
  provider?: string | null;
  reservoir_health?: number | null;
  overall_risk?: string | null;
  turbidity_index?: number | null;
  algae_bloom_risk?: string | null;
  shoreline_exposure_pct?: number | null;
  confidence?: number | null;
  analyzed_at?: string | null;
};

type Props = {
  assetLabel?: string | null;
  visionMode?: string | null;
  history: VisionHistoryItem[];
  loading?: boolean;
  error?: string | null;
  /** When true, timeline lists recent scans without requiring a site label. */
  showAllScans?: boolean;
};

function formatWhen(iso?: string | null) {
  if (!iso) return '—';
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleString(undefined, {
    year: 'numeric',
    month: 'short',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  });
}

function fingerprint(row: VisionHistoryItem): string {
  const minute = row.analyzed_at ? row.analyzed_at.slice(0, 16) : '';
  return [
    row.vision_mode || '',
    row.asset_label || '',
    minute,
    row.reservoir_health ?? '',
    row.overall_risk ?? '',
    row.shoreline_exposure_pct ?? '',
    row.confidence ?? '',
  ].join('|');
}

/** Drop exact-id dupes and near-identical consecutive uploads (double-submit). */
export function dedupeVisionHistory(rows: VisionHistoryItem[]): VisionHistoryItem[] {
  const byId = new Map<string, VisionHistoryItem>();
  for (const row of rows) {
    if (!row?.id) continue;
    if (!byId.has(row.id)) byId.set(row.id, row);
  }
  const unique = Array.from(byId.values()).sort((a, b) => {
    const ta = a.analyzed_at ? Date.parse(a.analyzed_at) : 0;
    const tb = b.analyzed_at ? Date.parse(b.analyzed_at) : 0;
    return tb - ta;
  });

  const out: VisionHistoryItem[] = [];
  const seenPrints = new Set<string>();
  for (const row of unique) {
    const print = fingerprint(row);
    if (seenPrints.has(print)) continue;
    seenPrints.add(print);
    out.push(row);
  }
  return out;
}

export const VisionHistoryTimeline: React.FC<Props> = ({
  assetLabel,
  visionMode,
  history,
  loading,
  error,
  showAllScans = false,
}) => {
  const rows = useMemo(() => dedupeVisionHistory(history || []), [history]);

  return (
    <section className="am-soft-card" aria-labelledby="aqualens-history-heading">
      <header className="border-b border-[var(--am-divider)] px-5 py-4">
        <h3 id="aqualens-history-heading" className="text-[17px] font-semibold text-[var(--am-text)]">
          Recent scan timeline
        </h3>
        <p className="mt-1 text-[15px] text-[var(--am-text-secondary)]">
          {assetLabel
            ? `Prior scans for “${assetLabel}”${visionMode ? ` · ${visionMode} mode` : ''}`
            : showAllScans
              ? `Your recent AquaLens scans${visionMode ? ` · ${visionMode} mode` : ''}`
              : 'Site-tagged history is unavailable for this view.'}
        </p>
      </header>

      <div className="p-5">
        {loading ? (
          <p className="text-[15px] text-[var(--am-text-tertiary)]" role="status" aria-live="polite">
            Loading scan history…
          </p>
        ) : null}
        {error ? (
          <p className="text-[15px] text-[var(--am-danger)]" role="alert">
            {error}
          </p>
        ) : null}
        {!loading && !error && !assetLabel && !showAllScans ? (
          <p className="text-[15px] text-[var(--am-text-tertiary)]">
            Timeline stays empty until a site label is set — AquaLens will not compare unrelated images.
          </p>
        ) : null}
        {!loading && !error && (assetLabel || showAllScans) && rows.length === 0 ? (
          <p className="text-[15px] text-[var(--am-text-tertiary)]">
            No prior scans yet. Upload an image to start the timeline.
          </p>
        ) : null}
        {rows.length > 0 ? (
          <ol className="relative space-y-4 border-l border-[var(--am-border)] pl-4">
            {rows.map((row) => (
              <li key={row.id} className="relative">
                <span
                  className="absolute -left-[1.3rem] top-1.5 h-2.5 w-2.5 rounded-full bg-[var(--am-accent)]"
                  aria-hidden
                />
                <div className="rounded-[12px] border border-[var(--am-border)] bg-[var(--am-bg-muted)]/50 px-3 py-2.5">
                  <div className="flex flex-wrap items-baseline justify-between gap-2">
                    <p className="text-[15px] font-semibold text-[var(--am-text)]">
                      {formatWhen(row.analyzed_at)}
                    </p>
                    <p className="text-[14px] tabular-nums text-[var(--am-text-secondary)]">
                      Confidence:{' '}
                      {row.confidence != null
                        ? `${Math.round(Number(row.confidence) * (row.confidence <= 1 ? 100 : 1))}%`
                        : '—'}
                    </p>
                  </div>
                  <p className="mt-1 text-[14px] text-[var(--am-text-secondary)]">
                    Health: {row.reservoir_health != null ? row.reservoir_health : '—'}
                    {row.overall_risk ? ` · Risk: ${row.overall_risk}` : ''}
                    {row.shoreline_exposure_pct != null
                      ? ` · Shoreline: ${Number(row.shoreline_exposure_pct).toFixed(0)}%`
                      : ''}
                  </p>
                </div>
              </li>
            ))}
          </ol>
        ) : null}
      </div>
    </section>
  );
};
