/** Display name for the standalone Gantt app (matches backend GANTT_APP_NAME). */
export const GANTT_APP_NAME = 'Caribbean Regional Connectivity';

/** Hostnames that serve the standalone Gantt app (not the evohome CMP). */
const DEFAULT_GANTT_HOSTS = ['carib-recon.org', 'www.carib-recon.org'];

export const GANTT_APP_URL =
  process.env.REACT_APP_GANTT_APP_URL || 'https://carib-recon.org/gantt';

const ganttHosts = (process.env.REACT_APP_GANTT_HOSTS || '')
  .split(',')
  .map((h) => h.trim().toLowerCase())
  .filter(Boolean);

const GANTT_HOSTS = ganttHosts.length ? ganttHosts : DEFAULT_GANTT_HOSTS;

export const isGanttHost = (hostname = window.location.hostname) =>
  GANTT_HOSTS.includes(hostname.toLowerCase());
