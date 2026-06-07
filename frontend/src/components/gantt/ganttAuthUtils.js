import { useEffect, useState } from 'react';
import { getApiBaseUrl } from '../../lib/api';
import { isGanttHost, GANTT_APP_NAME } from './ganttHostUtils';

export const GANTT_POST_AUTH_PATH = '/gantt';

/** Bootstrap fallback when /gantt/config is unreachable (matches backend default). */
export const GANTT_AUTH_ROLE = 'agent';

const DEFAULT_PUBLIC_CONFIG = {
  app_name: GANTT_APP_NAME,
  requires_auth: true,
  default_auth_role: GANTT_AUTH_ROLE,
};

export const getPostAuthPath = (role) => {
  if (isGanttHost()) return GANTT_POST_AUTH_PATH;
  return role === 'agent' ? '/agent/home' : '/buyer/dashboard';
};

/** Public gantt config from /gantt/config (no auth required). */
export const useGanttPublicConfig = () => {
  const [config, setConfig] = useState(DEFAULT_PUBLIC_CONFIG);
  useEffect(() => {
    let cancelled = false;
    fetch(`${getApiBaseUrl()}/gantt/config`, { credentials: 'include' })
      .then((res) => (res.ok ? res.json() : null))
      .then((data) => {
        if (!cancelled && data) {
          setConfig({
            app_name: data.app_name || GANTT_APP_NAME,
            requires_auth: data.requires_auth !== false,
            default_auth_role: data.default_auth_role || GANTT_AUTH_ROLE,
          });
        }
      })
      .catch(() => {});
    return () => {
      cancelled = true;
    };
  }, []);
  return config;
};

/** @deprecated Use useGanttPublicConfig().app_name */
export const useGanttAppName = () => useGanttPublicConfig().app_name;
