import { useEffect, useState } from 'react';
import { isGanttHost, GANTT_APP_NAME } from './ganttHostUtils';

const API = process.env.REACT_APP_BACKEND_URL + '/api';

export const GANTT_POST_AUTH_PATH = '/gantt';

/** Default role for CRC Gantt Chart sign-in (agent accounts). */
export const GANTT_AUTH_ROLE = 'agent';

export const getPostAuthPath = (role) => {
  if (isGanttHost()) return GANTT_POST_AUTH_PATH;
  return role === 'agent' ? '/agent/home' : '/buyer/dashboard';
};

/** Canonical app name from /gantt/config with local bootstrap fallback. */
export const useGanttAppName = () => {
  const [appName, setAppName] = useState(GANTT_APP_NAME);
  useEffect(() => {
    let cancelled = false;
    fetch(`${API}/gantt/config`, { credentials: 'include' })
      .then((res) => (res.ok ? res.json() : null))
      .then((config) => {
        if (!cancelled && config?.app_name) setAppName(config.app_name);
      })
      .catch(() => {});
    return () => {
      cancelled = true;
    };
  }, []);
  return appName;
};
