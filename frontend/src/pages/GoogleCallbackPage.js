import { useEffect, useState, useRef } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { toast } from 'sonner';
import { Loader2 } from 'lucide-react';

const API = process.env.REACT_APP_BACKEND_URL + '/api';

export const GoogleCallbackPage = () => {
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const { setAuthUser } = useAuth();
  const [error, setError] = useState(null);
  const hasProcessed = useRef(false);

  useEffect(() => {
    // Prevent double execution (React Strict Mode or re-renders)
    if (hasProcessed.current) return;
    hasProcessed.current = true;

    const handleCallback = async () => {
      const code = searchParams.get('code');
      const state = searchParams.get('state');
      const errorParam = searchParams.get('error');

      if (errorParam) {
        setError('Google authentication was cancelled or failed');
        toast.error('Authentication cancelled');
        setTimeout(() => navigate('/login'), 2000);
        return;
      }

      if (!code) {
        setError('No authorization code received');
        toast.error('Authentication failed');
        setTimeout(() => navigate('/login'), 2000);
        return;
      }

      try {
        const response = await fetch(`${API}/auth/google/callback`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          credentials: 'include',
          body: JSON.stringify({
            code,
            state: state ? decodeURIComponent(state) : '{}',
            redirect_uri: `${window.location.origin}/auth/google/callback`
          })
        });

        if (response.ok) {
          const data = await response.json();
          setAuthUser(data);
          toast.success('Login successful!');
          
          // Small delay to ensure state is updated before navigation
          await new Promise(resolve => setTimeout(resolve, 100));
          
          // Redirect based on role
          if (data.role === 'agent') {
            navigate('/agent/home', { replace: true });
          } else {
            navigate('/buyer/dashboard', { replace: true });
          }
        } else {
          const errorData = await response.json();
          throw new Error(errorData.detail || 'Authentication failed');
        }
      } catch (err) {
        console.error('Google OAuth callback error:', err);
        setError(err.message);
        toast.error(err.message);
        setTimeout(() => navigate('/login', { replace: true }), 3000);
      }
    };

    handleCallback();
  }, [searchParams, navigate, setAuthUser]);

  return (
    <div className="min-h-screen flex items-center justify-center bg-background">
      <div className="text-center">
        {error ? (
          <div className="space-y-4">
            <p className="text-destructive text-lg">{error}</p>
            <p className="text-muted-foreground">Redirecting to login...</p>
          </div>
        ) : (
          <div className="space-y-4">
            <Loader2 className="w-12 h-12 animate-spin text-primary mx-auto" />
            <p className="text-muted-foreground">Completing sign in...</p>
          </div>
        )}
      </div>
    </div>
  );
};

export default GoogleCallbackPage;
