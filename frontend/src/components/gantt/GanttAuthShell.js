import { Link } from 'react-router-dom';
import { ThemeToggle } from '../ThemeToggle';
import { useGanttPublicConfig } from './ganttAuthUtils';
import { useGanttBranding } from './ganttBrandingUtils';
import { GanttLogo } from './GanttLogo';

export const GanttAuthShell = ({ title, subtitle, children }) => {
  const { app_name: appName } = useGanttPublicConfig();
  useGanttBranding(appName);
  return (
  <div className="min-h-screen bg-background flex flex-col items-center justify-center p-4 relative">
    <div className="absolute top-3 right-3">
      <ThemeToggle />
    </div>
    <Link
      to="/gantt"
      className="flex flex-col items-center mb-6 text-foreground hover:opacity-90 transition-opacity"
      aria-label={appName}
    >
      <GanttLogo size="auth" alt={appName} />
    </Link>
    <div className="w-full max-w-md border rounded-xl bg-card p-6 sm:p-8 shadow-sm">
      {title ? (
        <div className="mb-6 text-center">
          <h1 className="text-xl font-semibold text-foreground">{title}</h1>
          {subtitle ? <p className="text-sm text-muted-foreground mt-1">{subtitle}</p> : null}
        </div>
      ) : null}
      {children}
    </div>
  </div>
  );
};
