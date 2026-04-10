import { useEffect, useRef } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { toast } from 'sonner';
import { Home } from 'lucide-react';

export const AuthCallback = () => {
  const { exchangeSession } = useAuth();
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const hasProcessed = useRef(false);

  useEffect(() => {
    // Use ref to prevent double processing in StrictMode
    if (hasProcessed.current) return;
    hasProcessed.current = true;

    const processCallback = async () => {
      const hash = window.location.hash;
      const sessionIdMatch = hash.match(/session_id=([^&]+)/);
      
      if (!sessionIdMatch) {
        toast.error('Authentication failed: No session ID');
        navigate('/login');
        return;
      }
      
      const sessionId = sessionIdMatch[1];
      // Get intended role from URL query params (set during login)
      const intendedRole = searchParams.get('intended_role');
      
      try {
        const user = await exchangeSession(sessionId, intendedRole);
        toast.success(`Welcome, ${user.name}!`);
        
        // Clear the hash and navigate
        window.history.replaceState(null, '', window.location.pathname);
        
        // Navigate based on role
        if (user.role === 'buyer') {
          navigate('/buyer/dashboard', { replace: true, state: { user } });
        } else {
          navigate('/agent/home', { replace: true, state: { user } });
        }
      } catch (error) {
        console.error('Auth callback error:', error);
        toast.error(error.message || 'Authentication failed. Please try again.');
        navigate('/login');
      }
    };

    processCallback();
  }, [exchangeSession, navigate, searchParams]);

  return (
    <div className="min-h-screen flex items-center justify-center bg-background">
      <div className="text-center">
        <div className="flex items-center justify-center gap-3 mb-8">
          <img 
            src="/evohome-logo.png" 
            alt="Evohome" 
            className="h-10 w-auto"
          />
        </div>
        <div className="w-8 h-8 border-2 border-primary border-t-transparent rounded-full animate-spin mx-auto mb-4"></div>
        <p className="text-muted-foreground">Completing authentication...</p>
      </div>
    </div>
  );
};
