import React, { useState } from 'react';
import { Link, useNavigate, useLocation } from 'react-router-dom';
import { Layers, Eye, EyeOff, Lock, Mail, AlertCircle } from 'lucide-react';
import { useAuth } from '../../context/AuthContext';
import { UnderstatedIllustration } from '../../components/common/UnderstatedIllustration';

export const SignInPage: React.FC = () => {
  const { login } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();

  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  // Success message passed from registration redirect
  const registrationSuccessMessage = (location.state as any)?.message;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (isLoading) return;
    setErrorMessage(null);

    const cleanEmail = email.trim();
    if (!cleanEmail || !password) {
      setErrorMessage('Please provide both email and password.');
      return;
    }

    setIsLoading(true);
    try {
      // Do not trim password; pass exact string
      const user = await login(cleanEmail, password);

      // Safe return path handling: must stay inside the application and respect role permissions
      const requestedPath = (location.state as any)?.from;
      let destination = user.role === 'ADMIN' ? '/admin/dashboard' : '/app/dashboard';

      if (
        typeof requestedPath === 'string' &&
        requestedPath.startsWith('/') &&
        !requestedPath.startsWith('//') &&
        !requestedPath.includes('\\')
      ) {
        if (user.role === 'ADMIN' && !requestedPath.startsWith('/app')) {
          destination = requestedPath;
        } else if (user.role === 'USER' && !requestedPath.startsWith('/admin')) {
          destination = requestedPath;
        }
      }

      navigate(destination, { replace: true });
    } catch (err: any) {
      setErrorMessage(err.message || 'Authentication failed. Please verify your credentials.');
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex flex-col lg:flex-row bg-[#F8FAFC] dark:bg-[#0B0F17] text-slate-900 dark:text-slate-100">
      {/* Left Column: Visual & Overview */}
      <div className="hidden lg:flex lg:w-1/2 bg-[#0F172A] p-12 flex-col justify-between relative overflow-hidden border-r border-slate-800">
        <div className="flex items-center gap-3">
          <div className="flex items-center justify-center w-10 h-10 rounded-xl bg-indigo-600 text-white shadow-md shadow-indigo-600/30">
            <Layers className="w-5 h-5 text-white" />
          </div>
          <div>
            <span className="text-lg font-bold tracking-tight text-white">
              QA Framework
            </span>
            <span className="block text-xs text-slate-400">
              Quality Assurance Workspace
            </span>
          </div>
        </div>

        {/* Center illustration */}
        <div className="my-auto py-8">
          <UnderstatedIllustration className="w-full max-w-lg mx-auto" />
          <div className="text-center mt-6">
            <h2 className="text-lg font-semibold text-white">
              Unified Software Quality Assurance
            </h2>
            <p className="text-sm text-slate-400 max-w-sm mx-auto mt-1 leading-relaxed">
              Standardized testing workspace for tool-use verification, workflow conformance, and robustness evaluation.
            </p>
          </div>
        </div>

        <div className="text-xs text-slate-400 flex items-center justify-between">
          <span>Protected System Environment</span>
          <span>Role-Based Access</span>
        </div>
      </div>

      {/* Right Column: Sign In Form */}
      <div className="flex-1 flex items-center justify-center p-6 sm:p-10 lg:p-16">
        <div className="w-full max-w-md">
          {/* Mobile Brand Header */}
          <div className="flex items-center gap-3 mb-8 lg:hidden">
            <div className="flex items-center justify-center w-10 h-10 rounded-xl bg-indigo-600 text-white">
              <Layers className="w-5 h-5" />
            </div>
            <div>
              <span className="text-base font-bold text-slate-900 dark:text-white">
                QA Framework
              </span>
              <span className="block text-xs text-slate-500 dark:text-slate-400">
                Quality Assurance Workspace
              </span>
            </div>
          </div>

          <div className="mb-8">
            <h1 className="text-2xl sm:text-3xl font-bold text-slate-900 dark:text-white tracking-tight">
              Sign In
            </h1>
            <p className="mt-2 text-sm text-slate-600 dark:text-slate-400">
              Enter your credentials to access your quality assurance workspace.
            </p>
          </div>

          {registrationSuccessMessage && (
            <div className="mb-6 p-4 rounded-xl bg-teal-50 dark:bg-teal-950/40 border border-teal-200 dark:border-teal-800 text-teal-800 dark:text-teal-200 text-sm">
              {registrationSuccessMessage}
            </div>
          )}

          {errorMessage && (
            <div
              id="signin-error"
              role="alert"
              className="mb-6 p-4 rounded-xl bg-rose-50 dark:bg-rose-950/40 border border-rose-200 dark:border-rose-800 text-rose-800 dark:text-rose-200 text-sm flex items-start gap-3"
            >
              <AlertCircle className="w-5 h-5 shrink-0 mt-0.5" />
              <span>{errorMessage}</span>
            </div>
          )}

          <form onSubmit={handleSubmit} className="space-y-5" noValidate>
            <div>
              <label
                htmlFor="signin-email"
                className="block text-xs font-semibold uppercase tracking-wider text-slate-700 dark:text-slate-300 mb-1.5"
              >
                Email Address
              </label>
              <div className="relative">
                <div className="absolute inset-y-0 left-0 pl-3.5 flex items-center pointer-events-none text-slate-400">
                  <Mail className="w-4 h-4" />
                </div>
                <input
                  id="signin-email"
                  type="email"
                  name="email"
                  autoComplete="username"
                  required
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="name@example.com"
                  aria-describedby={errorMessage ? 'signin-error' : undefined}
                  className="w-full pl-10 pr-4 py-2.5 rounded-xl border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-900 text-slate-900 dark:text-white placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-indigo-600 focus:border-transparent text-sm transition-all shadow-sm"
                />
              </div>
            </div>

            <div>
              <label
                htmlFor="signin-password"
                className="block text-xs font-semibold uppercase tracking-wider text-slate-700 dark:text-slate-300 mb-1.5"
              >
                Password
              </label>
              <div className="relative">
                <div className="absolute inset-y-0 left-0 pl-3.5 flex items-center pointer-events-none text-slate-400">
                  <Lock className="w-4 h-4" />
                </div>
                <input
                  id="signin-password"
                  type={showPassword ? 'text' : 'password'}
                  name="password"
                  autoComplete="current-password"
                  required
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="Enter account password"
                  aria-describedby={errorMessage ? 'signin-error' : undefined}
                  className="w-full pl-10 pr-11 py-2.5 rounded-xl border border-slate-300 dark:border-slate-700 bg-white dark:bg-slate-900 text-slate-900 dark:text-white placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-indigo-600 focus:border-transparent text-sm transition-all shadow-sm"
                />
                <button
                  type="button"
                  onClick={() => setShowPassword(!showPassword)}
                  className="absolute inset-y-0 right-0 pr-3.5 flex items-center text-slate-400 hover:text-slate-600 dark:hover:text-slate-200 focus:outline-none"
                  aria-label={showPassword ? 'Hide password' : 'Show password'}
                >
                  {showPassword ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                </button>
              </div>
            </div>

            <button
              type="submit"
              disabled={isLoading}
              className="w-full flex items-center justify-center gap-2 py-3 px-4 rounded-xl bg-indigo-600 hover:bg-indigo-700 disabled:bg-indigo-400 text-white font-semibold text-sm transition-colors shadow-sm shadow-indigo-600/30 focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:ring-offset-2 dark:focus:ring-offset-slate-950"
            >
              {isLoading ? (
                <>
                  <div className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin" />
                  <span>Signing in...</span>
                </>
              ) : (
                <span>Sign In</span>
              )}
            </button>
          </form>

          <div className="mt-8 pt-6 border-t border-slate-200 dark:border-slate-800 text-center">
            <p className="text-sm text-slate-600 dark:text-slate-400">
              Don't have an account?{' '}
              <Link
                to="/sign-up"
                className="font-semibold text-indigo-600 dark:text-indigo-400 hover:underline"
              >
                Sign up
              </Link>
            </p>
          </div>
        </div>
      </div>
    </div>
  );
};
