import { useEffect } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { LogIn, Map } from 'lucide-react';
import { useAuth } from '../../context/AuthContext';
import { Button } from '../../components/ui/button';
import { ThemeToggle } from '../../components/ThemeToggle';
import { GanttLogo } from '../../components/gantt/GanttLogo';
import { useGanttPublicConfig } from '../../components/gantt/ganttAuthUtils';
import { useGanttBranding } from '../../components/gantt/ganttBrandingUtils';

export const GanttLandingPage = () => {
  const { app_name: appName } = useGanttPublicConfig();
  const { user, loading } = useAuth();
  const navigate = useNavigate();
  useGanttBranding(appName);

  useEffect(() => {
    if (!loading && user) {
      navigate('/gantt', { replace: true });
    }
  }, [loading, user, navigate]);

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-background">
        <div className="h-6 w-6 animate-spin rounded-full border-2 border-muted-foreground border-t-transparent" />
      </div>
    );
  }

  if (user) {
    return null;
  }

  return (
    <div className="min-h-screen bg-background flex flex-col items-center justify-center p-6 relative">
      <div className="absolute top-3 right-3">
        <ThemeToggle />
      </div>
      <div className="flex flex-col items-center gap-8 max-w-md w-full text-center">
        <GanttLogo size="landing" alt={appName} />
        <div className="flex flex-col gap-3 w-full sm:flex-row sm:justify-center">
          <Button asChild size="lg" className="h-11 px-8">
            <Link to="/login">
              <LogIn className="h-4 w-4 mr-2" />
              Sign in
            </Link>
          </Button>
          <Button asChild variant="outline" size="lg" className="h-11 px-8">
            <Link to="/map">
              <Map className="h-4 w-4 mr-2" />
              Live vessel map
            </Link>
          </Button>
        </div>
      </div>
    </div>
  );
};
