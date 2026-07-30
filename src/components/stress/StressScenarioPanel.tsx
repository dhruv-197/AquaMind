import React from 'react';
import type { StressScenario } from './types';
import { Button } from '../ui/Button';

type Props = {
  scenario: StressScenario;
  onChange: (next: StressScenario) => void;
  onSimulate: () => void;
  onReset: () => void;
  presets?: { id: string; label: string; scenario: StressScenario }[];
  onPreset: (id: string) => void;
  busy?: boolean;
  deltaVsBaseline?: number | null;
};

function Slider({
  label,
  value,
  min,
  max,
  step,
  suffix,
  onChange,
}: {
  label: string;
  value: number;
  min: number;
  max: number;
  step: number;
  suffix: string;
  onChange: (v: number) => void;
}) {
  const id = `stress-slider-${label.replace(/\s+/g, '-').toLowerCase()}`;
  return (
    <label className="block" htmlFor={id}>
      <div className="mb-2 flex items-center justify-between text-[15px]">
        <span className="font-medium text-[var(--am-text-secondary)]">{label}</span>
        <span className="tabular-nums font-semibold text-[var(--am-text)]">
          {value > 0 ? '+' : ''}
          {value}
          {suffix}
        </span>
      </div>
      <input
        id={id}
        type="range"
        min={min}
        max={max}
        step={step}
        value={value}
        onChange={(e) => onChange(Number(e.target.value))}
        className="am-range w-full"
        aria-valuemin={min}
        aria-valuemax={max}
        aria-valuenow={value}
      />
    </label>
  );
}

export const StressScenarioPanel: React.FC<Props> = ({
  scenario,
  onChange,
  onSimulate,
  onReset,
  presets,
  onPreset,
  busy,
  deltaVsBaseline,
}) => {
  const set = (key: keyof StressScenario, value: number) => onChange({ ...scenario, [key]: value });

  return (
    <section className="flex h-full flex-col rounded-[20px] border border-[var(--am-border)] bg-[var(--am-bg-elevated)] shadow-[var(--am-shadow-md)]">
      <header className="border-b border-[var(--am-divider)] px-5 py-4">
        <h3 className="text-[17px] font-semibold text-[var(--am-text)]">Scenario simulation</h3>
        <p className="mt-0.5 text-[15px] text-[var(--am-text-secondary)]">
          Premium what-if controls. Re-fuses upstream forecasts
        </p>
      </header>

      <div className="space-y-5 p-5">
        <Slider label="Rainfall change" value={scenario.rainfall_delta_pct ?? 0} min={-50} max={50} step={1} suffix="%" onChange={(v) => set('rainfall_delta_pct', v)} />
        <Slider label="Population change" value={scenario.population_delta_pct ?? 0} min={-20} max={50} step={1} suffix="%" onChange={(v) => set('population_delta_pct', v)} />
        <Slider label="Demand change" value={scenario.demand_delta_pct ?? 0} min={-30} max={50} step={1} suffix="%" onChange={(v) => set('demand_delta_pct', v)} />
        <Slider label="Temperature change" value={scenario.temperature_delta_c ?? 0} min={-5} max={8} step={0.5} suffix="°C" onChange={(v) => set('temperature_delta_c', v)} />
        <Slider label="Reservoir storage change" value={scenario.reservoir_delta_pct ?? 0} min={-40} max={40} step={1} suffix=" pp" onChange={(v) => set('reservoir_delta_pct', v)} />
        <Slider label="Reservoir absolute level" value={scenario.reservoir_level_pct ?? 50} min={5} max={95} step={1} suffix="%" onChange={(v) => set('reservoir_level_pct', v)} />
      </div>

      {presets && presets.length > 0 ? (
        <div className="border-t border-[var(--am-divider)] px-5 py-4">
          <p className="mb-2 text-[16px] font-semibold uppercase tracking-wide text-[var(--am-text-tertiary)]">
            What-if presets
          </p>
          <div className="flex flex-col gap-1.5">
            {presets.map((p) => (
              <button
                key={p.id}
                type="button"
                onClick={() => onPreset(p.id)}
                disabled={busy}
                className="rounded-[12px] border border-[var(--am-border)] bg-[var(--am-bg-muted)]/50 px-3 py-2.5 text-left text-[15px] font-medium text-[var(--am-text)] transition hover:bg-[var(--am-bg-hover)] disabled:opacity-40 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--am-accent)]"
              >
                {p.label}
              </button>
            ))}
          </div>
        </div>
      ) : null}

      <div className="mt-auto space-y-2 border-t border-[var(--am-divider)] px-5 py-4">
        {deltaVsBaseline != null ? (
          <p className="text-[15px] text-[var(--am-text-secondary)]">
            Δ vs baseline:{' '}
            <span className="tabular-nums font-semibold text-[var(--am-text)]">
              {deltaVsBaseline >= 0 ? '+' : ''}
              {deltaVsBaseline.toFixed(1)} WSI
            </span>
          </p>
        ) : null}
        <div className="flex gap-2">
          <Button className="flex-1" onClick={onSimulate} loading={busy}>
            Run scenario
          </Button>
          <Button variant="secondary" onClick={onReset} disabled={busy}>
            Reset
          </Button>
        </div>
      </div>
    </section>
  );
};
