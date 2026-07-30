import React from 'react';
import { Link } from 'react-router-dom';
import { ArrowUpRight } from 'lucide-react';
import { Badge } from '../../ui/Badge';
import { SectionTitle } from './ExecutiveKpis';
import type { PredictionCard } from './derive';

type Props = { cards: PredictionCard[] };

export const PredictionCenter: React.FC<Props> = ({ cards }) => (
  <section>
    <SectionTitle
      title="Prediction Center"
      subtitle="Summarized model outlooks. Open any module for full workspace depth."
    />
    <div className="mt-4 grid grid-cols-1 gap-3 md:grid-cols-2 xl:grid-cols-5">
      {cards.map((c) => (
        <article
          key={c.id}
          className="flex flex-col rounded-[var(--am-radius-xl)] bg-[var(--am-bg-elevated)] p-4 shadow-[var(--am-shadow-md)] transition-shadow duration-200 hover:shadow-[var(--am-shadow-hover)]"
        >
          <div className="flex items-start justify-between gap-2">
            <h3 className="text-[16px] font-semibold text-[var(--am-text)]">{c.title}</h3>
            <Badge tone={c.tone === 'neutral' ? 'accent' : c.tone}>{c.confidence}</Badge>
          </div>
          <p className="mt-3 text-[22px] font-semibold tracking-[-0.02em] tabular-nums text-[var(--am-text)]">
            {c.current}
          </p>
          <p className="mt-1 text-[15px] text-[var(--am-text-secondary)]">{c.trend}</p>
          <Link
            to={c.href}
            className="mt-auto inline-flex items-center gap-1 pt-4 text-[15px] font-semibold text-[var(--am-accent)] hover:underline"
          >
            Open module <ArrowUpRight className="h-3.5 w-3.5" />
          </Link>
        </article>
      ))}
    </div>
  </section>
);
