import React from 'react';
import { Button } from '../../ui/Button';
import { SectionTitle } from './ExecutiveKpis';
import type { ScenarioState } from './derive';

type Props = {
  scenario: ScenarioState;
  onChange: (next: ScenarioState) => void;
  onApply: () => void;
  onReset: () => void;
  simulating?: boolean;
  resultHint?: string | null;
};

function Slider({
  label,
  value,
  min,
  max,
  step,
  unit,
  onChange,
}: {
  label: string;
  value: number;
  min: number;
  max: number;
  step: number;
  unit: string;
  onChange: (v: number) => void;
}) {
  return (
    <label className="block rounded-[14px] bg-[var(--am-bg-muted)] p-3.5">
      <div className="mb-2 flex items-center justify-between gap-2">
        <span className="text-[16px] font-semibold text-[var(--am-text)]">{label}</span>
        <span className="text-[16px] tabular-nums text-[var(--am-accent)]">
          {value > 0 ? '+' : ''}
          {value}
          {unit}
        </span>
      </div>
      <input
        type="range"
        min={min}
        max={max}
        step={step}
        value={value}
        onChange={(e) => onChange(Number(e.target.value))}
        className="am-range w-full"
      />
    </label>
  );
}

export const ScenarioSimulation: React.FC<Props> = ({
  scenario,
  onChange,
  onApply,
  onReset,
  simulating,
  resultHint,
}) => (
  <section
    id="scenario-simulation"
    className="rounded-[var(--am-radius-xl)] bg-[var(--am-bg-elevated)] p-5 shadow-[var(--am-shadow-md)]"
  >
    <div className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
      <SectionTitle
        title="Scenario Simulation"
        subtitle="Stress-test rainfall, demand, population, and reservoir failure. Updates KPIs and stress instantly."
      />
      <div className="flex gap-2">
        <Button variant="secondary" onClick={onReset} disabled={simulating}>
          Reset
        </Button>
        <Button onClick={onApply} disabled={simulating}>
          {simulating ? 'Simulating…' : 'Run scenario'}
        </Button>
      </div>
    </div>

    <div className="mt-4 grid grid-cols-1 gap-3 md:grid-cols-2 xl:grid-cols-3">
      <Slider
        label="Rainfall"
        value={scenario.rainfallDeltaPct}
        min={-40}
        max={40}
        step={1}
        unit="%"
        onChange={(rainfallDeltaPct) => onChange({ ...scenario, rainfallDeltaPct })}
      />
      <Slider
        label="Temperature"
        value={scenario.temperatureDeltaC}
        min={-5}
        max={8}
        step={0.5}
        unit="°C"
        onChange={(temperatureDeltaC) => onChange({ ...scenario, temperatureDeltaC })}
      />
      <Slider
        label="Demand increase"
        value={scenario.demandIncreasePct}
        min={0}
        max={40}
        step={1}
        unit="%"
        onChange={(demandIncreasePct) => onChange({ ...scenario, demandIncreasePct })}
      />
      <Slider
        label="Population growth"
        value={scenario.populationGrowthPct}
        min={0}
        max={20}
        step={1}
        unit="%"
        onChange={(populationGrowthPct) => onChange({ ...scenario, populationGrowthPct })}
      />
      <label className="flex items-center justify-between gap-3 rounded-[14px] bg-[var(--am-bg-muted)] p-3.5 md:col-span-2 xl:col-span-1">
        <div>
          <p className="text-[16px] font-semibold text-[var(--am-text)]">Reservoir failure</p>
          <p className="mt-0.5 text-[15px] text-[var(--am-text-secondary)]">
            Simulate abrupt storage collapse on primary asset
          </p>
        </div>
        <input
          type="checkbox"
          checked={scenario.reservoirFailure}
          onChange={(e) => onChange({ ...scenario, reservoirFailure: e.target.checked })}
          className="h-5 w-5 accent-[var(--am-danger)]"
        />
      </label>
    </div>

    {resultHint ? (
      <p className="mt-4 rounded-[14px] bg-[var(--am-accent-soft)] px-4 py-3 text-[16px] text-[var(--am-accent)]">
        {resultHint}
      </p>
    ) : null}
  </section>
);
