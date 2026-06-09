/**
 * Caribbean RE-Connect single-site mode (carib-recon.org).
 * All tools live on one domain: /, /login, /gantt, /map, …
 */
export const CARIB_SITE_URL =
  process.env.REACT_APP_CARIB_SITE_URL || 'https://carib-recon.org';

const DEFAULT_CARIB_HOSTS = ['carib-recon.org', 'www.carib-recon.org'];

const caribHosts = (process.env.REACT_APP_CARIB_HOSTS || '')
  .split(',')
  .map((h) => h.trim().toLowerCase())
  .filter(Boolean);

const CARIB_HOSTS = caribHosts.length ? caribHosts : DEFAULT_CARIB_HOSTS;

/** True on carib-recon.org or when DO build sets REACT_APP_CRC_SITE=true. */
export const isCaribSite = (hostname = window.location.hostname) =>
  process.env.REACT_APP_CRC_SITE === 'true' ||
  CARIB_HOSTS.includes(hostname.toLowerCase());

/** @deprecated use isCaribSite — kept for existing Gantt imports */
export const isGanttHost = isCaribSite;

export const isCaribMarketingHost = isCaribSite;

export const GANTT_APP_URL =
  process.env.REACT_APP_GANTT_APP_URL || `${CARIB_SITE_URL}/gantt`;

export const GANTT_LOGIN_URL =
  process.env.REACT_APP_LOGIN_URL || `${CARIB_SITE_URL}/login`;
