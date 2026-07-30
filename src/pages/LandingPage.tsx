import React, { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { motion } from 'framer-motion';
import {
  ArrowRight,
  CloudSun,
  Droplets,
  Eye,
  Gauge,
  ListChecks,
  TrendingUp,
} from 'lucide-react';
import { ThemeToggle } from '../components/common/ThemeToggle';
import { useTheme } from '../context/ThemeContext';

const FEATURES = [
  {
    title: 'Demand Forecast',
    desc: 'Predict future water demand before shortages happen.',
    impact: 'Gives utilities days of lead time to balance supply, avoid emergency rationing, and brief leadership with confidence.',
    icon: TrendingUp,
  },
  {
    title: 'Reservoir Forecast',
    desc: 'Track future storage levels across reservoirs.',
    impact: 'Shows which reservoirs may fall critical first so release schedules and contingency plans can be adjusted early.',
    icon: Droplets,
  },
  {
    title: 'Climate Risk',
    desc: 'Monitor rainfall, drought, flood, and weather conditions.',
    impact: 'Turns weather signals into operational risk, so teams prepare for drought, flood, and heat before they disrupt service.',
    icon: CloudSun,
  },
  {
    title: 'Water Stress',
    desc: 'View the overall health of your water system.',
    impact: 'One clear score for system pressure helps executives and engineers align on urgency without reading every chart.',
    icon: Gauge,
  },
  {
    title: 'Recommended Actions',
    desc: 'AI prioritizes the most important actions to take.',
    impact: 'Ranks what to do first, protecting people, reducing loss, and cutting response time when multiple risks compete.',
    icon: ListChecks,
  },
  {
    title: 'Satellite Insights',
    desc: 'Monitor reservoir health using satellite imagery.',
    impact: 'Adds visual evidence of shoreline change, vegetation, and inundation when ground sensors alone are not enough.',
    icon: Eye,
  },
] as const;

const HERO_POSTER = '/media/hero-water.jpg';

export const LandingPage: React.FC = () => {
  const { isLight } = useTheme();
  const [reduceMotion, setReduceMotion] = useState(false);

  useEffect(() => {
    const mq = window.matchMedia('(prefers-reduced-motion: reduce)');
    const sync = () => setReduceMotion(mq.matches);
    sync();
    mq.addEventListener('change', sync);
    return () => mq.removeEventListener('change', sync);
  }, []);

  return (
    <main className={`landing-page landing-enterprise ${isLight ? 'landing-light' : 'landing-dark'}`}>
      <header className="landing-nav landing-nav-over-hero">
        <Link to="/" className="landing-nav-brand">
          <img
            src="/logo-mark.png"
            alt=""
            width={32}
            height={32}
            className="landing-mark h-8 w-8 rounded-lg object-contain"
            decoding="async"
          />
          <span className="text-[17px] font-semibold tracking-tight">AquaMind AI</span>
        </Link>
        <div className="flex items-center gap-2 sm:gap-3">
          <ThemeToggle />
          <Link to="/login" className="landing-btn-ghost hidden sm:inline-flex">
            Sign in
          </Link>
          <Link to="/signup" className="landing-btn-primary">
            Open Platform
          </Link>
        </div>
      </header>

      <section className="landing-hero" aria-label="AquaMind AI hero">
        <div className="landing-hero-media" aria-hidden>
          <div
            className={`landing-hero-poster${reduceMotion ? '' : ' landing-hero-poster-drift'}`}
            style={{ backgroundImage: `url(${HERO_POSTER})` }}
          />
          <div className="landing-hero-wash" />
          {!reduceMotion ? <div className="landing-hero-caustic" /> : null}
        </div>

        <motion.div
          initial={{ opacity: 0, y: 12 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.45, ease: [0.16, 1, 0.3, 1] }}
          className="landing-hero-inner"
        >
          <p className="landing-brand-eyebrow">AquaMind AI</p>
          <h1 className="landing-headline-enterprise">
            Water Intelligence for Smarter Infrastructure Decisions
          </h1>
          <p className="landing-sub-enterprise">
            Monitor water demand, predict shortages, assess climate risks, and make faster
            operational decisions using AI-powered forecasting.
          </p>
          <div className="landing-frame-actions">
            <Link to="/signup" className="landing-btn-primary landing-btn-lg">
              Open Platform
              <ArrowRight className="h-4 w-4" aria-hidden />
            </Link>
            <a href="#capabilities" className="landing-btn-secondary landing-btn-lg">
              Learn More
            </a>
          </div>
        </motion.div>
      </section>

      <section id="capabilities" className="landing-features" aria-labelledby="capabilities-heading">
        <div className="landing-features-inner">
          <div className="landing-features-header">
            <div className="landing-features-intro">
              <p className="landing-section-eyebrow">Capabilities</p>
              <h2 id="capabilities-heading" className="landing-section-title">
                Everything operators need in one workspace
              </h2>
              <p className="landing-section-sub">
                Forecast demand and storage, assess climate risk, and prioritize actions without
                switching between disconnected tools.
              </p>
            </div>
            <Link to="/signup" className="landing-features-cta">
              Explore the platform
              <ArrowRight className="h-4 w-4" aria-hidden />
            </Link>
          </div>

          <ul className="landing-feature-grid">
            {FEATURES.map((item, i) => (
              <motion.li
                key={item.title}
                initial={{ opacity: 0, y: 14 }}
                whileInView={{ opacity: 1, y: 0 }}
                viewport={{ once: true, margin: '-60px' }}
                transition={{ delay: i * 0.05, duration: 0.4, ease: [0.16, 1, 0.3, 1] }}
                className="landing-feature-card"
              >
                <div className="landing-feature-card-top">
                  <span className="landing-capability-icon" aria-hidden>
                    <item.icon className="h-5 w-5" strokeWidth={1.75} />
                  </span>
                  <span className="landing-feature-index" aria-hidden>
                    {String(i + 1).padStart(2, '0')}
                  </span>
                </div>
                <h3>{item.title}</h3>
                <p className="landing-feature-desc">{item.desc}</p>
                <p className="landing-feature-impact">{item.impact}</p>
              </motion.li>
            ))}
          </ul>

          <div className="landing-trust-strip">
            <p>Built for government agencies, municipalities, utilities, and enterprise operators.</p>
            <div className="landing-trust-points" aria-label="Platform strengths">
              <span>Operational forecasts</span>
              <span>Climate situational awareness</span>
              <span>Action prioritization</span>
            </div>
          </div>
        </div>
      </section>

      <footer className="landing-footer">
        <p>AquaMind AI · Enterprise water intelligence for agencies and utilities</p>
        <p className="landing-footer-copy">© 2026 AquaMind AI. All rights reserved.</p>
      </footer>
    </main>
  );
};

export default LandingPage;
