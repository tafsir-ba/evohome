import { LandingPage } from '../LandingPage';
import { isGanttHost } from '../../components/gantt/ganttHostUtils';
import { GanttLandingPage } from './GanttLandingPage';

export const AppRootRoute = () => {
  if (isGanttHost()) {
    return <GanttLandingPage />;
  }

  return <LandingPage />;
};
