import { Navigate } from 'react-router-dom';
import { GanttChartTool } from './GanttChartTool';
import { GanttExternalRedirect } from './GanttExternalRedirect';
import { isCaribSite } from '../../components/carib/caribSiteUtils';

/** `/gantt` on carib-recon.org; other hosts redirect to CRC Gantt URL. */
export const GanttDomainRoute = ({ canonicalPath = '/gantt' }) => {
  if (isCaribSite()) {
    if (window.location.pathname !== canonicalPath) {
      return <Navigate to={canonicalPath} replace />;
    }
    return <GanttChartTool />;
  }
  return <GanttExternalRedirect />;
};
