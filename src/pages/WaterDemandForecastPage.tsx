import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import {
  ForecastChart,
  ForecastControls,
  ForecastExport,
  ForecastHeader,
  ForecastInsights,
  ForecastKpiCards,
  ForecastSummary,
  ForecastToolbar,
  filterSeriesByRange,
  type DemandWorkspaceData,
  type HorizonState,
  type SeriesPoint,
  type TimeRangeKey,
} from '../components/demand';
import { FilteredAssetMap } from '../components/maps';
import {
  fetchDemandMetrics,
  fetchDemandStatus,
  predictDemand,
  trainDemandModel,
  type DemandStatus,
} from '../services/demandForecast';
import { QuickSummary } from '../components/ui/QuickSummary';

function buildDemandSummary(data: DemandWorkspaceData | null, capacity?: number | null): string[] {
  if (!data?.series?.length && !data?.summary) {
    return [
      'Demand forecast is ready to run for the selected range.',
      'Generate a prediction to see shortage risk and system usage.',
    ];
  }
  const risk = String(data.summary?.expected_shortage_risk || data.risk_label || 'unknown').toLowerCase();
  const demand = data.today_predicted_demand_mgd;
  const util =
    demand != null && capacity ? Math.round((demand / capacity) * 100) : data.summary?.capacity_utilization_pct;
  const lines: string[] = [];

  if (risk === 'low' || risk === 'minimal' || risk === 'stable') {
    lines.push('Demand is expected to remain stable over the selected forecast range.');
    lines.push('No major shortage risk detected.');
  } else if (risk === 'moderate' || risk === 'medium' || risk === 'watch') {
    lines.push('Demand may rise moderately over the selected forecast range.');
    lines.push('Monitor capacity closely. Elevated shortage risk is possible.');
  } else {
    lines.push('Demand pressure is elevated for the selected forecast range.');
    lines.push('Shortage risk requires operational attention.');
  }

  if (util != null) {
    lines.push(
      util < 85
        ? 'Current water usage remains below system capacity.'
        : 'Water system usage is approaching maximum capacity.',
    );
  }
  return lines.slice(0, 3);
}

export const WaterDemandForecastPage: React.FC = () => {
  const chartRef = useRef<HTMLDivElement | null>(null);
  const [horizon, setHorizon] = useState<HorizonState>({ unit: 'days', value: 7 });
  const [range, setRange] = useState<TimeRangeKey>('ALL');
  const [status, setStatus] = useState<DemandStatus | null>(null);
  const [data, setData] = useState<DemandWorkspaceData | null>(null);
  const [metrics, setMetrics] = useState<Record<string, number | null | undefined>>({});
  const [error, setError] = useState('');
  const [loadingStatus, setLoadingStatus] = useState(true);
  const [predicting, setPredicting] = useState(false);
  const [training, setTraining] = useState(false);

  const refreshStatus = useCallback(async () => {
    setLoadingStatus(true);
    try {
      const st = await fetchDemandStatus();
      setStatus(st);
      const met = await fetchDemandMetrics();
      setMetrics((met.metrics || {}) as Record<string, number | null | undefined>);
      if (!st.trained) {
        setData({ trained: false, message: 'Model not trained' });
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Unable to load model status');
    } finally {
      setLoadingStatus(false);
    }
  }, []);

  useEffect(() => {
    void refreshStatus();
  }, [refreshStatus]);

  useEffect(() => {
    if (!loadingStatus && status?.trained && !data?.series?.length && !predicting) {
      void (async () => {
        try {
          setPredicting(true);
          const res = await predictDemand({
            value: 30,
            unit: 'days',
            include_history_days: 365,
          });
          setData(res.data);
          if (res.data.metrics) setMetrics(res.data.metrics);
        } catch {
          /* keep empty chart; user can predict manually */
        } finally {
          setPredicting(false);
        }
      })();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [loadingStatus, status?.trained]);

  const runPredict = useCallback(
    async (next?: HorizonState) => {
      const h = next || horizon;
      setPredicting(true);
      setError('');
      setData((prev) =>
        prev
          ? {
              ...prev,
              series: [],
              forecast_series: [],
              summary: undefined,
              insights: [],
              reliability: undefined,
            }
          : prev,
      );
      try {
        const res = await predictDemand({
          value: h.value,
          unit: h.unit,
          include_history_days: 365,
        });
        setData(res.data);
        if (res.data.metrics) setMetrics(res.data.metrics);
        setRange('ALL');
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Prediction failed');
      } finally {
        setPredicting(false);
      }
    },
    [horizon],
  );

  const runTrain = async () => {
    setTraining(true);
    setError('');
    try {
      await trainDemandModel({ use_sample: true });
      await refreshStatus();
      await runPredict();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Training failed');
    } finally {
      setTraining(false);
    }
  };

  const onPreset = (next: HorizonState) => {
    setHorizon(next);
    void runPredict(next);
  };

  const series: SeriesPoint[] = data?.series || [];
  const visibleSeries = useMemo(() => filterSeriesByRange(series, range), [series, range]);
  const untrained = status ? !status.trained : data?.trained === false;
  const forecastCount = data?.horizon?.point_count ?? data?.forecast_series?.length;
  const activeHorizonValue = data?.horizon?.value ?? horizon.value;
  const activeHorizonUnit = data?.horizon?.unit ?? horizon.unit;
  const capacity = data?.capacity_mgd ?? status?.capacity_mgd;

  const modelStatus = loadingStatus
    ? 'loading'
    : predicting
      ? 'predicting'
      : untrained
        ? 'untrained'
        : 'ready';

  const summaryLines = useMemo(() => buildDemandSummary(data, capacity), [data, capacity]);

  return (
    <div className="space-y-4 pb-8 print:bg-white">
      <ForecastHeader
        modelName={data?.model?.backend || status?.backend || 'xgboost_regressor'}
        modelVersion={status?.model_version || data?.model_version}
        modelStatus={modelStatus}
        lastTrained={status?.last_trained_at || data?.last_trained_at}
        dataPoints={status?.training_rows ?? data?.model?.training_dataset_size}
        onTrain={() => void runTrain()}
        training={training}
      />

      {error && (
        <div className="rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-[15px] text-red-800 dark:border-red-900 dark:bg-red-950/40 dark:text-red-200">
          {error}
        </div>
      )}

      {untrained && !loadingStatus ? (
        <section className="rounded-xl border border-amber-200 bg-amber-50 px-5 py-8 dark:border-amber-900 dark:bg-amber-950/30">
          <h2 className="text-base font-semibold text-amber-950 dark:text-amber-100">Model not trained</h2>
          <p className="mt-2 max-w-xl text-[15px] text-amber-900/90 dark:text-amber-100/80">
            Train the demand model before generating operational forecasts.
          </p>
          <button
            type="button"
            onClick={() => void runTrain()}
            disabled={training}
            className="mt-5 min-h-11 rounded-lg bg-[#1e3a5f] px-4 py-2.5 text-[15px] font-semibold text-white disabled:opacity-40"
          >
            {training ? 'Training…' : 'Train model'}
          </button>
        </section>
      ) : (
        <>
          <QuickSummary
            lines={summaryLines}
            technicalNote="Demand predictions combine past consumption patterns with weather and capacity constraints."
          />

          <FilteredAssetMap
            types={['demand_region', 'reservoir']}
            title="Demand overview map"
            subtitle="Demand regions from the shared national geospatial catalogue"
            height={280}
            variant="demand"
          />

          <ForecastKpiCards
            predictedDemand={data?.today_predicted_demand_mgd}
            peakDemand={data?.summary?.predicted_peak_demand_mgd}
            capacity={capacity}
            confidence={data?.confidence_score ?? data?.summary?.confidence}
            risk={data?.summary?.expected_shortage_risk || data?.risk_label}
            horizonValue={activeHorizonValue}
            horizonUnit={activeHorizonUnit}
            summary={data?.summary}
          />

          <ForecastControls
            horizon={horizon}
            onChange={setHorizon}
            onPredict={() => void runPredict()}
            onPreset={onPreset}
            predicting={predicting}
            disabled={untrained}
          />

          <ForecastToolbar
            range={range}
            onRangeChange={setRange}
            subtitle={
              forecastCount != null
                ? `Active forecast · ${forecastCount} ${activeHorizonUnit}`
                : undefined
            }
            rightSlot={<ForecastExport series={series} chartContainerRef={chartRef} />}
          />

          <div className="grid items-stretch gap-4 xl:grid-cols-12">
            <div className="xl:col-span-8 2xl:col-span-9">
              <ForecastChart
                series={visibleSeries}
                forecastPointCount={forecastCount}
                unit={activeHorizonUnit}
                capacityMgd={capacity}
                chartRef={chartRef}
                loading={predicting}
              />
            </div>
            <div className="xl:col-span-4 2xl:col-span-3">
              <ForecastSummary summary={data?.summary} capacityMgd={capacity} />
            </div>
          </div>

          <ForecastInsights insights={data?.insights} warning={data?.reliability?.warning} />
        </>
      )}
    </div>
  );
};
