import { useState, useEffect } from 'react';
import { useSearchParams, Link } from 'react-router-dom';
import { Button } from '../../components/ui/button';
import { Input } from '../../components/ui/input';
import { Label } from '../../components/ui/label';
import { toast } from 'sonner';
import { Loader2, CheckCircle, AlertCircle, Eye, EyeOff } from 'lucide-react';
import { GanttAuthShell } from '../../components/gantt/GanttAuthShell';

const API = process.env.REACT_APP_BACKEND_URL + '/api';

export const GanttResetPasswordPage = () => {
  const [searchParams] = useSearchParams();
  const token = searchParams.get('token');
  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [loading, setLoading] = useState(false);
  const [success, setSuccess] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    if (!token) {
      setError('Invalid reset link. Please request a new password reset.');
    }
  }, [token]);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    if (password.length < 8) {
      setError('Password must be at least 8 characters');
      return;
    }
    if (password !== confirmPassword) {
      setError('Passwords do not match');
      return;
    }
    setLoading(true);
    try {
      const res = await fetch(`${API}/auth/reset-password`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ token, new_password: password }),
      });
      if (res.ok) {
        setSuccess(true);
        toast.success('Password reset successful');
      } else {
        const data = await res.json();
        setError(data.detail || 'Failed to reset password');
      }
    } catch {
      setError('Network error. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  if (success) {
    return (
      <GanttAuthShell title="Password updated" subtitle="You can now sign in with your new password.">
        <Button asChild className="w-full">
          <Link to="/login">Go to sign in</Link>
        </Button>
      </GanttAuthShell>
    );
  }

  if (!token) {
    return (
      <GanttAuthShell title="Invalid link" subtitle={error}>
        <Button asChild variant="outline" className="w-full">
          <Link to="/forgot-password">Request a new reset link</Link>
        </Button>
      </GanttAuthShell>
    );
  }

  return (
    <GanttAuthShell title="Set new password" subtitle="Choose a new password for your account">
      <form onSubmit={handleSubmit} className="space-y-4">
        {error ? (
          <div className="flex items-start gap-2 text-sm text-destructive bg-destructive/10 p-3 rounded-lg">
            <AlertCircle className="w-4 h-4 shrink-0 mt-0.5" />
            <span>{error}</span>
          </div>
        ) : null}
        <div className="space-y-2">
          <Label htmlFor="gantt-reset-password">New password</Label>
          <div className="relative">
            <Input
              id="gantt-reset-password"
              type={showPassword ? 'text' : 'password'}
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
              minLength={8}
              className="pr-10 h-10"
            />
            <button
              type="button"
              className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground"
              onClick={() => setShowPassword((v) => !v)}
            >
              {showPassword ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
            </button>
          </div>
        </div>
        <div className="space-y-2">
          <Label htmlFor="gantt-reset-confirm">Confirm password</Label>
          <Input
            id="gantt-reset-confirm"
            type={showPassword ? 'text' : 'password'}
            value={confirmPassword}
            onChange={(e) => setConfirmPassword(e.target.value)}
            required
            minLength={8}
            className="h-10"
          />
        </div>
        <Button type="submit" className="w-full h-10" disabled={loading}>
          {loading ? <Loader2 className="w-4 h-4 animate-spin" /> : 'Update password'}
        </Button>
        <p className="text-center text-sm text-muted-foreground">
          <Link to="/login" className="text-primary hover:underline">
            Back to sign in
          </Link>
        </p>
      </form>
    </GanttAuthShell>
  );
};
