import { useEffect } from 'react';
import { GANTT_LOGO_PATH } from './GanttLogo';
import { isGanttHost } from './ganttHostUtils';

const EVOME_TITLE = 'Evohome | Real Estate Management';
const EVOME_DESCRIPTION = 'Evohome - Real Estate Upgrade Management Platform';
const GANTT_DESCRIPTION = 'Caribbean Regional Connectivity — project planning and Gantt charts';

let ganttFaviconLink = null;
let ganttAppleTouchLink = null;

const ensureBrandedLink = (rel, existingRef) => {
  if (existingRef?.isConnected) return existingRef;
  const link =
    document.querySelector(`link[rel='${rel}'][data-gantt-branding='true']`) ||
    document.createElement('link');
  link.rel = rel;
  link.type = 'image/png';
  link.setAttribute('data-gantt-branding', 'true');
  if (!link.parentNode) {
    document.head.appendChild(link);
  }
  return link;
};

/** Apply CRC favicon + meta on carib-recon host only. */
export const applyGanttBranding = (appName) => {
  if (!isGanttHost()) return;
  document.title = appName;
  ganttFaviconLink = ensureBrandedLink('icon', ganttFaviconLink);
  ganttFaviconLink.href = GANTT_LOGO_PATH;
  ganttAppleTouchLink = ensureBrandedLink('apple-touch-icon', ganttAppleTouchLink);
  ganttAppleTouchLink.href = GANTT_LOGO_PATH;
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
  if (ganttAppleTouchLink?.isConnected) {
    ganttAppleTouchLink.remove();
  }
  ganttAppleTouchLink = null;
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
