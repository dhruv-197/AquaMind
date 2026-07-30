import React from 'react';
import type { ForecastModelInfo } from './types';

type Props = {
  model?: ForecastModelInfo | null;
};

/** Model metadata panel (health). */
export const ForecastMetrics: React.FC<Props> = ({ model }) => {
  return (
    <section className="flex h-full flex-col rounded-xl border border-slate-200 bg-white shadow-sm dark:border-slate-700 dark:bg-slate-950">
      <header className="border-b border-slate-100 px-4 py-3 dark:border-slate-800">
        <h3 className="text-[15px] font-semibold text-slate-900 dark:text-slate-100">Model health</h3>
      </header>
      <div className="flex-1 p-4">
        <table className="w-full text-left text-[14px]">
          <tbody className="divide-y divide-slate-100 dark:divide-slate-800">
            {[
              ['Version', model?.model_version || '-'],
              ['Backend', model?.backend || 'xgboost'],
              [
                'Last trained',
                model?.last_trained_at
                  ? new Date(model.last_trained_at).toLocaleString()
                  : '-',
              ],
              [
                'Dataset size',
                model?.training_dataset_size != null
                  ? `${model.training_dataset_size.toLocaleString()} rows`
                  : '-',
              ],
            ].map(([k, v]) => (
              <tr key={k}>
                <th className="py-2.5 pr-3 font-medium text-slate-500">{k}</th>
                <td className="py-2.5 text-right font-mono text-slate-800 dark:text-slate-200">{v}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
};
