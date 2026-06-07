import { isGanttHost } from '../../components/gantt/ganttHostUtils';

/**
 * Renders the Gantt-branded auth page on carib-recon.org, else the CMP default.
 */
export const GanttHostAuthRoute = ({ gantt: GanttPage, default: DefaultPage }) =>
  isGanttHost() ? <GanttPage /> : <DefaultPage />;
