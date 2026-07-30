import React from 'react';
import { NotebookText } from 'lucide-react';

export type QuickSummaryProps = {
  title?: string;
  lines: string[];
  technicalNote?: string;
  className?: string;
};

/** Executive-readable summary at the top of prediction pages. */
export const QuickSummary: React.FC<QuickSummaryProps> = ({
  title = 'Quick Summary',
  lines,
  technicalNote,
  className = '',
}) => {
  const visible = (lines || []).filter(Boolean);
  if (!visible.length && !technicalNote) return null;

  return (
    <section
      className={`rounded-[16px] border border-[var(--am-border)] bg-[var(--am-bg-elevated)] px-5 py-4 shadow-[var(--am-shadow-sm)] ${className}`}
      aria-label={title}
    >
      <div className="flex items-start gap-3">
        <span className="mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-[var(--am-accent-soft)] text-[var(--am-accent)]">
          <NotebookText className="h-4 w-4" strokeWidth={2.25} aria-hidden />
        </span>
        <div className="min-w-0 flex-1">
          <h2 className="text-[16px] font-semibold uppercase tracking-[0.06em] text-[var(--am-text-secondary)]">
            {title}
          </h2>
          {visible.length ? (
            <ul className="mt-2 space-y-1.5">
              {visible.map((line) => (
                <li key={line} className="text-[17px] leading-snug text-[var(--am-text)]">
                  {line}
                </li>
              ))}
            </ul>
          ) : null}
          {technicalNote ? (
            <p className="mt-3 border-t border-[var(--am-divider)] pt-2.5 text-[15px] leading-relaxed text-[var(--am-text-tertiary)]">
              <span className="font-medium text-[var(--am-text-secondary)]">Technical: </span>
              {technicalNote}
            </p>
          ) : null}
        </div>
      </div>
    </section>
  );
};

export default QuickSummary;
