import React from 'react';
import { GlassCard } from '../components/common/GlassCard';
import { Info, Cpu } from 'lucide-react';

export const AboutPage: React.FC = () => <div className="space-y-6">
  <div className="bg-slate-900/40 border border-slate-800/80 rounded-2xl p-6 backdrop-blur-xl">
    <div className="flex items-center gap-3"><Info className="w-6 h-6 text-cyan-400" /><h1 className="text-2xl font-bold text-white">About AquaMind AI</h1></div>
    <p className="text-[14px] text-slate-400 mt-1">A unified workspace for water intelligence and decision support.</p>
  </div>
  <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
    <GlassCard glow><div className="flex items-center gap-2 text-cyan-400 font-bold text-[15px] mb-2"><Cpu className="w-4 h-4" /> Water intelligence</div><p className="text-[14px] text-slate-300 leading-relaxed">AquaMind brings reservoir monitoring, groundwater forecasting, leak detection, and demand planning into one focused workspace.</p></GlassCard>
  </div>
</div>;
