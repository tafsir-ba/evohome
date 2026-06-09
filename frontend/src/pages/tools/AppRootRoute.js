import { LandingPage } from '../LandingPage';
import { CaribLanding } from '../CaribLanding';
import { isCaribMarketingHost } from '../../components/carib/caribSiteUtils';
import { isGanttHost } from '../../components/gantt/ganttHostUtils';
import { GanttLandingPage } from './GanttLandingPage';

export const AppRootRoute = () => {
  if (isGanttHost()) {
    return <GanttLandingPage />;
  }

  if (isCaribMarketingHost()) {
    return <CaribLanding />;
  }

  return <LandingPage />;
};
