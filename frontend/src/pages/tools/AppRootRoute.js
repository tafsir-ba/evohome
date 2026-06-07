import { Navigate } from 'react-router-dom';
import { LandingPage } from '../LandingPage';
import { isGanttHost } from '../../components/gantt/ganttHostUtils';
import { useAuth } from '../../context/AuthContext';
import { Loader2 } from 'lucide-react';

export const AppRootRoute = () => {
  const { user, loading } = useAuth();

  if (isGanttHost()) {
    if (loading) {
      return (
        <div className="min-h-screen flex items-center justify-center bg-background">
          <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
        </div>
      );
    }
    return <Navigate to={user ? '/gantt' : '/login'} replace />;
  }

  return <LandingPage />;
};
