/**
 * Caribbean RE-Connect single-site mode (carib-recon.org).
 * All tools live on one domain: /, /login, /gantt, /map, …
 *
 * app.carib-recon.org is not an app host. app.evo-home.ch is the
 * Customer Management Platform and must not inherit CRC mode from
 * REACT_APP_CRC_SITE (that flag is build-wide on the shared image).
 */
export const CARIB_SITE_URL =
  process.env.REACT_APP_CARIB_SITE_URL || 'https://carib-recon.org';

/** Browser tab title on app.evo-home.ch. Keep in sync with public/index.html. */
export const CMP_DOCUMENT_TITLE = 'Customer Management Platform';

const DEFAULT_CARIB_HOSTS = ['carib-recon.org', 'www.carib-recon.org'];

/** Deleted from the app. Visitors are sent to CARIB_SITE_URL. */
const REMOVED_CARIB_HOSTS = ['app.carib-recon.org'];

/** Evohome customer-management platform. Never treated as the CRC site. */
const EVO_CMP_HOSTS = ['app.evo-home.ch'];

const caribHosts = (process.env.REACT_APP_CARIB_HOSTS || '')
  .split(',')
  .map((h) => h.trim().toLowerCase())
  .filter((h) => h && !REMOVED_CARIB_HOSTS.includes(h));

const CARIB_HOSTS = caribHosts.length ? caribHosts : DEFAULT_CARIB_HOSTS;

export const isRemovedCaribHost = (hostname = '') =>
  REMOVED_CARIB_HOSTS.includes(String(hostname || '').toLowerCase());

export const isEvohomeCmpHost = (hostname = '') =>
  EVO_CMP_HOSTS.includes(String(hostname || '').toLowerCase());

/**
 * True on carib-recon.org / www, or when REACT_APP_CRC_SITE=true on any
 * other host. Never true for app.evo-home.ch or app.carib-recon.org.
 */
export const isCaribSite = (
  hostname = window.location.hostname,
  crcSite = process.env.REACT_APP_CRC_SITE === 'true',
) => {
  const host = String(hostname || '').toLowerCase();
  if (isRemovedCaribHost(host) || isEvohomeCmpHost(host)) return false;
  if (CARIB_HOSTS.includes(host)) return true;
  return crcSite;
};

/** Leave the deleted subdomain. Returns true when navigation has started. */
export const redirectRemovedCaribHost = () => {
  if (typeof window === 'undefined') return false;
  if (!isRemovedCaribHost(window.location.hostname)) return false;
  const { pathname, search, hash } = window.location;
  window.location.replace(`${CARIB_SITE_URL}${pathname}${search}${hash}`);
  return true;
};

/** @deprecated use isCaribSite — kept for existing Gantt imports */
export const isGanttHost = isCaribSite;

export const isCaribMarketingHost = isCaribSite;

export const GANTT_APP_URL =
  process.env.REACT_APP_GANTT_APP_URL || `${CARIB_SITE_URL}/gantt`;

export const GANTT_LOGIN_URL =
  process.env.REACT_APP_LOGIN_URL || `${CARIB_SITE_URL}/login`;
