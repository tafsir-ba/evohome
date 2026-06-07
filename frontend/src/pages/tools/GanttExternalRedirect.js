import { useEffect } from 'react';
import { GANTT_APP_URL } from '../../components/gantt/ganttHostUtils';
import { useGanttAppName } from '../../components/gantt/ganttAuthUtils';

/** Sends users from evohome to the standalone Gantt host. */
export const GanttExternalRedirect = () => {
  const appName = useGanttAppName();
  useEffect(() => {
    window.location.replace(GANTT_APP_URL);
  }, []);

  return (
    <div className="min-h-screen flex items-center justify-center bg-background">
      <p className="text-sm text-muted-foreground">Redirecting to {appName}…</p>
    </div>
  );
};
