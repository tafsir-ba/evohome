import { LandingPage } from '../LandingPage';
import { CaribLanding } from '../CaribLanding';
import { isCaribSite } from '../../components/carib/caribSiteUtils';

/** `/` — CRC marketing on carib-recon.org; Evohome landing elsewhere. */
export const AppRootRoute = () => {
  if (isCaribSite()) {
    return <CaribLanding />;
  }
  return <LandingPage />;
};
