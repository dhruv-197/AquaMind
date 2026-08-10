import React, { useEffect, useState } from 'react';
import { Check, Clock3, X } from 'lucide-react';
import { apiGet, apiPost } from '../../services/apiClient';

export type FeedbackAction = 'accepted' | 'rejected' | 'deferred';

type Props = {
  recommendationId: string;
  source?: 'decision' | 'stress' | 'policy';
  regionId?: string;
};

type FeedbackRow = {
  recommendation_id: string;
  action: FeedbackAction;
  note?: string | null;
  updated_at?: string;
  persisted?: boolean;
};

const LABELS: Record<FeedbackAction, string> = {
  accepted: 'Accepted',
  rejected: 'Rejected',
  deferred: 'Deferred',
};

export const RecommendationFeedbackControls: React.FC<Props> = ({
  recommendationId,
  source = 'decision',
  regionId,
}) => {
  const [current, setCurrent] = useState<FeedbackAction | null>(null);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState('');
  const [error, setError] = useState('');

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const res = await apiGet<{ success: boolean; data: FeedbackRow[] }>(
          `/api/v1/recommendations/feedback?recommendation_id=${encodeURIComponent(recommendationId)}`,
        );
        if (cancelled) return;
        const row = res.data?.[0];
        if (row?.action) setCurrent(row.action);
      } catch {
        // Feedback is optional — ignore load failures silently.
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [recommendationId]);

  const submit = async (action: FeedbackAction) => {
    setBusy(true);
    setError('');
    setMessage('');
    try {
      const res = await apiPost<{
        success: boolean;
        message: string;
        data: FeedbackRow;
        disclaimer?: string;
      }>('/api/v1/recommendations/feedback', {
        recommendation_id: recommendationId,
        action,
        source,
        region_id: regionId,
      });
      setCurrent(res.data.action);
      setMessage(
        `${LABELS[res.data.action]} saved. Intent only — measured savings are not claimed.`,
      );
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Could not save feedback.');
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="mt-2" data-testid={`rec-feedback-${recommendationId}`}>
      <p className="mb-1.5 text-[13px] font-semibold uppercase tracking-wide text-[var(--am-text-tertiary)]">
        Operator decision
      </p>
      <div className="flex flex-wrap gap-1.5" role="group" aria-label="Recommendation feedback">
        {(
          [
            ['accepted', Check, 'Accept'],
            ['rejected', X, 'Reject'],
            ['deferred', Clock3, 'Defer'],
          ] as const
        ).map(([action, Icon, label]) => {
          const active = current === action;
          return (
            <button
              key={action}
              type="button"
              disabled={busy}
              aria-pressed={active}
              aria-label={`${label} recommendation ${recommendationId}`}
              onClick={() => void submit(action)}
              className={`inline-flex items-center gap-1.5 rounded-[10px] border px-2.5 py-1.5 text-[14px] font-semibold transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--am-accent)] disabled:opacity-50 ${
                active
                  ? 'border-[var(--am-accent)] bg-[var(--am-accent-soft)] text-[var(--am-accent)]'
                  : 'border-[var(--am-border)] bg-[var(--am-bg-muted)] text-[var(--am-text-secondary)] hover:bg-[var(--am-bg-hover)]'
              }`}
            >
              <Icon className="h-3.5 w-3.5" aria-hidden />
              {label}
            </button>
          );
        })}
      </div>
      {message ? (
        <p className="mt-1.5 text-[13px] text-[var(--am-text-tertiary)]" role="status">
          {message}
        </p>
      ) : null}
      {error ? (
        <p className="mt-1.5 text-[13px] text-[var(--am-danger)]" role="alert">
          {error}
        </p>
      ) : null}
    </div>
  );
};
