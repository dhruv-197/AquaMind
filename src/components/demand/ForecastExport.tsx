import React from 'react';
import type { SeriesPoint } from './types';
import { downloadText, exportChartPng, seriesToCsv } from './utils';
import { useToast } from '../ui/Toast';

type Props = {
  series: SeriesPoint[];
  chartContainerRef: React.RefObject<HTMLDivElement | null>;
  filePrefix?: string;
};

export const ForecastExport: React.FC<Props> = ({
  series,
  chartContainerRef,
  filePrefix = 'demand-forecast',
}) => {
  const { toast } = useToast();
  const stamp = new Date().toISOString().slice(0, 10);
  const btn =
    'min-h-9 rounded-lg border border-slate-200 bg-white px-3 py-1.5 text-[14px] font-medium text-slate-700 hover:bg-slate-50 disabled:opacity-40 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--am-accent)] dark:border-slate-600 dark:bg-slate-900 dark:text-slate-200';

  const onCsv = () => {
    try {
      if (!series.length) {
        toast('No data available to export.', 'error');
        return;
      }
      downloadText(`${filePrefix}-${stamp}.csv`, seriesToCsv(series));
      toast('CSV exported successfully.');
    } catch {
      toast('CSV export failed. Please try again.', 'error');
    }
  };

  const onPng = async () => {
    try {
      if (!series.length || !chartContainerRef.current) {
        toast('No chart available to export.', 'error');
        return;
      }
      await exportChartPng(chartContainerRef.current, `${filePrefix}-${stamp}.png`);
      toast('PNG exported successfully.');
    } catch {
      toast('PNG export failed. Please try again.', 'error');
    }
  };

  return (
    <div className="flex flex-wrap items-center gap-2">
      <button type="button" disabled={!series.length} className={btn} onClick={onCsv}>
        Export CSV
      </button>
      <button
        type="button"
        disabled={!series.length}
        className={btn}
        onClick={() => void onPng()}
      >
        Export PNG
      </button>
    </div>
  );
};
