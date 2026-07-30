import React, { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { Lock, Mail, ArrowRight, AlertCircle, Info } from 'lucide-react';
import { authService } from '../services/auth';
import { BrandLogo } from '../components/common/BrandLogo';
import { useTheme } from '../context/ThemeContext';
import { ThemeToggle } from '../components/common/ThemeToggle';

export const LoginPage: React.FC = () => {
  const navigate = useNavigate();
  const { isLight } = useTheme();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setIsLoading(true);

    try {
      const res = await authService.login(email, password);
      if (res.success && res.data) {
        localStorage.setItem('access_token', res.data.access_token);
        localStorage.setItem('user_role', res.data.role);
        localStorage.setItem('username', res.data.username);
        localStorage.setItem('user_email', res.data.email);
        navigate('/dashboard');
      } else {
        setError(res.message || 'Authentication failed.');
      }
    } catch (err: any) {
      setError(err.message || 'An error occurred during authentication.');
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div
      className={`min-h-screen flex items-center justify-center p-6 ${
        isLight
          ? 'bg-[linear-gradient(180deg,#f8fafc_0%,#eef2f7_100%)] text-slate-800'
          : 'bg-slate-950 text-slate-100 selection:bg-cyan-500/30'
      }`}
    >
      <div className="absolute top-4 right-4">
        <ThemeToggle />
      </div>
      <div className="w-full max-w-md space-y-6">
        <div className="text-center space-y-3">
          <BrandLogo size="lg" stacked to="/" className="mx-auto" />
          <h1 className={`text-xl font-extrabold pt-2 ${isLight ? 'text-slate-900' : 'text-white'}`}>
            Login
          </h1>
        </div>

        <div
          className={`rounded-xl p-3 flex items-start gap-2.5 text-[14px] border ${
            isLight
              ? 'bg-cyan-50 border-cyan-200 text-cyan-800'
              : 'bg-cyan-500/10 border-cyan-500/30 text-cyan-300'
          }`}
        >
          <Info className="w-4 h-4 shrink-0 mt-0.5" />
          <span>
            Demo mode. Seeded pilot login: <b>admin@centralvalleywater.gov</b> / <b>password123</b>.
            This account only exists in local/development environments.
          </span>
        </div>

        {error && (
          <div
            className={`rounded-xl p-3 flex items-start gap-2.5 text-[14px] border ${
              isLight
                ? 'bg-red-50 border-red-200 text-red-700'
                : 'bg-red-500/10 border-red-500/30 text-red-400'
            }`}
          >
            <AlertCircle className="w-4.5 h-4.5 shrink-0 mt-0.5" />
            <span>{error}</span>
          </div>
        )}

        <form
          onSubmit={handleLogin}
          className={`p-6 rounded-2xl space-y-4 border ${
            isLight
              ? 'bg-white border-slate-200 shadow-lg shadow-slate-200/60'
              : 'bg-slate-900/50 border-slate-800 backdrop-blur-xl'
          }`}
        >
          <div>
            <label
              className={`text-[14px] font-semibold block mb-1.5 ${
                isLight ? 'text-slate-700' : 'text-slate-300'
              }`}
            >
              Government / Utility Email
            </label>
            <div className="relative">
              <Mail className={`w-4 h-4 absolute left-3 top-3 ${isLight ? 'text-slate-500' : 'text-slate-500'}`} />
              <input
                type="email"
                required
                placeholder="admin@utility.gov"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                className={`w-full pl-9 pr-3 py-2.5 rounded-xl text-[14px] focus:outline-none focus:ring-2 focus:ring-cyan-500/40 ${
                  isLight
                    ? 'bg-slate-50 border border-slate-300 text-slate-900 placeholder:text-slate-400'
                    : 'bg-slate-950 border border-slate-800 text-white'
                }`}
              />
            </div>
          </div>

          <div>
            <div className="flex items-center justify-between mb-1.5">
              <label className={`text-[14px] font-semibold ${isLight ? 'text-slate-700' : 'text-slate-300'}`}>
                Password
              </label>
              <Link
                to="/forgot-password"
                className={`text-[16px] font-semibold hover:underline ${
                  isLight ? 'text-cyan-700' : 'text-cyan-400'
                }`}
              >
                Forgot Password?
              </Link>
            </div>
            <div className="relative">
              <Lock className="w-4 h-4 text-slate-500 absolute left-3 top-3" />
              <input
                type="password"
                required
                placeholder="••••••••••••"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className={`w-full pl-9 pr-3 py-2.5 rounded-xl text-[14px] focus:outline-none focus:ring-2 focus:ring-cyan-500/40 ${
                  isLight
                    ? 'bg-slate-50 border border-slate-300 text-slate-900 placeholder:text-slate-400'
                    : 'bg-slate-950 border border-slate-800 text-white'
                }`}
              />
            </div>
          </div>

          <button
            type="submit"
            disabled={isLoading}
            className="w-full py-2.5 rounded-xl bg-cyan-600 text-white font-bold text-[14px] hover:bg-cyan-500 transition-colors flex items-center justify-center gap-2 disabled:opacity-60"
          >
            {isLoading ? 'Authenticating...' : 'Authenticate & Access Portal'} <ArrowRight className="w-4 h-4" />
          </button>
        </form>

        <p className={`text-center text-[14px] ${isLight ? 'text-slate-600' : 'text-slate-500'}`}>
          Don&apos;t have an account?{' '}
          <Link
            to="/signup"
            className={`font-bold hover:underline ${isLight ? 'text-cyan-700' : 'text-cyan-400'}`}
          >
            Request Access
          </Link>
        </p>
      </div>
    </div>
  );
};
export default LoginPage;
