import React, { useState, useEffect, useCallback } from 'react';
import { CommandCenter } from '../components/dashboard/executive/CommandCenter';
import { AIExecutiveReportModal } from '../components/dashboard/AIExecutiveReportModal';
import { Button } from '../components/ui/Button';
import { FASTAPI_BASE } from '../config/api';
import { apiGet } from '../services/apiClient';
import {
  fetchWaterStress,
  loadAlerts,
  loadGroundwater,
  loadRecommendations,
  loadSensors,
  loadShortageRisks,
  loadWeather,
  type ApiAlert,
  type ApiAquifer,
  type ApiSensor,
  type ApiShortageRisk,
  type ApiWeather,
  type WaterIntelligencePayload,
} from '../services/telemetry';

export const DashboardPage: React.FC = () => {
  const [isReportOpen, setIsReportOpen] = useState(false);
  const [reportData, setReportData] = useState<any>(null);
  const [isAiSynthesizing, setIsAiSynthesizing] = useState(false);

  const [sensors, setSensors] = useState<ApiSensor[]>([]);
  const [alerts, setAlerts] = useState<ApiAlert[]>([]);
  const [shortageRisks, setShortageRisks] = useState<ApiShortageRisk[]>([]);
  const [aquifers, setAquifers] = useState<ApiAquifer[]>([]);
  const [weather, setWeather] = useState<ApiWeather | null>(null);
  const [waterStress, setWaterStress] = useState<WaterIntelligencePayload | null>(null);
  const [recommendations, setRecommendations] = useState<any[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [apiUnavailable, setApiUnavailable] = useState(false);
  const [apiError, setApiError] = useState<string | null>(null);

  const fetchDashboardData = useCallback(async () => {
    setIsLoading(true);
    setApiUnavailable(false);
    setApiError(null);
    try {
      await fetch(`${FASTAPI_BASE}/health`).then((r) => {
        if (!r.ok) throw new Error(`Health check failed (${r.status})`);
      });

      const results = await Promise.allSettled([
        loadSensors(),
        loadAlerts(),
        loadShortageRisks(),
        loadGroundwater(),
        loadWeather(),
        loadRecommendations(),
        fetchWaterStress(),
      ]);

      const failures: string[] = [];
      const [sensorsR, alertsR, shortageR, gwR, weatherR, recsR, wsiR] = results;

      if (sensorsR.status === 'fulfilled') setSensors(sensorsR.value);
      else {
        setSensors([]);
        failures.push('sensors');
      }

      if (alertsR.status === 'fulfilled') setAlerts(alertsR.value);
      else {
        setAlerts([]);
        failures.push('leakages');
      }

      if (shortageR.status === 'fulfilled') setShortageRisks(shortageR.value);
      else {
        setShortageRisks([]);
        failures.push('shortage-risks');
      }

      if (gwR.status === 'fulfilled') setAquifers(gwR.value);
      else {
        setAquifers([]);
        failures.push('groundwater');
      }

      if (weatherR.status === 'fulfilled') setWeather(weatherR.value);
      else {
        setWeather(null);
        failures.push('weather');
      }

      if (recsR.status === 'fulfilled') {
        setRecommendations(recsR.value.recommendations || []);
      } else {
        setRecommendations([]);
        failures.push('recommendation');
      }

      if (wsiR.status === 'fulfilled') setWaterStress(wsiR.value);
      else {
        setWaterStress(null);
        failures.push('water-stress');
      }

      if (failures.length >= 6) {
        setApiUnavailable(true);
        setApiError(`Most dashboard endpoints failed: ${failures.join(', ')}`);
      } else if (failures.length > 0) {
        setApiError(`Partial load. Failed: ${failures.join(', ')}`);
      }
    } catch (err) {
      setApiUnavailable(true);
      setApiError(err instanceof Error ? err.message : 'Connection failed');
      setSensors([]);
      setAlerts([]);
      setShortageRisks([]);
      setAquifers([]);
      setWeather(null);
      setWaterStress(null);
      setRecommendations([]);
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    void fetchDashboardData();
  }, [fetchDashboardData]);

  const handleGenerateReport = async () => {
    setIsAiSynthesizing(true);
    setIsReportOpen(true);
    try {
      const body = await apiGet<any>('/ai/recommendation-engine/live?force_refresh=false');
      const data = body.data || body;
      setReportData({
        title: 'AquaMind Executive Water Briefing',
        summary: data.text_summary || 'Briefing ready for your operations team.',
        keyFindings: data.recommendations || [],
        actionPlan: data.recommendations || [],
        expected_saving: data.expected_saving,
        source: `${data.source || 'engine'} · ${data.provider || 'n/a'}`,
      });
    } catch {
      setReportData({
        title: 'Dashboard Snapshot',
        summary: 'Could not reach recommendation engine. Showing local snapshot only.',
        keyFindings: recommendations.map((r) => r.title || r.action_description).filter(Boolean),
      });
    } finally {
      setIsAiSynthesizing(false);
    }
  };

  if (isLoading) {
    return (
      <div className="flex flex-col items-center justify-center space-y-4 py-24">
        <div className="h-10 w-10 animate-spin rounded-full border-[3px] border-[var(--am-accent)] border-t-transparent" />
        <p className="text-[16px] text-[var(--am-text-secondary)]">
          Assembling executive water intelligence…
        </p>
      </div>
    );
  }

  if (apiUnavailable) {
    return (
      <div className="rounded-[var(--am-radius-xl)] bg-[var(--am-bg-elevated)] p-8 text-center shadow-[var(--am-shadow-md)]">
        <h2 className="text-[22px] font-semibold text-[var(--am-warning)]">Unable to reach AquaMind services</h2>
        <p className="mt-2 text-[16px] text-[var(--am-text-secondary)]">
          Confirm FastAPI is running on port 8000, then try again.
        </p>
        {apiError ? <p className="mt-3 text-[15px] text-[var(--am-text-tertiary)]">{apiError}</p> : null}
        <Button className="mt-5" onClick={() => void fetchDashboardData()}>
          Try again
        </Button>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {apiError ? (
        <div className="rounded-xl bg-[var(--am-warning-soft)] px-4 py-2 text-[15px] text-[var(--am-warning)]">
          Some live readings could not refresh. Showing the latest available command center view.
        </div>
      ) : null}

      <CommandCenter
        sensors={sensors}
        alerts={alerts}
        shortageRisks={shortageRisks}
        aquifers={aquifers}
        weather={weather}
        waterStress={waterStress}
        recommendations={recommendations}
        onOpenReportModal={() => void handleGenerateReport()}
        onRefresh={() => void fetchDashboardData()}
      />

      <AIExecutiveReportModal
        isOpen={isReportOpen}
        onClose={() => setIsReportOpen(false)}
        reportData={reportData}
        isLoading={isAiSynthesizing}
        onRegenerate={() => void handleGenerateReport()}
      />
    </div>
  );
};

export default DashboardPage;
