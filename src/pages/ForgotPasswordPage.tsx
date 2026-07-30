import React, { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { Lock, Mail, ArrowRight, AlertCircle, CheckCircle, Info } from 'lucide-react';
import { authService } from '../services/auth';
import { BrandLogo } from '../components/common/BrandLogo';
import { useTheme } from '../context/ThemeContext';
import { ThemeToggle } from '../components/common/ThemeToggle';

const MIN_PASSWORD_LENGTH = 8;

export const ForgotPasswordPage: React.FC = () => {
  const navigate = useNavigate();
  const { isLight } = useTheme();
  const [step, setStep] = useState<'request' | 'reset'>('request');
  const [email, setEmail] = useState('');
  const [newPassword, setNewPassword] = useState('');
  const [resetToken, setResetToken] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [successMsg, setSuccessMsg] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);

  const labelClass = `text-[14px] font-semibold block mb-1.5 ${
    isLight ? 'text-slate-700' : 'text-slate-200'
  }`;
  const inputClass = `w-full pl-9 pr-3 py-2.5 rounded-xl text-[15px] focus:outline-none focus:ring-2 focus:ring-cyan-500/40 ${
    isLight
      ? 'bg-white border border-slate-300 text-slate-900 placeholder:text-slate-400'
      : 'bg-slate-950 border border-slate-700 text-white placeholder:text-slate-500'
  }`;
  const formClass = `p-6 rounded-2xl space-y-4 border ${
    isLight
      ? 'bg-white border-slate-200 shadow-lg shadow-slate-200/60'
      : 'bg-slate-900 border-slate-700'
  }`;

  const handleRequestToken = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setSuccessMsg(null);
    setIsLoading(true);
    try {
      const res = await authService.requestPasswordReset(email);
      setSuccessMsg(
        res.message ||
          'If that email is registered, a reset token has been issued (valid 30 minutes).',
      );
      setStep('reset');
    } catch (err: any) {
      setError(err.message || 'Could not request a reset token right now.');
    } finally {
      setIsLoading(false);
    }
  };

  const handleReset = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setSuccessMsg(null);

    if (newPassword.length < MIN_PASSWORD_LENGTH) {
      setError(`Password must be at least ${MIN_PASSWORD_LENGTH} characters.`);
      return;
    }

    setIsLoading(true);
    try {
      const res = await authService.forgotPassword(email, newPassword, resetToken);
      if (res.success) {
        setSuccessMsg(res.message || 'Password reset completed. Redirecting to login...');
        setTimeout(() => {
          navigate('/login');
        }, 2500);
      } else {
        setError(res.message || 'Failed to reset password.');
      }
    } catch (err: any) {
      setError(err.message || 'An error occurred during password reset.');
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div
      className={`min-h-screen flex items-center justify-center p-6 ${
        isLight
          ? 'bg-[linear-gradient(180deg,#f8fafc_0%,#eef2f7_100%)] text-slate-800'
          : 'bg-slate-950 text-slate-100'
      }`}
    >
      <div className="absolute top-4 right-4">
        <ThemeToggle />
      </div>

      <div className="w-full max-w-md space-y-6">
        <div className="text-center space-y-3">
          <BrandLogo size="lg" stacked to="/" className="mx-auto" />
          <h1 className={`text-xl font-extrabold pt-2 ${isLight ? 'text-slate-900' : 'text-white'}`}>
            Reset Password
          </h1>
        </div>

        <div
          className={`rounded-xl p-3 flex items-start gap-2.5 text-[14px] border ${
            isLight
              ? 'bg-cyan-50 border-cyan-200 text-cyan-900'
              : 'bg-cyan-500/10 border-cyan-500/30 text-cyan-200'
          }`}
        >
          <Info className="w-4 h-4 shrink-0 mt-0.5" />
          <span>
            Pilot limitation: no email/SMS provider is connected yet, so the reset token isn&apos;t
            delivered to your inbox. It is logged on the server console for local/demo use.
            A production deployment must wire in a real mail provider before go-live.
          </span>
        </div>

        {error && (
          <div
            className={`rounded-xl p-3 flex items-start gap-2.5 text-[14px] border ${
              isLight
                ? 'bg-red-50 border-red-200 text-red-700'
                : 'bg-red-500/10 border-red-500/30 text-red-300'
            }`}
          >
            <AlertCircle className="w-4.5 h-4.5 shrink-0 mt-0.5" />
            <span>{error}</span>
          </div>
        )}

        {successMsg && (
          <div
            className={`rounded-xl p-3 flex items-start gap-2.5 text-[14px] border ${
              isLight
                ? 'bg-emerald-50 border-emerald-200 text-emerald-800'
                : 'bg-emerald-500/10 border-emerald-500/30 text-emerald-300'
            }`}
          >
            <CheckCircle className="w-4.5 h-4.5 shrink-0 mt-0.5" />
            <span>{successMsg}</span>
          </div>
        )}

        {step === 'request' ? (
          <form onSubmit={handleRequestToken} className={formClass}>
            <div>
              <label className={labelClass}>Registered Account Email</label>
              <div className="relative">
                <Mail className={`w-4 h-4 absolute left-3 top-3 ${isLight ? 'text-slate-500' : 'text-slate-400'}`} />
                <input
                  type="email"
                  required
                  placeholder="admin@utility.gov"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  className={inputClass}
                />
              </div>
            </div>

            <button
              type="submit"
              disabled={isLoading}
              className="w-full py-2.5 rounded-xl bg-cyan-600 text-white font-bold text-[15px] hover:bg-cyan-500 transition-colors flex items-center justify-center gap-2 disabled:opacity-60"
            >
              {isLoading ? 'Requesting token...' : 'Send Reset Token'} <ArrowRight className="w-4 h-4" />
            </button>
            <button
              type="button"
              onClick={() => setStep('reset')}
              className={`w-full text-[14px] transition-colors ${
                isLight ? 'text-slate-600 hover:text-cyan-700' : 'text-slate-400 hover:text-cyan-400'
              }`}
            >
              Already have a token? Enter it directly
            </button>
          </form>
        ) : (
          <form onSubmit={handleReset} className={formClass}>
            <div>
              <label className={labelClass}>Registered Account Email</label>
              <div className="relative">
                <Mail className={`w-4 h-4 absolute left-3 top-3 ${isLight ? 'text-slate-500' : 'text-slate-400'}`} />
                <input
                  type="email"
                  required
                  placeholder="admin@utility.gov"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  className={inputClass}
                />
              </div>
            </div>

            <div>
              <label className={labelClass}>Reset Token</label>
              <div className="relative">
                <Lock className={`w-4 h-4 absolute left-3 top-3 ${isLight ? 'text-slate-500' : 'text-slate-400'}`} />
                <input
                  type="text"
                  required
                  placeholder="Token from the server log (30 min validity)"
                  value={resetToken}
                  onChange={(e) => setResetToken(e.target.value)}
                  className={inputClass}
                />
              </div>
            </div>

            <div>
              <label className={labelClass}>New Secure Password</label>
              <div className="relative">
                <Lock className={`w-4 h-4 absolute left-3 top-3 ${isLight ? 'text-slate-500' : 'text-slate-400'}`} />
                <input
                  type="password"
                  required
                  minLength={MIN_PASSWORD_LENGTH}
                  placeholder="At least 8 characters"
                  value={newPassword}
                  onChange={(e) => setNewPassword(e.target.value)}
                  className={inputClass}
                />
              </div>
            </div>

            <button
              type="submit"
              disabled={isLoading}
              className="w-full py-2.5 rounded-xl bg-cyan-600 text-white font-bold text-[15px] hover:bg-cyan-500 transition-colors flex items-center justify-center gap-2 disabled:opacity-60"
            >
              {isLoading ? 'Resetting Password...' : 'Reset Password'} <ArrowRight className="w-4 h-4" />
            </button>
            <button
              type="button"
              onClick={() => setStep('request')}
              className={`w-full text-[14px] transition-colors ${
                isLight ? 'text-slate-600 hover:text-cyan-700' : 'text-slate-400 hover:text-cyan-400'
              }`}
            >
              Back to request a token
            </button>
          </form>
        )}

        <p className={`text-center text-[14px] ${isLight ? 'text-slate-600' : 'text-slate-400'}`}>
          Remember credentials?{' '}
          <Link
            to="/login"
            className={`font-bold hover:underline ${isLight ? 'text-cyan-700' : 'text-cyan-400'}`}
          >
            Log in
          </Link>
        </p>
      </div>
    </div>
  );
};

export default ForgotPasswordPage;
