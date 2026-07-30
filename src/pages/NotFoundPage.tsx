import React from 'react';
import { Link } from 'react-router-dom';
import { AlertTriangle, ArrowLeft } from 'lucide-react';

export const NotFoundPage: React.FC = () => {
  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 flex flex-col items-center justify-center p-6 text-center selection:bg-cyan-500/30">
      <div className="p-4 rounded-2xl bg-cyan-500/10 border border-cyan-500/30 text-cyan-400 mb-4">
        <AlertTriangle className="w-10 h-10" />
      </div>
      <h1 className="text-4xl font-extrabold text-white">404 - Sensor Route Not Found</h1>
      <p className="text-[14px] text-slate-400 mt-2 max-w-sm">
        The page you requested is not available.
      </p>
      <Link to="/dashboard" className="mt-6 px-5 py-2.5 rounded-xl bg-cyan-400 text-slate-950 font-bold text-[14px] flex items-center gap-2 hover:bg-cyan-300 transition-all shadow-[0_0_20px_rgba(6,182,212,0.3)]">
        <ArrowLeft className="w-4 h-4" /> Return to Dashboard Command
      </Link>
    </div>
  );
};
