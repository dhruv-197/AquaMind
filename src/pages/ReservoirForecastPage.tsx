import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import {
  ForecastControls,
  ForecastExport,
  ForecastInsights,
  ForecastToolbar,
  filterSeriesByRange,
  type HorizonState,
  type SeriesPoint,
  type TimeRangeKey,
} from '../components/demand';
import {
  ReservoirChart,
  ReservoirHeader,
  ReservoirKpiCards,
  ReservoirMap,
  ReservoirSummary,
  type ReservoirWorkspaceData,
} from '../components/reservoir';
import {
  fetchReservoirMetrics,
  fetchReservoirStatus,
  predictReservoir,
  trainReservoirModel,
  type ReservoirStatus,
} from '../services/reservoirForecast';
import { useWaterAssets } from '../hooks/useWaterAssets';
import type { WaterAsset } from '../services/geospatial';
import { Badge } from '../components/ui/Badge';
import { QuickSummary } from '../components/ui/QuickSummary';
import { riskTone } from '../design-system/tokens';

function buildReservoirSummary(
  data: ReservoirWorkspaceData | null,
  selectedName?: string | null,
): string[] {
  if (!data?.series?.length && !data?.summary) {
    return [
      'Reservoir forecast is ready. Select a location and run a prediction.',
      'Storage trends, risk level, and remaining days will appear here.',
    ];
  }

  const lines: string[] = [];
  const current = data?.current_storage_pct ?? data?.summary?.current_storage_pct;
  const forecast = data?.forecasted_storage_pct ?? data?.summary?.forecasted_storage_pct;
  const risk = String(data?.summary?.risk_label ?? data?.risk_label ?? 'unknown').toLowerCase();
  const days = data?.summary?.remaining_days ?? data?.summary?.days_to_critical;
  const name = data?.reservoir_name || selectedName;

  if (current != null && forecast != null) {
    const delta = forecast - current;
    if (Math.abs(delta) < 2) {
      lines.push(
        `${name ? `${name}: ` : ''}Storage is expected to remain stable over the forecast range (${forecast.toFixed(1)}%).`,
      );
    } else if (delta > 0) {
      lines.push(
        `${name ? `${name}: ` : ''}Storage is predicted to rise from ${current.toFixed(1)}% to ${forecast.toFixed(1)}%.`,
      );
    } else {
      lines.push(
        `${name ? `${name}: ` : ''}Storage is predicted to decline from ${current.toFixed(1)}% to ${forecast.toFixed(1)}%.`,
      );
    }
  }

  if (risk === 'low' || risk === 'minimal' || risk === 'stable') {
    lines.push('Storage risk is low for the selected forecast range.');
  } else if (risk === 'moderate' || risk === 'medium' || risk === 'watch') {
    lines.push('Moderate storage risk. Monitor levels and inflows closely.');
  } else if (risk !== 'unknown' && risk !== '-') {
    lines.push(`Elevated storage risk (${risk}) requires operational attention.`);
  }

  if (days != null) {
    lines.push(
      days < 30
        ? `Only ${days} days of usable storage remain before critical levels (<20%).`
        : `Approximately ${days} days of usable storage remain at current trends.`,
    );
  }

  return lines.slice(0, 3);
}

export const ReservoirForecastPage: React.FC = () => {
  const chartRef = useRef<HTMLDivElement | null>(null);
  const [horizon, setHorizon] = useState<HorizonState>({ unit: 'days', value: 7 });
  const [range, setRange] = useState<TimeRangeKey>('ALL');
  const [status, setStatus] = useState<ReservoirStatus | null>(null);
  const [data, setData] = useState<ReservoirWorkspaceData | null>(null);
  const [metrics, setMetrics] = useState<Record<string, number | null | undefined>>({});
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [error, setError] = useState('');
  const [loadingStatus, setLoadingStatus] = useState(true);
  const [predicting, setPredicting] = useState(false);
  const [training, setTraining] = useState(false);
  const [stateFilter, setStateFilter] = useState('');

  const {
    assets: nationalReservoirs,
    loading: geoLoading,
    error: geoError,
    meta: geoMeta,
  } = useWaterAssets({ types: 'reservoir' });

  const filteredAssets = useMemo(() => {
    if (!stateFilter) return nationalReservoirs;
    return nationalReservoirs.filter((a) => (a.state || '') === stateFilter);
  }, [nationalReservoirs, stateFilter]);

  const states = useMemo(
    () =>
      Array.from(new Set(nationalReservoirs.map((a) => a.state).filter(Boolean) as string[])).sort(),
    [nationalReservoirs]
  );

  const selectedAsset: WaterAsset | null = useMemo(
    () => nationalReservoirs.find((a) => a.id === selectedId) || null,
    [nationalReservoirs, selectedId]
  );

  const refreshStatus = useCallback(async () => {
    setLoadingStatus(true);
    try {
      const st = await fetchReservoirStatus();
      setStatus(st);
      const met = await fetchReservoirMetrics();
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

  // Default selection from national catalogue
  useEffect(() => {
    if (!selectedId && nationalReservoirs.length) {
      setSelectedId(nationalReservoirs[0].id);
    }
  }, [nationalReservoirs, selectedId]);

  const runPredict = useCallback(
    async (next?: HorizonState, assetId?: string | null) => {
      const h = next || horizon;
      const aid = assetId ?? selectedId;
      if (!aid) return;
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
              executive_recommendations: [],
            }
          : prev
      );
      try {
        const asset = nationalReservoirs.find((a) => a.id === aid);
        const res = await predictReservoir({
          value: h.value,
          unit: h.unit,
          asset_id: aid,
          capacity_mcm: asset?.capacity_mcm ?? undefined,
          include_history_days: 365,
        });
        setData(res.data);
        if (res.data.metrics) setMetrics(res.data.metrics);
        if (res.data.reservoir_id) setSelectedId(res.data.reservoir_id);
        setRange('ALL');
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Prediction failed');
      } finally {
        setPredicting(false);
      }
    },
    [horizon, selectedId, nationalReservoirs]
  );

  useEffect(() => {
    if (!loadingStatus && status?.trained && selectedId && !predicting && !data?.series?.length) {
      void runPredict({ unit: 'days', value: 30 }, selectedId);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [loadingStatus, status?.trained, selectedId]);

  const runTrain = async () => {
    setTraining(true);
    setError('');
    try {
      await trainReservoirModel({ use_sample: true });
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

  const onSelectReservoir = useCallback(
    (id: string) => {
      setSelectedId(id);
      void runPredict(horizon, id);
    },
    [horizon, runPredict],
  );

  const series: SeriesPoint[] = data?.series || [];
  const visibleSeries = useMemo(() => filterSeriesByRange(series, range), [series, range]);
  const untrained = status ? !status.trained : data?.trained === false;
  const forecastCount = data?.horizon?.point_count ?? data?.forecast_series?.length;
  const activeHorizonValue = data?.horizon?.value ?? horizon.value;
  const activeHorizonUnit = data?.horizon?.unit ?? horizon.unit;

  const summaryLines = useMemo(
    () => buildReservoirSummary(data, data?.reservoir_name || selectedAsset?.name),
    [data, selectedAsset?.name],
  );

  const modelStatus = loadingStatus
    ? 'loading'
    : predicting
      ? 'predicting'
      : untrained
        ? 'untrained'
        : 'ready';

  return (
    <div className="space-y-4 pb-8 print:bg-white">
      <ReservoirHeader
        modelName={data?.model?.backend || status?.backend || 'xgboost_regressor'}
        modelVersion={status?.model_version || data?.model_version}
        modelStatus={modelStatus}
        lastTrained={status?.last_trained_at || data?.last_trained_at}
        dataPoints={status?.training_rows ?? data?.model?.training_dataset_size}
        onTrain={() => void runTrain()}
        training={training}
        selectedName={data?.reservoir_name || selectedAsset?.name}
      />

      {(error || geoError) && (
        <div className="rounded-xl bg-[var(--am-danger-soft)] px-4 py-3 text-[15px] text-[var(--am-danger)]">
          {error || geoError}
        </div>
      )}

      {untrained && !loadingStatus ? (
        <section className="rounded-[var(--am-radius-xl)] bg-[var(--am-warning-soft)] px-5 py-8">
          <h2 className="text-base font-semibold text-[var(--am-text)]">Model not trained</h2>
          <p className="mt-2 max-w-xl text-[15px] text-[var(--am-text-secondary)]">
            Train the reservoir model before generating storage forecasts. The national map still
            loads from the shared geospatial catalogue ({geoMeta?.counts?.reservoir ?? '-'} reservoirs).
          </p>
          <button
            type="button"
            onClick={() => void runTrain()}
            disabled={training}
            className="mt-5 rounded-[14px] bg-[var(--am-accent)] px-4 py-2.5 text-[15px] font-semibold text-white disabled:opacity-40"
          >
            {training ? 'Training…' : 'Train model'}
          </button>
          <div className="mt-6">
            <div className="mb-3 flex flex-wrap items-center gap-2">
              <label className="text-[15px] font-semibold text-[var(--am-text-secondary)]">
                State filter
              </label>
              <select
                value={stateFilter}
                onChange={(e) => setStateFilter(e.target.value)}
                className="rounded-xl border-0 bg-[var(--am-bg-elevated)] px-3 py-2 text-[16px] shadow-[var(--am-shadow-sm)]"
              >
                <option value="">All states ({states.length})</option>
                {states.map((s) => (
                  <option key={s} value={s}>
                    {s}
                  </option>
                ))}
              </select>
            </div>
            <ReservoirMap
              assets={filteredAssets}
              selectedId={selectedId}
              onSelect={onSelectReservoir}
              loading={geoLoading}
            />
          </div>
        </section>
      ) : (
        <>
          <QuickSummary
            lines={summaryLines}
            technicalNote="Prediction uses historical storage, rainfall, weather, and environmental variables."
          />

          <div className="mb-1 flex flex-wrap items-center gap-2">
            <label className="text-[15px] font-semibold text-[var(--am-text-secondary)]">State filter</label>
            <select
              value={stateFilter}
              onChange={(e) => setStateFilter(e.target.value)}
              className="rounded-xl border-0 bg-[var(--am-bg-elevated)] px-3 py-2 text-[16px] shadow-[var(--am-shadow-sm)]"
            >
              <option value="">All states ({states.length})</option>
              {states.map((s) => (
                <option key={s} value={s}>
                  {s}
                </option>
              ))}
            </select>
          </div>

          <div className="grid gap-4 xl:grid-cols-12">
            <div className="xl:col-span-8">
              <ReservoirMap
                assets={filteredAssets}
                selectedId={selectedId}
                onSelect={onSelectReservoir}
                loading={geoLoading}
              />
            </div>
            <div className="xl:col-span-4">
              <SelectedAssetPanel asset={selectedAsset} data={data} />
            </div>
          </div>

          <ReservoirKpiCards
            currentStorage={data?.current_storage_pct ?? selectedAsset?.current_storage_pct}
            forecastedStorage={data?.forecasted_storage_pct ?? selectedAsset?.forecast_storage_pct}
            remainingDays={data?.summary?.remaining_days}
            peakStorage={data?.summary?.peak_storage_pct}
            minimumStorage={data?.summary?.minimum_storage_pct}
            confidence={data?.confidence_score ?? data?.summary?.confidence ?? selectedAsset?.confidence}
            risk={data?.summary?.risk_label || data?.risk_label || selectedAsset?.risk_level}
            summary={data?.summary}
            horizonValue={activeHorizonValue}
            horizonUnit={activeHorizonUnit}
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
                ? `Active forecast · ${data?.reservoir_name || selectedAsset?.name || 'reservoir'} · ${forecastCount} ${activeHorizonUnit}`
                : undefined
            }
            rightSlot={
              <ForecastExport
                series={series}
                chartContainerRef={chartRef}
                filePrefix="reservoir-forecast"
              />
            }
          />

          <div className="grid items-stretch gap-4 xl:grid-cols-12">
            <div className="xl:col-span-8 2xl:col-span-9">
              <ReservoirChart
                series={visibleSeries}
                forecastPointCount={forecastCount}
                unit={activeHorizonUnit}
                chartRef={chartRef}
                loading={predicting}
              />
            </div>
            <div className="xl:col-span-4 2xl:col-span-3">
              <ReservoirSummary
                summary={data?.summary}
                recommendations={data?.executive_recommendations}
              />
            </div>
          </div>

          <ForecastInsights insights={data?.insights} warning={data?.reliability?.warning} />
        </>
      )}
    </div>
  );
};

function SelectedAssetPanel({
  asset,
  data,
}: {
  asset: WaterAsset | null;
  data: ReservoirWorkspaceData | null;
}) {
  if (!asset) {
    return (
      <div className="flex h-full min-h-[280px] items-center justify-center rounded-[var(--am-radius-xl)] bg-[var(--am-bg-elevated)] p-5 text-[16px] text-[var(--am-text-secondary)] shadow-[var(--am-shadow-md)]">
        Select a reservoir on the map
      </div>
    );
  }
  const risk = data?.risk_label || asset.risk_level || '-';
  const tone = riskTone(risk);
  const rows: [string, string][] = [
    ['Name', asset.name],
    ['State', asset.state || '-'],
    ['Latitude', asset.lat.toFixed(4)],
    ['Longitude', asset.lng.toFixed(4)],
    ['Capacity', asset.capacity_mcm != null ? `${asset.capacity_mcm.toLocaleString()} MCM` : '-'],
    [
      'Current storage',
      `${(data?.current_storage_pct ?? asset.current_storage_pct)?.toFixed?.(1) ?? '-'}%`,
    ],
    [
      'Forecast storage',
      `${(data?.forecasted_storage_pct ?? asset.forecast_storage_pct)?.toFixed?.(1) ?? '-'}%`,
    ],
    ['Risk level', String(risk).toUpperCase()],
    [
      'Confidence',
      data?.confidence_score != null || asset.confidence != null
        ? `${Math.round(((data?.confidence_score ?? asset.confidence) as number) * 100)}%`
        : '-',
    ],
    ['Last updated', asset.last_updated ? new Date(asset.last_updated).toLocaleString() : '-'],
  ];

  return (
    <aside className="rounded-[var(--am-radius-xl)] bg-[var(--am-bg-elevated)] p-5 shadow-[var(--am-shadow-md)]">
      <div className="flex items-start justify-between gap-2">
        <div>
          <p className="text-[14px] font-semibold uppercase tracking-[0.06em] text-[var(--am-text-tertiary)]">
            Selected asset
          </p>
          <h3 className="mt-1 text-[18px] font-semibold tracking-tight text-[var(--am-text)]">{asset.name}</h3>
        </div>
        <Badge tone={tone === 'neutral' ? 'accent' : tone}>{String(risk)}</Badge>
      </div>
      <dl className="mt-4 space-y-2.5">
        {rows.map(([k, v]) => (
          <div key={k} className="flex items-start justify-between gap-3 text-[16px]">
            <dt className="text-[var(--am-text-secondary)]">{k}</dt>
            <dd className="text-right font-medium tabular-nums text-[var(--am-text)]">{v}</dd>
          </div>
        ))}
      </dl>
    </aside>
  );
}

export default ReservoirForecastPage;
