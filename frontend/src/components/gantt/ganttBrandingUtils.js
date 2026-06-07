import { useEffect } from 'react';
import { isGanttHost } from './ganttHostUtils';

const GANTT_FAVICON = '/crc-favicon.svg';
const EVOME_TITLE = 'Evohome | Real Estate Management';
const EVOME_DESCRIPTION = 'Evohome - Real Estate Upgrade Management Platform';
const GANTT_DESCRIPTION = 'Caribbean Regional Connectivity — project planning and Gantt charts';

let ganttFaviconLink = null;

const ensureFaviconLink = () => {
  if (ganttFaviconLink?.isConnected) return ganttFaviconLink;
  ganttFaviconLink =
    document.querySelector("link[rel='icon'][data-gantt-branding='true']") ||
    document.createElement('link');
  ganttFaviconLink.rel = 'icon';
  ganttFaviconLink.type = 'image/svg+xml';
  ganttFaviconLink.setAttribute('data-gantt-branding', 'true');
  if (!ganttFaviconLink.parentNode) {
    document.head.appendChild(ganttFaviconLink);
  }
  return ganttFaviconLink;
};

/** Apply CRC favicon + meta on carib-recon host only. */
export const applyGanttBranding = (appName) => {
  if (!isGanttHost()) return;
  document.title = appName;
  const link = ensureFaviconLink();
  link.href = GANTT_FAVICON;
  const meta = document.querySelector('meta[name="description"]');
  if (meta) meta.setAttribute('content', GANTT_DESCRIPTION);
};

/** Restore evohome defaults when leaving gantt-branded views. */
export const clearGanttBranding = () => {
  document.title = EVOME_TITLE;
  if (ganttFaviconLink?.isConnected) {
    ganttFaviconLink.remove();
  }
  ganttFaviconLink = null;
  const meta = document.querySelector('meta[name="description"]');
  if (meta) meta.setAttribute('content', EVOME_DESCRIPTION);
};

/** Hook: sync title + favicon from canonical app name on gantt host. */
export const useGanttBranding = (appName) => {
  useEffect(() => {
    if (!isGanttHost() || !appName) return undefined;
    applyGanttBranding(appName);
    return clearGanttBranding;
  }, [appName]);
};
