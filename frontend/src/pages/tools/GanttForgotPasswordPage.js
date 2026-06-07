import { useState } from 'react';
import { Link } from 'react-router-dom';
import { Button } from '../../components/ui/button';
import { Input } from '../../components/ui/input';
import { Label } from '../../components/ui/label';
import { toast } from 'sonner';
import { Loader2, Mail, CheckCircle } from 'lucide-react';
import { GanttAuthShell } from '../../components/gantt/GanttAuthShell';
import { getApiBaseUrl } from '../../lib/api';
import { GANTT_AUTH_ROLE } from '../../components/gantt/ganttAuthUtils';

export const GanttForgotPasswordPage = () => {
  const [email, setEmail] = useState('');
  const [loading, setLoading] = useState(false);
  const [sent, setSent] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!email) {
      toast.error('Please enter your email address');
      return;
    }
    setLoading(true);
    try {
      const res = await fetch(`${getApiBaseUrl()}/auth/forgot-password`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
        body: JSON.stringify({ email, role: GANTT_AUTH_ROLE }),
      });
      if (res.ok) {
        setSent(true);
        toast.success('If an account exists, a reset link has been sent.');
      } else {
        const data = await res.json();
        toast.error(data.detail || 'Failed to send reset email');
      }
    } catch {
      toast.error('Network error. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  if (sent) {
    return (
      <GanttAuthShell title="Check your email" subtitle={`We sent a reset link to ${email} if an account exists.`}>
        <div className="text-center space-y-4">
          <div className="w-12 h-12 bg-primary/10 rounded-full flex items-center justify-center mx-auto">
            <CheckCircle className="w-6 h-6 text-primary" />
          </div>
          <Button asChild variant="outline" className="w-full">
            <Link to="/login">Back to sign in</Link>
          </Button>
          <button
            type="button"
            onClick={() => setSent(false)}
            className="text-xs text-muted-foreground hover:text-foreground"
          >
            Didn&apos;t receive it? Try again
          </button>
        </div>
      </GanttAuthShell>
    );
  }

  return (
    <GanttAuthShell
      title="Forgot password?"
      subtitle="Enter your email and we will send a reset link"
    >
      <form onSubmit={handleSubmit} className="space-y-4">
        <div className="space-y-2">
          <Label htmlFor="gantt-forgot-email">Email</Label>
          <div className="relative">
            <Mail className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
            <Input
              id="gantt-forgot-email"
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="you@example.com"
              required
              className="pl-10 h-10"
            />
          </div>
        </div>
        <Button type="submit" className="w-full h-10" disabled={loading || !email}>
          {loading ? <Loader2 className="w-4 h-4 animate-spin" /> : 'Send reset link'}
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
