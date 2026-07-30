import React from 'react';
import {
  AlertTriangle,
  CheckCircle2,
  Info,
  TrendingDown,
  TrendingUp,
} from 'lucide-react';

type Props = {
  insights?: string[] | null;
  warning?: string | null;
};

function iconFor(text: string) {
  const t = text.toLowerCase();
  if (t.includes('warning') || t.includes('exceeds') || t.includes('degraded')) {
    return <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-amber-500" />;
  }
  if (t.includes('no high') || t.includes('none')) {
    return <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0 text-emerald-500" />;
  }
  if (t.includes('decrease') || t.includes('decline')) {
    return <TrendingDown className="mt-0.5 h-4 w-4 shrink-0 text-sky-500" />;
  }
  if (t.includes('increase') || t.includes('peak') || t.includes('utilisation') || t.includes('utilization')) {
    return <TrendingUp className="mt-0.5 h-4 w-4 shrink-0 text-blue-500" />;
  }
  return <Info className="mt-0.5 h-4 w-4 shrink-0 text-slate-400" />;
}

export const ForecastInsights: React.FC<Props> = ({ insights, warning }) => {
  const items = insights?.length ? insights : ['Run a forecast to generate AI insights.'];
  return (
    <section className="flex h-full flex-col rounded-xl border border-slate-200 bg-white shadow-sm dark:border-slate-700 dark:bg-slate-950">
      <header className="border-b border-slate-100 px-4 py-3 dark:border-slate-800">
        <h3 className="text-[15px] font-semibold text-slate-900 dark:text-slate-100">AI insights</h3>
        <p className="mt-0.5 text-[14px] text-slate-500">Generated from the active prediction</p>
      </header>
      {warning ? (
        <div className="flex gap-2 border-b border-amber-100 bg-amber-50 px-4 py-2.5 text-[14px] text-amber-900 dark:border-amber-900/40 dark:bg-amber-950/30 dark:text-amber-100">
          <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" />
          <span>{warning}</span>
        </div>
      ) : null}
      <ul className="flex-1 space-y-3 px-4 py-3">
        {items.map((text, i) => (
          <li key={`${i}-${text.slice(0, 24)}`} className="flex gap-2.5 text-[16px] leading-relaxed text-slate-700 dark:text-slate-300">
            {iconFor(text)}
            <span>{text}</span>
          </li>
        ))}
      </ul>
    </section>
  );
};
