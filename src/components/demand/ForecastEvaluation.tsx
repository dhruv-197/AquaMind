import React from 'react';

type Props = {
  metrics?: Record<string, number | null | undefined> | null;
};

function fmt(n: number | null | undefined, digits = 3): string {
  if (n == null || Number.isNaN(Number(n))) return '-';
  return Number(n).toFixed(digits);
}

/** Evaluation metrics panel. */
export const ForecastEvaluation: React.FC<Props> = ({ metrics }) => {
  return (
    <section className="flex h-full flex-col rounded-xl border border-slate-200 bg-white shadow-sm dark:border-slate-700 dark:bg-slate-950">
      <header className="border-b border-slate-100 px-4 py-3 dark:border-slate-800">
        <h3 className="text-[15px] font-semibold text-slate-900 dark:text-slate-100">Evaluation</h3>
        <p className="mt-0.5 text-[14px] text-slate-500">Holdout validation scores</p>
      </header>
      <div className="grid flex-1 grid-cols-2 gap-2.5 p-4">
        {[
          ['MAE', fmt(metrics?.mae, 2), 'MGD'],
          ['RMSE', fmt(metrics?.rmse, 2), 'MGD'],
          ['MAPE', metrics?.mape != null ? Number(metrics.mape).toFixed(2) : '-', '%'],
          ['R²', fmt(metrics?.r2, 3), ''],
        ].map(([k, v, unit]) => (
          <div
            key={k}
            className="rounded-lg border border-slate-200 bg-slate-50/70 px-3 py-3 dark:border-slate-700 dark:bg-slate-900/40"
          >
            <p className="text-[16px] font-semibold uppercase tracking-wide text-slate-500">{k}</p>
            <p className="mt-1.5 font-mono text-xl font-semibold text-slate-900 dark:text-slate-50">
              {v}
              {unit ? <span className="ml-1 text-[14px] font-normal text-slate-400">{unit}</span> : null}
            </p>
          </div>
        ))}
      </div>
    </section>
  );
};
