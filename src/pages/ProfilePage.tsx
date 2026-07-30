import React, { useMemo } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { GlassCard } from '../components/common/GlassCard';
import { useTheme } from '../context/ThemeContext';
import {
  User,
  Shield,
  Building2,
  Mail,
  LogOut,
  Settings,
  BadgeCheck,
} from 'lucide-react';

function clearSession() {
  localStorage.removeItem('access_token');
  localStorage.removeItem('user_role');
  localStorage.removeItem('username');
  localStorage.removeItem('user_email');
}

function initialsFrom(name: string, email: string): string {
  const source = (name || email || 'U').trim();
  const parts = source.split(/[\s@_./-]+/).filter(Boolean);
  if (parts.length >= 2) return (parts[0][0] + parts[1][0]).toUpperCase();
  return source.slice(0, 2).toUpperCase();
}

export const ProfilePage: React.FC = () => {
  const navigate = useNavigate();
  const { isLight } = useTheme();

  const account = useMemo(() => {
    const username = localStorage.getItem('username') || 'Admin';
    const email = localStorage.getItem('user_email') || 'admin@centralvalleywater.gov';
    const role = (localStorage.getItem('user_role') || 'admin').toLowerCase();
    return {
      username,
      email,
      role,
      roleLabel: role === 'admin' ? 'Administrator' : role.charAt(0).toUpperCase() + role.slice(1),
      initials: initialsFrom(username, email),
    };
  }, []);

  const handleLogout = () => {
    clearSession();
    navigate('/login', { replace: true });
  };

  const panel = isLight
    ? 'bg-white border border-slate-200 shadow-sm'
    : 'bg-slate-900/40 border border-slate-800/80 backdrop-blur-xl';
  const title = isLight ? 'text-slate-900' : 'text-white';
  const muted = isLight ? 'text-slate-500' : 'text-slate-400';
  const row = isLight ? 'text-slate-700' : 'text-slate-300';

  return (
    <div className="space-y-6">
      <div className={`rounded-2xl p-6 flex flex-col sm:flex-row sm:items-center gap-4 ${panel}`}>
        <div
          className={`w-16 h-16 rounded-2xl flex items-center justify-center font-bold text-xl text-white border shrink-0 ${
            isLight
              ? 'bg-sky-600 border-sky-500'
              : 'bg-gradient-to-br from-blue-600 to-cyan-500 border-cyan-400/40 shadow-[0_0_20px_rgba(6,182,212,0.3)]'
          }`}
        >
          {account.initials}
        </div>
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <h1 className={`text-2xl font-bold truncate ${title}`}>{account.username}</h1>
            <span
              className={`text-[16px] font-mono uppercase px-2 py-0.5 rounded border ${
                isLight
                  ? 'bg-emerald-50 text-emerald-700 border-emerald-200'
                  : 'bg-emerald-500/15 text-emerald-300 border-emerald-500/30'
              }`}
            >
              Signed in
            </span>
          </div>
          <p className={`text-[14px] font-mono mt-0.5 ${isLight ? 'text-sky-700' : 'text-cyan-400'}`}>
            Central Valley Water Utility · {account.roleLabel}
          </p>
          <p className={`text-[14px] mt-1 ${muted}`}>
            Account details from your login session (local JWT). Profile edit API not required for this pilot.
          </p>
        </div>
        <div className="flex flex-wrap gap-2 shrink-0">
          <Link
            to="/settings"
            className={`inline-flex items-center gap-1.5 rounded-lg px-3 py-2 text-[14px] font-semibold border transition-colors ${
              isLight
                ? 'bg-slate-50 border-slate-200 text-slate-700 hover:bg-slate-100'
                : 'bg-slate-950/50 border-slate-700 text-slate-200 hover:border-cyan-500/40'
            }`}
          >
            <Settings className="w-3.5 h-3.5" /> Settings
          </Link>
          <button
            type="button"
            onClick={handleLogout}
            className={`inline-flex items-center gap-1.5 rounded-lg px-3 py-2 text-[14px] font-semibold border transition-colors ${
              isLight
                ? 'bg-red-50 border-red-200 text-red-700 hover:bg-red-100'
                : 'bg-red-950/40 border-red-800/50 text-red-300 hover:border-red-500/50'
            }`}
          >
            <LogOut className="w-3.5 h-3.5" /> Sign out
          </button>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        <GlassCard>
          <h2 className={`text-[15px] font-bold mb-4 flex items-center gap-2 ${title}`}>
            <User className={`w-4 h-4 ${isLight ? 'text-sky-600' : 'text-cyan-400'}`} /> Account identity
          </h2>
          <div className={`space-y-3 text-[14px] ${row}`}>
            <div className="flex items-center gap-3">
              <Mail className={`w-4 h-4 shrink-0 ${muted}`} />
              <span className="truncate">{account.email}</span>
            </div>
            <div className="flex items-center gap-3">
              <Building2 className={`w-4 h-4 shrink-0 ${muted}`} />
              <span>Department of Municipal Infrastructure</span>
            </div>
            <div className="flex items-center gap-3">
              <Shield className={`w-4 h-4 shrink-0 ${muted}`} />
              <span className="capitalize">{account.roleLabel} access</span>
            </div>
          </div>
        </GlassCard>

        <GlassCard>
          <h2 className={`text-[15px] font-bold mb-4 flex items-center gap-2 ${title}`}>
            <BadgeCheck className={`w-4 h-4 ${isLight ? 'text-sky-600' : 'text-cyan-400'}`} /> Session
          </h2>
          <dl className="space-y-3 text-[14px]">
            <div className="flex justify-between gap-3">
              <dt className={muted}>Auth</dt>
              <dd className={`font-mono ${row}`}>JWT (local)</dd>
            </div>
            <div className="flex justify-between gap-3">
              <dt className={muted}>Role</dt>
              <dd className={`font-mono capitalize ${row}`}>{account.role}</dd>
            </div>
            <div className="flex justify-between gap-3">
              <dt className={muted}>Workspace</dt>
              <dd className={`font-mono ${row}`}>AquaMind pilot</dd>
            </div>
          </dl>
          <p className={`mt-4 text-[14px] leading-relaxed ${muted}`}>
            Demo mode only: this deployment seeded a pilot login (
            <span className="font-mono">admin@centralvalleywater.gov</span> /{' '}
            <span className="font-mono">password123</span>). Seeding is disabled automatically
            outside a development environment (<span className="font-mono">AQUAMIND_ENVIRONMENT=production</span>).
          </p>
        </GlassCard>
      </div>
    </div>
  );
};
