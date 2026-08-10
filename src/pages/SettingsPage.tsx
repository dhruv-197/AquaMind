import React, { useEffect, useState } from 'react';
import { GlassCard } from '../components/common/GlassCard';
import { useTheme } from '../context/ThemeContext';
import { FASTAPI_BASE } from '../config/api';
import { ReadinessPanel } from '../components/settings/ReadinessPanel';
import {
  Sliders,
  Key,
  Database,
  Server,
  Moon,
  Sun,
  CheckCircle2,
  AlertCircle,
  Loader2,
} from 'lucide-react';

const PREFS_KEY = 'aquamind-settings-prefs';

type Prefs = {
  acousticThreshold: number;
  pressureSensitivity: number;
};

type ServiceStatus = 'checking' | 'online' | 'offline';

function loadPrefs(): Prefs {
  try {
    const raw = localStorage.getItem(PREFS_KEY);
    if (!raw) return { acousticThreshold: 65, pressureSensitivity: 25 };
    const parsed = JSON.parse(raw) as Partial<Prefs>;
    return {
      acousticThreshold: Number(parsed.acousticThreshold ?? 65),
      pressureSensitivity: Number(parsed.pressureSensitivity ?? 25),
    };
  } catch {
    return { acousticThreshold: 65, pressureSensitivity: 25 };
  }
}

export const SettingsPage: React.FC = () => {
  const { isLight, theme, toggleTheme } = useTheme();
  const [prefs, setPrefs] = useState<Prefs>(() => loadPrefs());
  const [savedFlash, setSavedFlash] = useState(false);
  const [apiStatus, setApiStatus] = useState<ServiceStatus>('checking');

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const res = await fetch(`${FASTAPI_BASE}/health`, { signal: AbortSignal.timeout(4000) });
        if (!cancelled) setApiStatus(res.ok ? 'online' : 'offline');
      } catch {
        if (!cancelled) setApiStatus('offline');
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  const updatePref = <K extends keyof Prefs>(key: K, value: Prefs[K]) => {
    setPrefs((prev) => {
      const next = { ...prev, [key]: value };
      localStorage.setItem(PREFS_KEY, JSON.stringify(next));
      setSavedFlash(true);
      window.setTimeout(() => setSavedFlash(false), 1200);
      return next;
    });
  };

  const panel = isLight
    ? 'bg-white border border-slate-200 shadow-sm'
    : 'bg-slate-900/40 border border-slate-800/80 backdrop-blur-xl';
  const title = isLight ? 'text-slate-900' : 'text-white';
  const muted = isLight ? 'text-slate-500' : 'text-slate-400';
  const label = isLight ? 'text-slate-700' : 'text-slate-300';
  const monoRow = isLight
    ? 'bg-slate-50 border border-slate-200 text-slate-700'
    : 'bg-slate-900 border border-slate-800 text-slate-300';

  const statusPill = (status: ServiceStatus | 'local') => {
    if (status === 'checking') {
      return (
        <span className={`inline-flex items-center gap-1 font-bold ${muted}`}>
          <Loader2 className="w-3 h-3 animate-spin" /> Checking
        </span>
      );
    }
    if (status === 'online' || status === 'local') {
      return (
        <span
          className={`inline-flex items-center gap-1 font-bold ${
            isLight ? 'text-emerald-700' : 'text-emerald-400'
          }`}
        >
          <CheckCircle2 className="w-3.5 h-3.5" />
          {status === 'local' ? 'Local session' : 'Online'}
        </span>
      );
    }
    return (
      <span
        className={`inline-flex items-center gap-1 font-bold ${
          isLight ? 'text-amber-700' : 'text-amber-300'
        }`}
      >
        <AlertCircle className="w-3.5 h-3.5" /> Offline
      </span>
    );
  };

  return (
    <div className="space-y-6">
      <div className={`rounded-2xl p-6 ${panel}`}>
        <div className="flex flex-wrap items-center gap-2 mb-1">
          <h1 className={`text-2xl font-bold ${title}`}>Platform settings</h1>
          {savedFlash && (
            <span
              className={`text-[16px] font-mono uppercase px-2 py-0.5 rounded border ${
                isLight
                  ? 'bg-emerald-50 text-emerald-700 border-emerald-200'
                  : 'bg-emerald-500/15 text-emerald-300 border-emerald-500/30'
              }`}
            >
              Saved locally
            </span>
          )}
        </div>
        <p className={`text-[14px] mt-1 ${muted}`}>
          Operator preferences for this browser. Model weights and API keys stay on the server (
          <span className="font-mono">.env.local</span>).
        </p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        <GlassCard>
          <div
            className={`flex items-center gap-2 font-bold text-[15px] mb-4 ${
              isLight ? 'text-sky-700' : 'text-cyan-400'
            }`}
          >
            <Sliders className="w-4 h-4" /> Telemetry sensitivity
          </div>
          <div className="space-y-5">
            <div>
              <div className="flex justify-between gap-2 mb-1">
                <label className={`text-[14px] font-semibold ${label}`}>
                  Acoustic vibration threshold (dB)
                </label>
                <span className={`text-[14px] font-mono ${muted}`}>{prefs.acousticThreshold}</span>
              </div>
              <input
                type="range"
                min={40}
                max={90}
                value={prefs.acousticThreshold}
                onChange={(e) => updatePref('acousticThreshold', Number(e.target.value))}
                className={`w-full ${isLight ? 'accent-sky-600' : 'accent-cyan-400'}`}
              />
            </div>
            <div>
              <div className="flex justify-between gap-2 mb-1">
                <label className={`text-[14px] font-semibold ${label}`}>
                  Pressure drop sensitivity (%)
                </label>
                <span className={`text-[14px] font-mono ${muted}`}>{prefs.pressureSensitivity}</span>
              </div>
              <input
                type="range"
                min={5}
                max={50}
                value={prefs.pressureSensitivity}
                onChange={(e) => updatePref('pressureSensitivity', Number(e.target.value))}
                className={`w-full ${isLight ? 'accent-sky-600' : 'accent-cyan-400'}`}
              />
            </div>
            <p className={`text-[14px] leading-relaxed ${muted}`}>
              Demo UI preferences only; they do not retrain sklearn models. Leak classification still
              uses the acoustic ExtraTrees model.
            </p>
          </div>
        </GlassCard>

        <GlassCard>
          <div
            className={`flex items-center gap-2 font-bold text-[15px] mb-4 ${
              isLight ? 'text-sky-700' : 'text-blue-400'
            }`}
          >
            <Key className="w-4 h-4" /> Integrations & runtime
          </div>
          <div className="space-y-3 text-[14px]">
            <div className={`p-2.5 rounded-lg font-mono flex justify-between items-center gap-3 ${monoRow}`}>
              <span className="inline-flex items-center gap-2 truncate">
                <Server className="w-3.5 h-3.5 shrink-0" /> FastAPI
              </span>
              {statusPill(apiStatus)}
            </div>
            <div className={`p-2.5 rounded-lg font-mono flex justify-between items-center gap-3 ${monoRow}`}>
              <span className="inline-flex items-center gap-2 truncate">
                <Key className="w-3.5 h-3.5 shrink-0" /> AquaLens / AquaAI
              </span>
              <span
                className={`font-bold shrink-0 ${
                  isLight ? 'text-slate-600' : 'text-slate-400'
                }`}
              >
                Via .env.local
              </span>
            </div>
            <div className={`p-2.5 rounded-lg font-mono flex justify-between items-center gap-3 ${monoRow}`}>
              <span className="inline-flex items-center gap-2 truncate">
                <Database className="w-3.5 h-3.5 shrink-0" /> SQLite
              </span>
              {statusPill('local')}
            </div>
            <p className={`text-[14px] leading-relaxed pt-1 ${muted}`}>
              Endpoint: <span className="font-mono">{FASTAPI_BASE}</span>
            </p>
          </div>
        </GlassCard>

        <ReadinessPanel isLight={isLight} />

        <GlassCard className="md:col-span-2">
          <div
            className={`flex items-center gap-2 font-bold text-[15px] mb-4 ${
              isLight ? 'text-sky-700' : 'text-cyan-400'
            }`}
          >
            {theme === 'light' ? <Sun className="w-4 h-4" /> : <Moon className="w-4 h-4" />} Appearance
          </div>
          <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
            <p className={`text-[14px] ${muted}`}>
              Current theme: <span className="font-semibold capitalize">{theme}</span>. Same control as
              the header toggle, stored in this browser.
            </p>
            <button
              type="button"
              onClick={toggleTheme}
              className={`inline-flex items-center justify-center gap-2 rounded-lg px-4 py-2 text-[14px] font-semibold border transition-colors ${
                isLight
                  ? 'bg-slate-900 text-white border-slate-900 hover:bg-slate-800'
                  : 'bg-cyan-500 text-slate-950 border-cyan-400 hover:bg-cyan-400'
              }`}
            >
              Switch to {theme === 'light' ? 'dark' : 'light'} mode
            </button>
          </div>
        </GlassCard>
      </div>
    </div>
  );
};
