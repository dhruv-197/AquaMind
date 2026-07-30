import React from 'react';
import { LineChart } from 'lucide-react';
import type { HorizonState } from './types';
import { PRESETS } from './types';

type Props = {
  horizon: HorizonState;
  onChange: (next: HorizonState) => void;
  onPredict: () => void;
  onPreset: (next: HorizonState) => void;
  predicting: boolean;
  disabled?: boolean;
};

/** Single control row. Horizon presets (max 7 days) + predict. */
export const ForecastControls: React.FC<Props> = ({
  horizon,
  onPredict,
  onPreset,
  predicting,
  disabled,
}) => {
  return (
    <section className="am-soft-card px-5 py-4">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h2 className="text-[17px] font-semibold text-[var(--am-text)]">Forecast Range</h2>
          <p className="mt-0.5 text-[15px] text-[var(--am-text-secondary)]">
            Choose how far ahead to look (up to 7 days)
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          {PRESETS.map((p) => {
            const active = horizon.unit === p.unit && horizon.value === p.value;
            return (
              <button
                key={p.label}
                type="button"
                onClick={() => onPreset({ unit: p.unit, value: p.value })}
                className={`rounded-[12px] px-3.5 py-2 text-[16px] font-semibold transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--am-accent)] ${
                  active
                    ? 'bg-[var(--am-accent)] text-white'
                    : 'bg-[var(--am-bg-muted)] text-[var(--am-text)] hover:bg-[var(--am-bg-hover)]'
                }`}
              >
                {p.label}
              </button>
            );
          })}
          <button
            type="button"
            disabled={disabled || predicting}
            onClick={onPredict}
            className="inline-flex items-center gap-2 rounded-[12px] bg-[var(--am-accent)] px-4 py-2 text-[16px] font-semibold text-white shadow-[var(--am-shadow-sm)] hover:bg-[var(--am-accent-hover)] disabled:opacity-40"
          >
            <LineChart className="h-4 w-4" />
            {predicting ? 'Running…' : 'Predict'}
          </button>
        </div>
      </div>
    </section>
  );
};
