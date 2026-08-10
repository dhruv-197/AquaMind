import React, { useState } from 'react';
import { Lightbulb, X, Check, Copy, Download, ShieldCheck, AlertTriangle, Radio } from 'lucide-react';
import type { ExecutiveBriefing } from '../../types/apiContracts';

interface AIExecutiveReportModalProps {
  isOpen: boolean;
  onClose: () => void;
  reportData: ExecutiveBriefing | null;
  isLoading: boolean;
  onRegenerate: () => void;
}

export const AIExecutiveReportModal: React.FC<AIExecutiveReportModalProps> = ({
  isOpen,
  onClose,
  reportData,
  isLoading,
  onRegenerate,
}) => {
  const [copied, setCopied] = useState(false);

  if (!isOpen) return null;

  const handleCopy = () => {
    if (reportData) {
      navigator.clipboard.writeText(JSON.stringify(reportData, null, 2));
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 sm:p-6 bg-slate-950/80 backdrop-blur-xl animate-fade-in">
      <div className="relative w-full max-w-3xl max-h-[90vh] flex flex-col rounded-2xl bg-slate-900 border border-cyan-500/30 shadow-[0_0_50px_rgba(6,182,212,0.2)] overflow-hidden">
        {/* Modal Top Bar */}
        <div className="px-6 py-4 border-b border-slate-800/80 bg-slate-950/80 flex items-center justify-between">
          <div className="flex items-center gap-2.5">
            <div className="p-2 rounded-xl bg-cyan-500/20 border border-cyan-500/40 text-cyan-300">
              <Lightbulb className="w-5 h-5 animate-pulse" />
            </div>
            <div>
              <h2 className="text-base font-bold text-white tracking-tight">
                Water Intelligence Briefing
              </h2>
              <p className="text-[14px] text-cyan-400">
                Priority actions for your operations team
              </p>
            </div>
          </div>

          <button
            onClick={onClose}
            className="p-1.5 rounded-lg text-slate-400 hover:text-white hover:bg-slate-800 transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Modal Content Scroll Area */}
        <div className="p-6 overflow-y-auto space-y-6 flex-1 text-[14px]">
          {isLoading ? (
            <div className="py-16 flex flex-col items-center justify-center space-y-4">
              <div className="relative w-12 h-12 flex items-center justify-center">
                <div className="absolute inset-0 rounded-full border-2 border-cyan-500/20 border-t-cyan-400 animate-spin" />
                <Lightbulb className="w-5 h-5 text-cyan-400" />
              </div>
              <p className="text-cyan-300 animate-pulse text-[14px]">
                Preparing your executive briefing...
              </p>
            </div>
          ) : reportData ? (
            <>
              {/* Executive Summary Header */}
              <div className="p-4 rounded-xl bg-slate-950 border border-slate-800/80 space-y-2">
                <span className="text-[16px] font-mono uppercase text-cyan-400 font-bold tracking-wider">
                  Executive Briefing Overview
                </span>
                <h3 className="text-[15px] font-bold text-white">{reportData.title || 'AquaMind AI Executive Water Briefing'}</h3>
                <p className="text-[14px] text-slate-300 leading-relaxed font-sans">{reportData.summary}</p>
              </div>

              {/* Key Findings */}
              {reportData.keyFindings && (
                <div className="space-y-2">
                  <h4 className="text-[14px] font-bold text-slate-200 uppercase font-mono tracking-wider flex items-center gap-1.5">
                    <ShieldCheck className="w-4 h-4 text-cyan-400" />
                    Critical findings
                  </h4>
                  <ul className="space-y-2 font-sans">
                    {reportData.keyFindings.map((finding: string, idx: number) => (
                      <li key={idx} className="p-3 rounded-xl bg-slate-950/60 border border-slate-800/80 text-slate-200 leading-relaxed flex items-start gap-2.5">
                        <span className="w-1.5 h-1.5 rounded-full bg-cyan-400 mt-1.5 shrink-0" />
                        <span>{finding}</span>
                      </li>
                    ))}
                  </ul>
                </div>
              )}

              {/* Action Plan */}
              {reportData.actionPlan && (
                <div className="space-y-2">
                  <h4 className="text-[14px] font-bold text-slate-200 uppercase font-mono tracking-wider flex items-center gap-1.5">
                    <AlertTriangle className="w-4 h-4 text-amber-400" />
                    Immediate Operational Action Plan
                  </h4>
                  <ul className="space-y-2 font-sans">
                    {reportData.actionPlan.map((action: string, idx: number) => (
                      <li key={idx} className="p-3 rounded-xl bg-slate-950/60 border border-amber-500/20 text-slate-200 leading-relaxed flex items-start gap-2.5">
                        <span className="text-amber-400 font-mono font-bold text-[14px]">{idx + 1}.</span>
                        <span>{action}</span>
                      </li>
                    ))}
                  </ul>
                </div>
              )}
            </>
          ) : (
            <div className="text-center py-12 text-slate-400">No report available. Click synthesize to generate.</div>
          )}
        </div>

        {/* Modal Footer Controls */}
        <div className="px-6 py-4 border-t border-slate-800/80 bg-slate-950/80 flex items-center justify-between">
          <button
            onClick={onRegenerate}
            disabled={isLoading}
            className="px-3.5 py-2 rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-200 text-[14px] font-semibold flex items-center gap-1.5 transition-colors"
          >
            <Radio className="w-3.5 h-3.5 text-cyan-400" />
            Re-synthesize Live
          </button>

          <div className="flex items-center gap-2">
            <button
              onClick={handleCopy}
              className="px-3.5 py-2 rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-200 text-[14px] font-semibold flex items-center gap-1.5 transition-colors"
            >
              {copied ? <Check className="w-3.5 h-3.5 text-emerald-400" /> : <Copy className="w-3.5 h-3.5" />}
              {copied ? 'Copied JSON' : 'Copy JSON'}
            </button>
            <button
              onClick={onClose}
              className="px-4 py-2 rounded-xl bg-cyan-500 hover:bg-cyan-400 text-slate-950 font-bold text-[14px] transition-colors"
            >
              Done
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};
