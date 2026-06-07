import { useEffect } from 'react';
import { GANTT_APP_URL } from '../../components/gantt/ganttHostUtils';

/** Sends users from evohome to the standalone Gantt host. */
export const GanttExternalRedirect = () => {
  useEffect(() => {
    window.location.replace(GANTT_APP_URL);
  }, []);

  return (
    <div className="min-h-screen flex items-center justify-center bg-background">
      <p className="text-sm text-muted-foreground">Redirecting to Gantt…</p>
    </div>
  );
};
