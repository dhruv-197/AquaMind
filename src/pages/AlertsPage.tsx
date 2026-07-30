import React, { useEffect, useState } from 'react';
import { GlassCard } from '../components/common/GlassCard';
import { AlertOctagon, Clock } from 'lucide-react';
import { loadAlerts, type ApiAlert } from '../services/telemetry';

export const AlertsPage: React.FC = () => {
  const [alerts, setAlerts] = useState<ApiAlert[]>([]);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const rows = await loadAlerts();
        if (!cancelled) setAlerts(rows);
      } catch (err) {
        if (!cancelled) setError(err instanceof Error ? err.message : 'Failed to load alerts');
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => { cancelled = true; };
  }, []);

  return (
    <div className="space-y-6">
      <div className="bg-slate-900/40 border border-slate-800/80 rounded-2xl p-6 backdrop-blur-xl">
        <h1 className="text-2xl font-bold text-white">System Alerts & Notifications</h1>
        <p className="text-[14px] text-slate-400 mt-1">
          Stay ahead of leaks and critical incidents across your network.
        </p>
      </div>

      {error && (
        <div className="rounded-xl border border-amber-500/40 bg-amber-500/10 px-4 py-3 text-[14px] text-amber-200">{error}</div>
      )}
      {loading && <p className="text-[15px] text-slate-400">Checking the latest network alerts…</p>}
      {!loading && alerts.length === 0 && !error && (
        <p className="text-[15px] text-slate-400">All clear. No active alerts right now.</p>
      )}

      <div className="space-y-3">
        {alerts.map((alert) => (
          <GlassCard key={alert.id} glow={alert.severity === 'critical'}>
            <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
              <div className="flex items-center gap-3">
                <div className={`p-2.5 rounded-xl ${
                  alert.severity === 'critical'
                    ? 'bg-red-500/20 text-red-400 border border-red-500/30'
                    : 'bg-amber-500/20 text-amber-400 border border-amber-500/30'
                }`}>
                  <AlertOctagon className="w-5 h-5" />
                </div>
                <div>
                  <div className="flex items-center gap-2">
                    <span className="text-[15px] font-bold text-white">
                      {alert.sensorId || alert.id} - {alert.locationName}
                    </span>
                    <span className="px-2 py-0.5 rounded text-[16px] font-mono uppercase bg-red-500/20 text-red-300 border border-red-500/30">
                      {alert.severity}
                    </span>
                  </div>
                  <p className="text-[14px] text-slate-400 mt-1">{alert.aiDiagnostics}</p>
                </div>
              </div>

              <div className="flex items-center gap-4 text-[14px] font-mono text-slate-400">
                <div className="flex items-center gap-1">
                  <Clock className="w-3.5 h-3.5 text-cyan-400" />
                  <span>{alert.timestamp ? new Date(alert.timestamp).toLocaleString() : 'n/a'}</span>
                </div>
                <span className="px-3 py-1.5 rounded-lg bg-slate-800 text-slate-300 border border-slate-700 text-[14px]">
                  {alert.status}
                </span>
              </div>
            </div>
          </GlassCard>
        ))}
      </div>
    </div>
  );
};
