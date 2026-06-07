import { Link } from 'react-router-dom';
import { BarChart3 } from 'lucide-react';
import { ThemeToggle } from '../ThemeToggle';
import { useGanttAppName } from './ganttAuthUtils';
import { useGanttBranding } from './ganttBrandingUtils';

export const GanttAuthShell = ({ title, subtitle, children }) => {
  const appName = useGanttAppName();
  useGanttBranding(appName);
  return (
  <div className="min-h-screen bg-background flex flex-col items-center justify-center p-4 relative">
    <div className="absolute top-3 right-3">
      <ThemeToggle />
    </div>
    <Link to="/gantt" className="flex items-center gap-2 mb-6 text-foreground hover:text-primary transition-colors">
      <BarChart3 className="h-6 w-6 text-primary" />
      <span className="text-base font-semibold">{appName}</span>
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
