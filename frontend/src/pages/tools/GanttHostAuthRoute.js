import { isCaribSite } from '../../components/carib/caribSiteUtils';

/** CRC-branded auth pages on carib-recon.org; Evohome pages on other hosts. */
export const GanttHostAuthRoute = ({ gantt: GanttPage, default: DefaultPage }) =>
  isCaribSite() ? <GanttPage /> : <DefaultPage />;
