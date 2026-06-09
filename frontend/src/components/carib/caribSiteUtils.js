/**
 * carib-recon.org / www → CRC marketing site.
 * app.carib-recon.org → Gantt app (see ganttHostUtils).
 */
const DEFAULT_MARKETING_HOSTS = ['carib-recon.org', 'www.carib-recon.org'];

const marketingHosts = (process.env.REACT_APP_CARIB_MARKETING_HOSTS || '')
  .split(',')
  .map((h) => h.trim().toLowerCase())
  .filter(Boolean);

const CARIB_MARKETING_HOSTS = marketingHosts.length ? marketingHosts : DEFAULT_MARKETING_HOSTS;

export const isCaribMarketingHost = (hostname = window.location.hostname) =>
  CARIB_MARKETING_HOSTS.includes(hostname.toLowerCase());
