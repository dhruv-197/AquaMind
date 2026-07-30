import React from 'react';
import { GlassCard } from '../common/GlassCard';
import { Cpu, CheckCircle2 } from 'lucide-react';

export const AiEngineTab: React.FC = () => {
  const models = [
    {
      name: 'Water Demand Forecast',
      focus: 'City demand outlook',
      accuracy: 'High forecast fit',
      purpose: 'Projects municipal demand from climate and calendar patterns.',
      status: 'Ready',
    },
    {
      name: 'Reservoir Level Forecast',
      focus: 'Storage outlook',
      accuracy: 'Tight storage fit',
      purpose: 'Projects reservoir levels with rainfall, inflow, and temperature drivers.',
      status: 'Ready',
    },
    {
      name: 'Water Stress Intelligence',
      focus: 'Fused risk score',
      accuracy: 'Multi-model fusion',
      purpose: 'Combines demand, storage, and climate into a 0-100 regional stress index.',
      status: 'Ready',
    },
    {
      name: 'Decision Optimization',
      focus: 'Action ranking',
      accuracy: 'Impact-scored plans',
      purpose: 'Ranks interventions from prediction outputs for operators and planners.',
      status: 'Ready',
    },
  ];

  return (
    <div className="space-y-6">
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 bg-slate-900/40 border border-slate-800/80 rounded-2xl p-5 backdrop-blur-xl">
        <div>
          <div className="flex items-center gap-2">
            <Cpu className="w-6 h-6 text-cyan-400" />
            <h1 className="text-xl md:text-2xl font-bold tracking-tight text-white">Supporting intelligence</h1>
          </div>
          <p className="text-[14px] text-slate-400 mt-1">
            Trusted forecasts that quietly power the action plan above.
          </p>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {models.map((model) => (
          <GlassCard key={model.name}>
            <div className="flex items-start justify-between gap-3">
              <div>
                <h2 className="text-[15px] font-bold text-white">{model.name}</h2>
                <p className="text-[14px] text-cyan-300 mt-1">{model.focus}</p>
              </div>
              <CheckCircle2 className="w-4 h-4 text-emerald-400 shrink-0" />
            </div>
            <p className="text-[14px] text-slate-400 mt-3 leading-relaxed">{model.purpose}</p>
            <div className="mt-3 flex flex-wrap gap-2">
              <span className="status-chip-muted text-[16px] px-2 py-1 rounded font-semibold border">
                {model.accuracy}
              </span>
              <span className="status-chip-active text-[16px] px-2 py-1 rounded font-semibold border">
                {model.status}
              </span>
            </div>
          </GlassCard>
        ))}
      </div>
    </div>
  );
};
