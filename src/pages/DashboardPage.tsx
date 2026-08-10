import React, { useCallback, useEffect, useRef, useState } from 'react';
import { CommandCenter } from '../components/dashboard/executive/CommandCenter';
import { CommandCenterSkeleton } from '../components/dashboard/executive/CommandCenterSkeleton';
import { AIExecutiveReportModal } from '../components/dashboard/AIExecutiveReportModal';
import { Button } from '../components/ui/Button';
import { ApiError, apiGet, isAbortError } from '../services/apiClient';
import { useDashboardData } from '../hooks/useDashboardData';
import type {
  AIRecommendationEngineData,
  ApiEnvelope,
  ExecutiveBriefing,
} from '../types/apiContracts';

/** Backstop for the executive briefing so the modal can never spin indefinitely. */
const REPORT_TIMEOUT_MS = 30_000;

export const DashboardPage: React.FC = () => {
  const {
    panels,
    panelStatus,
    isInitialLoading,
    apiUnavailable,
    failedPanels,
    lastUpdatedAt,
    refresh,
    requestRecommendations,
  } = useDashboardData();

  const [isReportOpen, setIsReportOpen] = useState(false);
  const [reportData, setReportData] = useState<ExecutiveBriefing | null>(null);
  const [isAiSynthesizing, setIsAiSynthesizing] = useState(false);
  const reportControllerRef = useRef<AbortController | null>(null);

  useEffect(
    () => () => reportControllerRef.current?.abort(new ApiError('Dashboard unmounted', 'aborted')),
    []
  );

  /**
   * The AI briefing is a remote LLM call, so it is never part of page load and
   * gets a longer deadline than the dashboard's 10s budget. It still needs
   * *a* deadline: the modal shows a spinner until this settles, and a hung
   * provider would otherwise leave it spinning for the rest of the session.
   * The backend caps its own remote-AI budget well below this.
   */
  const synthesizeReport = useCallback(
    async (forceRefresh: boolean) => {
      reportControllerRef.current?.abort(new ApiError('Superseded by a newer report request', 'aborted'));
      const controller = new AbortController();
      reportControllerRef.current = controller;

      setIsAiSynthesizing(true);
      try {
        const body = await apiGet<ApiEnvelope<AIRecommendationEngineData>>(
          `/ai/recommendation-engine/live?force_refresh=${forceRefresh ? 'true' : 'false'}`,
          { signal: controller.signal, timeoutMs: REPORT_TIMEOUT_MS }
        );
        const data = body.data;
        setReportData({
          title: 'AquaMind Executive Water Briefing',
          summary: data?.text_summary || 'Briefing ready for your operations team.',
          keyFindings: data?.recommendations || [],
          actionPlan: data?.recommendations || [],
          expected_saving: data?.expected_saving,
          source: `${data?.source || 'engine'} · ${data?.provider || 'n/a'}`,
        });
      } catch (error) {
        if (isAbortError(error)) return;
        const actions = (panels.recommendations.data || [])
          .map((r) => r.title || r.action_description)
          .filter((value): value is string => Boolean(value));
        setReportData({
          title: 'Operations Snapshot',
          summary: actions.length
            ? 'Synthesis is unavailable right now. These actions come from the current model telemetry.'
            : 'Synthesis is unavailable right now and no current recommendation feed has loaded. Refresh the dashboard and re-open the briefing.',
          keyFindings: actions,
          actionPlan: actions,
          source: 'local-fallback',
        });
      } finally {
        if (reportControllerRef.current === controller) {
          setIsAiSynthesizing(false);
        }
      }
    },
    [panels.recommendations.data]
  );

  const openReport = useCallback(() => {
    setIsReportOpen(true);
    // The modal falls back to the recommendation feed if the LLM call fails.
    requestRecommendations();
    // Reuse the briefing already synthesized this session; "Re-synthesize" forces a new one.
    if (!reportData && !isAiSynthesizing) void synthesizeReport(false);
  }, [reportData, isAiSynthesizing, requestRecommendations, synthesizeReport]);

  if (apiUnavailable) {
    return (
      <div className="rounded-[var(--am-radius-xl)] bg-[var(--am-bg-elevated)] p-8 text-center shadow-[var(--am-shadow-md)]">
        <h2 className="text-[22px] font-semibold text-[var(--am-warning)]">Unable to reach AquaMind AI services</h2>
        <p className="mt-2 text-[16px] text-[var(--am-text-secondary)]">
          Confirm FastAPI is running on port 8000, then try again.
        </p>
        <p className="mt-3 text-[15px] text-[var(--am-text-tertiary)]">
          {failedPanels.length
            ? `Could not load: ${failedPanels.join(', ')}.`
            : panels.shortageRisks.error ||
              panels.alerts.error ||
              panels.waterStress.error ||
              'No dashboard endpoint responded.'}
        </p>
        <Button className="mt-5" onClick={refresh}>
          Try again
        </Button>
      </div>
    );
  }

  // The shell paints straight away; the command center swaps in once the
  // first-view feeds (water stress, reservoirs, leak alerts) have settled.
  if (isInitialLoading) {
    return <CommandCenterSkeleton />;
  }

  return (
    <div className="space-y-4">
      {failedPanels.length > 0 ? (
        <div className="flex flex-wrap items-center justify-between gap-3 rounded-xl bg-[var(--am-warning-soft)] px-4 py-2 text-[15px] text-[var(--am-warning)]">
          <span>
            Some live readings could not refresh ({failedPanels.join(', ')}). Showing the latest available
            command center view.
          </span>
          <Button variant="secondary" size="sm" onClick={refresh}>
            Retry
          </Button>
        </div>
      ) : null}

      <CommandCenter
        sensors={panels.sensors.data || []}
        alerts={panels.alerts.data || []}
        shortageRisks={panels.shortageRisks.data || []}
        aquifers={panels.aquifers.data || []}
        weather={panels.weather.data || null}
        waterStress={panels.waterStress.data}
        recommendations={panels.recommendations.data || []}
        feedStatus={panelStatus}
        lastUpdatedAt={lastUpdatedAt}
        onRequestRecommendations={requestRecommendations}
        onOpenReportModal={openReport}
        onRefresh={refresh}
      />

      <AIExecutiveReportModal
        isOpen={isReportOpen}
        onClose={() => setIsReportOpen(false)}
        reportData={reportData}
        isLoading={isAiSynthesizing}
        onRegenerate={() => void synthesizeReport(true)}
      />
    </div>
  );
};

export default DashboardPage;
