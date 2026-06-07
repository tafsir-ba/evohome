import { Navigate } from 'react-router-dom';
import { GanttChartTool } from './GanttChartTool';
import { GanttExternalRedirect } from './GanttExternalRedirect';
import { isGanttHost } from '../../components/gantt/ganttHostUtils';

/**
 * Same DO app serves evohome CMP + Gantt subdomain:
 * - app.carib-recon.org → Gantt tool
 * - app.evo-home.ch → redirect legacy Gantt URLs to app.carib-recon.org
 */
export const GanttDomainRoute = ({ canonicalPath = '/gantt' }) => {
  if (isGanttHost()) {
    if (window.location.pathname !== canonicalPath) {
      return <Navigate to={canonicalPath} replace />;
    }
    return <GanttChartTool />;
  }
  return <GanttExternalRedirect />;
};
