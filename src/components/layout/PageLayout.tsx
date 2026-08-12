import React, { useEffect, useMemo, useRef, useState } from 'react';
import { Link, useLocation, useNavigate } from 'react-router-dom';
import { AnimatePresence, motion } from 'framer-motion';
import {
  LayoutGrid,
  Satellite,
  CloudRain,
  AudioLines,
  ChartSpline,
  Waves,
  ListChecks,
  Bell,
  Settings,
  LogOut,
  CircleGauge,
  PanelLeftClose,
  PanelLeft,
} from 'lucide-react';
import { loadAlerts } from '../../services/telemetry';
import { ThemeToggle } from '../common/ThemeToggle';
import { BrandLogo } from '../common/BrandLogo';
import { WaterCopilot } from '../copilot/WaterCopilot';
import { IconButton } from '../ui/IconButton';

interface PageLayoutProps {
  children: React.ReactNode;
}

const SIDEBAR_KEY = 'aquamind-sidebar-collapsed';

function clearSession() {
  localStorage.removeItem('access_token');
  localStorage.removeItem('user_role');
  localStorage.removeItem('username');
  localStorage.removeItem('user_email');
}

function profileInitials(): string {
  const username = localStorage.getItem('username') || '';
  const email = localStorage.getItem('user_email') || '';
  const source = (username || email || 'GO').trim();
  const parts = source.split(/[\s@_./-]+/).filter(Boolean);
  if (parts.length >= 2) return (parts[0][0] + parts[1][0]).toUpperCase();
  return source.slice(0, 2).toUpperCase() || 'GO';
}

const navItems = [
  { path: '/dashboard', label: 'Dashboard', icon: LayoutGrid },
  { path: '/water-stress', label: 'Water Stress', icon: CircleGauge },
  { path: '/leak-detection', label: 'Leak Detection', icon: AudioLines },
  { path: '/demand', label: 'Demand Forecast', icon: ChartSpline },
  { path: '/reservoir-forecast', label: 'Reservoir Forecast', icon: Waves },
  { path: '/decision-intelligence', label: 'Recommended Actions', icon: ListChecks },
  { path: '/climate-risk', label: 'Climate Risk', icon: CloudRain },
  { path: '/vision-analysis', label: 'AquaLens', icon: Satellite },
] as const;

export const PageLayout: React.FC<PageLayoutProps> = ({ children }) => {
  const location = useLocation();
  const navigate = useNavigate();
  const [activeAlertCount, setActiveAlertCount] = useState(0);
  const [collapsed, setCollapsed] = useState(() => {
    if (typeof window === 'undefined') return false;
    return localStorage.getItem(SIDEBAR_KEY) === '1';
  });
  const avatarLabel = useMemo(() => profileInitials(), [location.pathname]);
  const mainRef = useRef<HTMLElement>(null);

  useEffect(() => {
    // Page content scrolls inside <main>, not the window — reset on every route change.
    mainRef.current?.scrollTo({ top: 0, left: 0, behavior: 'auto' });
    window.scrollTo({ top: 0, left: 0, behavior: 'auto' });
  }, [location.pathname]);

  useEffect(() => {
    localStorage.setItem(SIDEBAR_KEY, collapsed ? '1' : '0');
  }, [collapsed]);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const alerts = await loadAlerts();
        if (cancelled) return;
        setActiveAlertCount(alerts.filter((a) => a.status === 'active' || a.severity === 'critical').length);
      } catch {
        if (!cancelled) setActiveAlertCount(0);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [location.pathname]);

  return (
    <>
    <div className="app-shell flex h-dvh max-h-dvh flex-col overflow-hidden font-sans text-[var(--am-text)]">
      <header className="app-header sticky top-0 z-40 flex h-14 shrink-0 items-center justify-between gap-4 border-b border-[var(--am-border)] bg-[var(--am-bg-elevated)]/90 px-4 backdrop-blur-xl sm:px-6">
        <div className="flex min-w-0 items-center gap-3">
          <IconButton
            label={collapsed ? 'Expand sidebar' : 'Collapse sidebar'}
            onClick={() => setCollapsed((c) => !c)}
            className="hidden lg:inline-flex"
          >
            {collapsed ? <PanelLeft className="h-4 w-4" /> : <PanelLeftClose className="h-4 w-4" />}
          </IconButton>
          <BrandLogo size="md" />
        </div>

        <div className="flex items-center gap-1.5 sm:gap-2">
          <ThemeToggle />

          <Link to="/alerts" className="relative">
            <IconButton label={`${activeAlertCount} active alerts`} active={location.pathname === '/alerts'}>
              <Bell className="h-4 w-4" />
            </IconButton>
            {activeAlertCount > 0 ? (
              <span className="absolute -right-0.5 -top-0.5 flex h-4 min-w-4 items-center justify-center rounded-full bg-[var(--am-danger)] px-1 text-[15px] font-bold text-white">
                {activeAlertCount > 99 ? '99+' : activeAlertCount}
              </span>
            ) : null}
          </Link>

          <Link to="/settings">
            <IconButton label="Settings" active={location.pathname === '/settings'}>
              <Settings className="h-4 w-4" />
            </IconButton>
          </Link>

          <Link
            to="/profile"
            title="Account"
            className="ml-1 flex h-8 w-8 items-center justify-center rounded-full bg-[var(--am-accent)] text-[14px] font-bold text-white shadow-[var(--am-shadow-sm)] transition-transform duration-200 hover:scale-[1.03]"
          >
            {avatarLabel}
          </Link>

          <IconButton
            label="Sign out"
            onClick={() => {
              clearSession();
              navigate('/login', { replace: true });
            }}
            className="text-[var(--am-text-tertiary)] hover:text-[var(--am-danger)]"
          >
            <LogOut className="h-4 w-4" />
          </IconButton>
        </div>
      </header>

      <div className="flex min-h-0 flex-1 overflow-hidden">
        <aside
          className={`app-sidebar flex shrink-0 flex-col border-[var(--am-border)] bg-[var(--am-bg-elevated)] transition-[width] duration-200 ease-[cubic-bezier(0.25,0.1,0.25,1)] ${
            collapsed ? 'lg:w-[72px]' : 'lg:w-[240px]'
          } w-full border-b lg:h-full lg:border-b-0 lg:border-r`}
        >
          <div className={`hidden px-4 pb-2 pt-4 lg:block ${collapsed ? 'px-2 text-center' : ''}`}>
            <p className="text-[14px] font-semibold uppercase tracking-[0.08em] text-[var(--am-text-tertiary)]">
              {collapsed ? 'Nav' : 'Navigation'}
            </p>
          </div>

          <nav className="flex gap-1 overflow-x-auto p-2 scrollbar-none lg:flex-col lg:overflow-y-auto lg:overflow-x-hidden">
            {navItems.map((item) => {
              const Icon = item.icon;
              const isActive = location.pathname === item.path;
              return (
                <Link
                  key={item.path}
                  to={item.path}
                  title={item.label}
                  className={`am-nav-item relative flex items-center gap-3 rounded-xl px-3 py-2.5 text-[16px] font-medium transition-colors duration-200 ${
                    collapsed ? 'lg:justify-center lg:px-2' : ''
                  } ${
                    isActive
                      ? 'text-[var(--am-accent)]'
                      : 'text-[var(--am-text-secondary)] hover:bg-[var(--am-bg-muted)] hover:text-[var(--am-text)]'
                  }`}
                >
                  {isActive ? (
                    <motion.span
                      layoutId="nav-active"
                      className="absolute inset-0 rounded-xl bg-[var(--am-accent-soft)]"
                      transition={{ duration: 0.2, ease: [0.25, 0.1, 0.25, 1] }}
                    />
                  ) : null}
                  <Icon className="relative z-10 h-[18px] w-[18px] shrink-0" strokeWidth={isActive ? 2.35 : 2} />
                  <span className={`relative z-10 truncate ${collapsed ? 'lg:hidden' : ''}`}>{item.label}</span>
                </Link>
              );
            })}
          </nav>

          <div className="mt-auto hidden border-t border-[var(--am-border)] p-3 lg:block">
            <p
              className={`text-[14px] leading-relaxed text-[var(--am-text-tertiary)] ${
                collapsed ? 'text-center' : 'px-1'
              }`}
            >
              {collapsed ? 'AM' : 'AquaMind AI'}
            </p>
          </div>
        </aside>

        <main
          ref={mainRef}
          className="mx-auto min-h-0 w-full max-w-[1600px] flex-1 overflow-y-auto px-4 py-4 sm:px-6 sm:py-5 lg:px-7 lg:py-6"
        >
          <AnimatePresence mode="wait">
            <motion.div
              key={location.pathname}
              initial={{ opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -6 }}
              transition={{ duration: 0.2, ease: [0.25, 0.1, 0.25, 1] }}
            >
              {children}
            </motion.div>
          </AnimatePresence>
        </main>
      </div>
    </div>
      <WaterCopilot />
    </>
  );
};
