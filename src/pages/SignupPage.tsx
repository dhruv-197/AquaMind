import React, { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { Mail, User, ArrowRight, ShieldCheck, Lock, AlertCircle } from 'lucide-react';
import { authService } from '../services/auth';
import { BrandLogo } from '../components/common/BrandLogo';
import { useTheme } from '../context/ThemeContext';
import { ThemeToggle } from '../components/common/ThemeToggle';

const MIN_PASSWORD_LENGTH = 8;

function passwordIssue(password: string): string | null {
  if (password.length < MIN_PASSWORD_LENGTH) {
    return `Password must be at least ${MIN_PASSWORD_LENGTH} characters.`;
  }
  if (!/[a-zA-Z]/.test(password) || !/[0-9]/.test(password)) {
    return 'Password must include at least one letter and one number.';
  }
  return null;
}

export const SignupPage: React.FC = () => {
  const navigate = useNavigate();
  const { isLight } = useTheme();
  const [username, setUsername] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [role, setRole] = useState('user');
  const [error, setError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);

  const labelClass = `text-[14px] font-semibold block mb-1.5 ${
    isLight ? 'text-slate-700' : 'text-slate-200'
  }`;
  const inputClass = `w-full pl-9 pr-3 py-2.5 rounded-xl text-[15px] focus:outline-none focus:ring-2 focus:ring-cyan-500/40 ${
    isLight
      ? 'bg-white border border-slate-300 text-slate-900 placeholder:text-slate-400'
      : 'bg-slate-950 border border-slate-700 text-white placeholder:text-slate-500'
  }`;
  const iconClass = `w-4 h-4 absolute left-3 top-3 ${isLight ? 'text-slate-500' : 'text-slate-400'}`;

  const handleSignup = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);

    const pwIssue = passwordIssue(password);
    if (pwIssue) {
      setError(pwIssue);
      return;
    }
    if (password !== confirmPassword) {
      setError('Passwords do not match.');
      return;
    }

    setIsLoading(true);

    try {
      const res = await authService.signup(username, email, role, password);
      if (res.success && res.data) {
        localStorage.setItem('access_token', res.data.access_token);
        localStorage.setItem('user_role', res.data.role);
        localStorage.setItem('username', res.data.username);
        localStorage.setItem('user_email', res.data.email);
        navigate('/dashboard');
      } else {
        setError(res.message || 'Registration failed.');
      }
    } catch (err: any) {
      setError(err.message || 'An error occurred during registration.');
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
            Enterprise Signup
          </h1>
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

        <form
          onSubmit={handleSignup}
          className={`p-6 rounded-2xl space-y-4 border ${
            isLight
              ? 'bg-white border-slate-200 shadow-lg shadow-slate-200/60'
              : 'bg-slate-900 border-slate-700'
          }`}
        >
          <div>
            <label className={labelClass}>Full Name</label>
            <div className="relative">
              <User className={iconClass} />
              <input
                type="text"
                required
                placeholder="Alex Mercer"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                className={inputClass}
              />
            </div>
          </div>

          <div>
            <label className={labelClass}>Work Email</label>
            <div className="relative">
              <Mail className={iconClass} />
              <input
                type="email"
                required
                placeholder="a.mercer@state.gov"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                className={inputClass}
              />
            </div>
          </div>

          <div>
            <label className={labelClass}>Role / Authorization Level</label>
            <div className="relative">
              <ShieldCheck className={iconClass} />
              <select
                value={role}
                onChange={(e) => setRole(e.target.value)}
                className={`${inputClass} appearance-none cursor-pointer`}
              >
                <option value="user">User (Viewer)</option>
                <option value="government_officer">Government Officer</option>
                <option value="industry">Industry Operator</option>
              </select>
            </div>
            <p className={`text-[14px] mt-1.5 leading-relaxed ${isLight ? 'text-slate-600' : 'text-slate-400'}`}>
              Administrator access is granted by an existing admin after signup, not self-selected here.
            </p>
          </div>

          <div>
            <label className={labelClass}>Password</label>
            <div className="relative">
              <Lock className={iconClass} />
              <input
                type="password"
                required
                minLength={MIN_PASSWORD_LENGTH}
                placeholder="At least 8 characters, 1 letter + 1 number"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className={inputClass}
              />
            </div>
          </div>

          <div>
            <label className={labelClass}>Confirm Password</label>
            <div className="relative">
              <Lock className={iconClass} />
              <input
                type="password"
                required
                placeholder="Re-enter your password"
                value={confirmPassword}
                onChange={(e) => setConfirmPassword(e.target.value)}
                className={inputClass}
              />
            </div>
          </div>

          <button
            type="submit"
            disabled={isLoading}
            className="w-full py-2.5 rounded-xl bg-cyan-600 text-white font-bold text-[15px] hover:bg-cyan-500 transition-colors flex items-center justify-center gap-2 disabled:opacity-60"
          >
            {isLoading ? 'Registering...' : 'Create Enterprise Account'}
            <ArrowRight className="w-4 h-4" />
          </button>
        </form>

        <p className={`text-center text-[14px] ${isLight ? 'text-slate-600' : 'text-slate-400'}`}>
          Already registered?{' '}
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

export default SignupPage;
