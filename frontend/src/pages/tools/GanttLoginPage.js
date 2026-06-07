import { useEffect, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useAuth } from '../../context/AuthContext';
import { Button } from '../../components/ui/button';
import { Input } from '../../components/ui/input';
import { Label } from '../../components/ui/label';
import { toast } from 'sonner';
import { getApiBaseUrl, parseApiError } from '../../lib/api';
import { Loader2, Mail, Lock } from 'lucide-react';
import { GanttAuthShell } from '../../components/gantt/GanttAuthShell';
import { getPostAuthPath, useGanttPublicConfig } from '../../components/gantt/ganttAuthUtils';
import { useGanttBranding } from '../../components/gantt/ganttBrandingUtils';

export const GanttLoginPage = () => {
  const {
    app_name: appName,
    default_auth_role: authRole,
    registration_enabled: registrationEnabled,
  } = useGanttPublicConfig();
  useGanttBranding(appName);
  const { user, loginWithGoogle, setAuthUser } = useAuth();
  const navigate = useNavigate();
  const [googleLoading, setGoogleLoading] = useState(false);
  const [emailLoading, setEmailLoading] = useState(false);
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');

  useEffect(() => {
    if (user) {
      navigate(getPostAuthPath(user.role), { replace: true });
    }
  }, [user, navigate]);

  const handleGoogleLogin = () => {
    setGoogleLoading(true);
    loginWithGoogle(authRole);
  };

  const handleEmailLogin = async (e) => {
    e.preventDefault();
    setEmailLoading(true);
    try {
      const res = await fetch(`${getApiBaseUrl()}/auth/login`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
        body: JSON.stringify({ email, password }),
      });
      if (!res.ok) {
        const err = await parseApiError(res);
        throw new Error(err.message || 'Login failed');
      }
      const data = await res.json();
      if (data.token) {
        localStorage.setItem('auth_token', data.token);
      }
      setAuthUser(data);
      toast.success('Signed in successfully');
      navigate(getPostAuthPath(data.role), { replace: true });
    } catch (error) {
      toast.error(error.message);
    } finally {
      setEmailLoading(false);
    }
  };

  return (
    <GanttAuthShell
      title="Sign in"
      subtitle="Access your saved Gantt projects across devices"
    >
      <div className="space-y-4">
        <Button
          type="button"
          className="w-full h-11"
          onClick={handleGoogleLogin}
          disabled={googleLoading}
        >
          {googleLoading ? (
            <Loader2 className="w-4 h-4 animate-spin" />
          ) : (
            <>
              <svg className="w-4 h-4 mr-2" viewBox="0 0 24 24" aria-hidden>
                <path
                  fill="currentColor"
                  d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"
                />
                <path
                  fill="currentColor"
                  d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"
                />
                <path
                  fill="currentColor"
                  d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z"
                />
                <path
                  fill="currentColor"
                  d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z"
                />
              </svg>
              Continue with Google
            </>
          )}
        </Button>

        <div className="relative">
          <div className="absolute inset-0 flex items-center">
            <div className="w-full border-t border-border" />
          </div>
          <div className="relative flex justify-center text-xs">
            <span className="bg-card px-2 text-muted-foreground">or</span>
          </div>
        </div>

        <form onSubmit={handleEmailLogin} className="space-y-3">
          <div className="space-y-2">
            <Label htmlFor="gantt-login-email">Email</Label>
            <div className="relative">
              <Mail className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
              <Input
                id="gantt-login-email"
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="you@example.com"
                required
                className="pl-10 h-10"
              />
            </div>
          </div>
          <div className="space-y-2">
            <div className="flex items-center justify-between">
              <Label htmlFor="gantt-login-password">Password</Label>
              <Link to="/forgot-password" className="text-xs text-primary hover:underline">
                Forgot password?
              </Link>
            </div>
            <div className="relative">
              <Lock className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
              <Input
                id="gantt-login-password"
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="••••••••"
                required
                className="pl-10 h-10"
              />
            </div>
          </div>
          <Button type="submit" className="w-full h-10" disabled={emailLoading}>
            {emailLoading ? <Loader2 className="w-4 h-4 animate-spin" /> : 'Sign in with email'}
          </Button>
        </form>

        {registrationEnabled ? (
          <p className="text-center text-sm text-muted-foreground">
            No account?{' '}
            <Link to="/register" className="text-primary hover:underline font-medium">
              Create one
            </Link>
          </p>
        ) : null}
      </div>
    </GanttAuthShell>
  );
};
