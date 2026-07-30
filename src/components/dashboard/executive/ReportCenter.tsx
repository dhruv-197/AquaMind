import React, { useEffect, useState } from 'react';
import { Download, FileText } from 'lucide-react';
import { Button } from '../../ui/Button';
import { SectionTitle } from './ExecutiveKpis';
import { loadReports } from '../../../services/telemetry';

type Props = {
  onGenerateReport: () => void;
  onExportPdf: () => void;
  onExportCsv: () => void;
};

export const ReportCenter: React.FC<Props> = ({ onGenerateReport, onExportPdf, onExportCsv }) => {
  const [reports, setReports] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const data = await loadReports();
        if (!cancelled) setReports(data.reports || []);
      } catch (err) {
        if (!cancelled) setError(err instanceof Error ? err.message : 'Could not load reports');
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  return (
    <section className="am-soft-card p-5 sm:p-6">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
        <SectionTitle
          title="Report Center"
          subtitle="Executive briefings, CSV extracts, and recent published reports."
        />
        <div className="flex flex-wrap gap-2">
          <Button icon={<FileText className="h-4 w-4" />} onClick={onGenerateReport}>
            Generate report
          </Button>
          <Button variant="secondary" icon={<Download className="h-4 w-4" />} onClick={onExportPdf}>
            Download PDF
          </Button>
          <Button variant="tertiary" onClick={onExportCsv}>
            Export CSV
          </Button>
        </div>
      </div>

      <div className="mt-5 space-y-2.5">
        {loading ? <p className="text-[16px] text-[var(--am-text-secondary)]">Loading reports…</p> : null}
        {error ? <p className="text-[16px] text-[var(--am-warning)]">{error}</p> : null}
        {!loading && reports.length === 0 ? (
          <p className="rounded-[16px] bg-[var(--am-bg-muted)] p-5 text-[16px] leading-relaxed text-[var(--am-text-secondary)]">
            No published reports yet. Generate an executive briefing to start the library.
          </p>
        ) : null}
        {reports.slice(0, 6).map((r) => (
          <article
            key={r.id}
            className="rounded-[16px] border border-[var(--am-border)] bg-[var(--am-bg-muted)]/70 p-4 transition hover:shadow-[var(--am-shadow-sm)]"
          >
            <div className="flex items-start justify-between gap-3">
              <div className="min-w-0">
                <p className="truncate text-[17px] font-semibold tracking-tight text-[var(--am-text)]">{r.title}</p>
                <p className="mt-1.5 line-clamp-2 text-[16px] leading-relaxed text-[var(--am-text-secondary)]">{r.summary}</p>
              </div>
              <span className="shrink-0 rounded-full bg-[var(--am-accent-soft)] px-2.5 py-0.5 text-[16px] font-semibold uppercase tracking-wide text-[var(--am-accent)]">
                {r.category || 'brief'}
              </span>
            </div>
          </article>
        ))}
      </div>
    </section>
  );
};
