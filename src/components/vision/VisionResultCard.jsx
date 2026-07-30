import React, { useMemo } from 'react';
import { Lightbulb, TrendingDown, TrendingUp, Minus } from 'lucide-react';
import { VisionImageViewer } from './VisionImageViewer';
import { StatusBadge } from '../ui/Badge';
import { Button } from '../ui/Button';

function classById(classes, idPart) {
  return (classes || []).find((c) => String(c.id || c.label || '').toLowerCase().includes(idPart));
}

/** Strip vendor / model product names from customer-facing copy. */
function sanitizeVendorCopy(text) {
  if (text == null || text === '') return text;
  return String(text)
    .replace(/Gemini\s*Vision\s*\+\s*CLIPSeg/gi, 'AquaLens vision analysis')
    .replace(/CLIPSag/gi, 'Zero shot image segmentation')
    .replace(/CLIPSeg/gi, 'Zero shot image segmentation')
    .replace(/clipseg/gi, 'zero shot image segmentation')
    .replace(/Gemini(\s+Vision)?/gi, 'LLM')
    .replace(/\bvlm\s*\+\s*clipseg\b/gi, 'vision + zero shot image segmentation')
    .replace(/\bvlm\b/gi, 'vision analysis')
    .replace(/\s{2,}/g, ' ')
    .trim();
}

function pct(value) {
  if (value == null || Number.isNaN(Number(value))) return null;
  return Number(value);
}

function formatPct(value, digits = 0) {
  const n = pct(value);
  if (n == null) return '-';
  return `${n.toFixed(digits)}%`;
}

function formatDelta(value) {
  const n = pct(value);
  if (n == null) return null;
  const sign = n > 0 ? '+' : '';
  return `${sign}${n.toFixed(0)}%`;
}

export const VisionResultCard = ({ result, originalPreview }) => {
  const data = result?.data || result || {};
  const assetLabel = result?.asset_label || null;
  const comparison = result?.comparison || null;

  const segmentation = data.segmentation || result?.segmentation || null;
  const overlaySrc = segmentation?.overlay_base64
    ? `data:image/png;base64,${segmentation.overlay_base64}`
    : null;
  const segOriginalSrc = segmentation?.original_base64
    ? `data:image/png;base64,${segmentation.original_base64}`
    : originalPreview;

  const imageSrc = overlaySrc || segOriginalSrc || originalPreview;

  const visionMode = result?.vision_mode || data.vision_mode || 'reservoir';
  const isFlood = visionMode === 'flood';
  const guidance = segmentation?.guidance || null;
  const segClasses = segmentation?.classes || [];
  const waterCls = classById(segClasses, 'water');
  const vegCls = classById(segClasses, 'veg') || classById(segClasses, 'green');
  const floodCls =
    classById(segClasses, 'flood') || classById(segClasses, 'inundat') || classById(segClasses, 'mud');

  const coverageRows = useMemo(() => {
    if (segClasses.length) {
      return segClasses.map((cls) => ({
        id: cls.id || cls.label,
        label: cls.label || cls.id || 'Class',
        color: cls.color || 'var(--am-accent)',
        coverage:
          cls.coverage_pct != null
            ? Number(cls.coverage_pct)
            : cls.score != null
              ? Number(cls.score) * 100
              : null,
      }));
    }
    if (isFlood && guidance) {
      return [
        {
          id: 'permanent',
          label: 'Permanent water',
          color: '#0284c7',
          coverage: pct(guidance.permanent_water_pct),
        },
        {
          id: 'flood',
          label: 'Flooded land',
          color: '#c2410c',
          coverage: pct(guidance.flood_inundation_pct),
        },
      ].filter((r) => r.coverage != null);
    }
    return [
      waterCls && {
        id: 'water',
        label: 'Water',
        color: waterCls.color || '#0284c7',
        coverage: waterCls.coverage_pct ?? (waterCls.score != null ? waterCls.score * 100 : null),
      },
      vegCls && {
        id: 'vegetation',
        label: 'Vegetation',
        color: vegCls.color || '#16a34a',
        coverage: vegCls.coverage_pct ?? (vegCls.score != null ? vegCls.score * 100 : null),
      },
      floodCls && {
        id: 'flood',
        label: 'Flood inundation',
        color: floodCls.color || '#c2410c',
        coverage: floodCls.coverage_pct ?? (floodCls.score != null ? floodCls.score * 100 : null),
      },
    ].filter(Boolean);
  }, [segClasses, isFlood, guidance, waterCls, vegCls, floodCls]);

  if (!result) return null;

  const parsedHealth = Number(data.reservoir_health);
  const healthScore = Number.isFinite(parsedHealth) ? parsedHealth : null;
  const overallRisk = data.overall_risk ?? data.overall_flood_risk ?? 'Unknown';
  const summary = sanitizeVendorCopy(data.summary ?? 'No visual summary returned.');
  const recommendations =
    Array.isArray(data.recommendations) && data.recommendations.length
      ? data.recommendations.map((r) => sanitizeVendorCopy(String(r)))
      : [];

  const healthDelta = comparison?.reservoir_health_delta;
  const changeCards = [
    healthDelta != null && {
      label: 'Health change',
      value: `${healthDelta > 0 ? '+' : ''}${healthDelta}`,
      suffix: 'pts',
      tone: comparison?.trend,
    },
    comparison?.water_spread_delta_pct != null && {
      label: 'Water spread change',
      value: formatDelta(comparison.water_spread_delta_pct),
      tone: comparison.trend,
    },
    data.shoreline_exposure_pct != null && {
      label: 'Shoreline exposure',
      value: formatPct(data.shoreline_exposure_pct),
      tone: 'neutral',
    },
    healthScore != null && {
      label: 'Current health',
      value: String(healthScore),
      suffix: '/100',
      tone: 'neutral',
    },
    !isFlood && data.water_spread != null && {
      label: 'Water spread',
      value: String(data.water_spread),
      tone: 'neutral',
    },
    isFlood && guidance?.flood_inundation_pct != null && {
      label: 'Flooded land',
      value: formatPct(guidance.flood_inundation_pct),
      tone: Number(guidance.flood_inundation_pct) > 10 ? 'degrading' : 'neutral',
    },
  ].filter(Boolean);

  const exportJson = () => {
    const { provider: _p, analysis_mode: _m, ...safeData } = data;
    const blob = new Blob(
      [
        JSON.stringify(
          {
            vision_mode: visionMode,
            segmentation: segmentation?.available ? 'Zero shot image segmentation' : 'Unavailable',
            ...safeData,
          },
          null,
          2,
        ),
      ],
      { type: 'application/json' },
    );
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `aquavision-${visionMode}-${Date.now()}.json`;
    a.click();
    URL.revokeObjectURL(url);
  };

  return (
    <div className="space-y-5 animate-fade-in">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <h2 className="am-section-title text-[22px]">
            {isFlood ? 'Flood inundation result' : 'Reservoir segmentation result'}
          </h2>
          <p className="mt-1 text-[16px] text-[var(--am-text-secondary)]">
            Segmented imagery with coverage and change percentages
            {assetLabel ? ` · ${assetLabel}` : ''}
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <StatusBadge status={isFlood ? 'Flood mode' : 'Reservoir mode'} kind={isFlood ? 'high' : 'ready'} />
          <StatusBadge
            status={segmentation?.available ? 'Zero shot image segmentation' : 'Preview only'}
            kind={segmentation?.available ? 'ready' : 'neutral'}
          />
          <Button variant="secondary" size="sm" onClick={exportJson}>
            Export JSON
          </Button>
        </div>
      </div>

      {comparison ? (
        <div
          className={`flex items-start gap-3 rounded-[16px] border p-4 text-[16px] ${
            comparison.trend === 'improving'
              ? 'border-[var(--am-success)]/25 bg-[var(--am-success-soft)] text-[var(--am-success)]'
              : comparison.trend === 'degrading'
                ? 'border-[var(--am-danger)]/25 bg-[var(--am-danger-soft)] text-[var(--am-danger)]'
                : 'border-[var(--am-border)] bg-[var(--am-bg-muted)] text-[var(--am-text-secondary)]'
          }`}
        >
          {comparison.trend === 'improving' ? (
            <TrendingUp className="mt-0.5 h-4 w-4 shrink-0" aria-hidden />
          ) : comparison.trend === 'degrading' ? (
            <TrendingDown className="mt-0.5 h-4 w-4 shrink-0" aria-hidden />
          ) : (
            <Minus className="mt-0.5 h-4 w-4 shrink-0" aria-hidden />
          )}
          <div>
            <p className="font-semibold">
              {healthDelta != null
                ? `Health ${healthDelta > 0 ? '+' : ''}${healthDelta} vs previous scan (${comparison.trend})`
                : `Trend: ${comparison.trend}`}
            </p>
            {comparison.note ? (
              <p className="mt-1 opacity-90">{sanitizeVendorCopy(comparison.note)}</p>
            ) : null}
          </div>
        </div>
      ) : assetLabel ? (
        <div className="rounded-[16px] border border-[var(--am-border)] bg-[var(--am-bg-muted)]/50 p-4 text-[16px] text-[var(--am-text-secondary)]">
          First recorded scan for <strong>{assetLabel}</strong>. Future uploads with this label will show
          percentage change here.
        </div>
      ) : null}

      {changeCards.length > 0 ? (
        <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
          {changeCards.map((card) => (
            <div
              key={card.label}
              className="rounded-[16px] border border-[var(--am-border)] bg-[var(--am-bg-elevated)] p-4 shadow-[var(--am-shadow-sm)]"
            >
              <p className="text-[14px] font-semibold uppercase tracking-wide text-[var(--am-text-tertiary)]">
                {card.label}
              </p>
              <p
                className={`mt-2 text-[24px] font-semibold tabular-nums tracking-tight ${
                  card.tone === 'improving'
                    ? 'text-[var(--am-success)]'
                    : card.tone === 'degrading'
                      ? 'text-[var(--am-danger)]'
                      : 'text-[var(--am-text)]'
                }`}
              >
                {card.value}
                {card.suffix ? (
                  <span className="ml-1 text-[16px] font-medium text-[var(--am-text-tertiary)]">
                    {card.suffix}
                  </span>
                ) : null}
              </p>
            </div>
          ))}
        </div>
      ) : null}

      <div className="grid gap-4 xl:grid-cols-12">
        <section className="am-soft-card space-y-4 p-4 sm:p-5 xl:col-span-8">
          <div>
            <h3 className="text-[17px] font-semibold text-[var(--am-text)]">Segmented image</h3>
            <p className="mt-0.5 text-[15px] text-[var(--am-text-secondary)]">
              {segmentation?.available
                ? 'Zero shot image segmentation overlay · zoom, pan, and fullscreen available'
                : 'Uploaded scene preview · segmentation overlay unavailable for this scan'}
            </p>
          </div>
          <VisionImageViewer src={imageSrc} alt="Segmented AquaLens imagery" />
        </section>

        <aside className="space-y-4 xl:col-span-4">
          <section className="am-soft-card p-4 sm:p-5">
            <h3 className="text-[17px] font-semibold text-[var(--am-text)]">Coverage percentages</h3>
            <p className="mt-0.5 text-[15px] text-[var(--am-text-secondary)]">
              Share of the scene by detected class
            </p>
            {coverageRows.length ? (
              <ul className="mt-4 space-y-3">
                {coverageRows.map((row) => (
                  <li key={row.id}>
                    <div className="mb-1.5 flex items-center justify-between gap-2">
                      <span className="inline-flex items-center gap-2 text-[16px] font-medium text-[var(--am-text)]">
                        <span
                          className="h-2.5 w-2.5 rounded-sm"
                          style={{ backgroundColor: row.color }}
                          aria-hidden
                        />
                        {row.label}
                      </span>
                      <span className="text-[17px] font-semibold tabular-nums text-[var(--am-text)]">
                        {formatPct(row.coverage)}
                      </span>
                    </div>
                    <div className="h-2 overflow-hidden rounded-full bg-[var(--am-bg-muted)]">
                      <div
                        className="h-full rounded-full transition-all duration-500"
                        style={{
                          width: `${Math.max(0, Math.min(100, row.coverage ?? 0))}%`,
                          background: row.color,
                        }}
                      />
                    </div>
                  </li>
                ))}
              </ul>
            ) : (
              <p className="mt-4 text-[16px] text-[var(--am-text-tertiary)]">
                No coverage percentages available for this scan.
              </p>
            )}
            <p className="mt-4 border-t border-[var(--am-divider)] pt-3 text-[15px] text-[var(--am-text-tertiary)]">
              Overall risk: <span className="font-semibold text-[var(--am-text)]">{overallRisk}</span>
            </p>
          </section>

          <section className="am-soft-card p-4 sm:p-5">
            <h3 className="text-[17px] font-semibold text-[var(--am-text)]">Quick summary</h3>
            <p className="mt-2 text-[16px] leading-relaxed text-[var(--am-text-secondary)]">{summary}</p>
          </section>
        </aside>
      </div>

      {recommendations.length > 0 ? (
        <section className="am-soft-card p-5">
          <div className="mb-3 flex items-center gap-2">
            <Lightbulb className="h-4 w-4 text-[var(--am-accent)]" aria-hidden />
            <h3 className="text-[17px] font-semibold text-[var(--am-text)]">Recommended next steps</h3>
          </div>
          <ul className="grid gap-2 md:grid-cols-2">
            {recommendations.slice(0, 4).map((rec, idx) => (
              <li
                key={`${idx}-${String(rec).slice(0, 24)}`}
                className="rounded-[14px] border border-[var(--am-border)] bg-[var(--am-bg-muted)]/70 px-3.5 py-3 text-[16px] text-[var(--am-text)]"
              >
                {rec}
              </li>
            ))}
          </ul>
        </section>
      ) : null}
    </div>
  );
};

export default VisionResultCard;
