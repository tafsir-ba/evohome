/** Display name for the standalone Gantt app (matches backend GANTT_APP_NAME). */
export const GANTT_APP_NAME = 'Caribbean Regional Connectivity';

/**
 * Hostnames that serve the Gantt app on DO (not Emergent marketing, not evohome CMP).
 * carib-recon.org / www → CRC marketing site; app.carib-recon.org → Gantt app.
 */
const DEFAULT_GANTT_HOSTS = ['app.carib-recon.org'];

export const GANTT_APP_URL =
  process.env.REACT_APP_GANTT_APP_URL || 'https://app.carib-recon.org/gantt';

export const GANTT_LOGIN_URL =
  process.env.REACT_APP_GANTT_LOGIN_URL || 'https://app.carib-recon.org/login';

const ganttHosts = (process.env.REACT_APP_GANTT_HOSTS || '')
  .split(',')
  .map((h) => h.trim().toLowerCase())
  .filter(Boolean);

const GANTT_HOSTS = ganttHosts.length ? ganttHosts : DEFAULT_GANTT_HOSTS;

export const isGanttHost = (hostname = window.location.hostname) =>
  GANTT_HOSTS.includes(hostname.toLowerCase());
