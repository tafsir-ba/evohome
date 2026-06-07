export const parseApiError = (errBody, fallback = 'Request failed') => {
  const detail = errBody?.detail;
  if (typeof detail === 'string') return detail;
  if (Array.isArray(detail)) {
    return detail.map((item) => item?.msg || String(item)).join(', ');
  }
  return fallback;
};

const GANTT_SESSION_KEY = 'gantt_session_id';

/** Stable anonymous session id for public Gantt access (no login). */
export const getGanttSessionId = () => {
  let id = localStorage.getItem(GANTT_SESSION_KEY);
  if (!id) {
    id = crypto.randomUUID();
    localStorage.setItem(GANTT_SESSION_KEY, id);
  }
  return id;
};

/** Auth headers: Bearer token when logged in, else anonymous gantt session. */
export const getGanttHeaders = (extra = {}) => {
  const headers = { ...extra };
  const token = localStorage.getItem('auth_token');
  if (token) {
    headers.Authorization = `Bearer ${token}`;
  } else {
    headers['X-Gantt-Session'] = getGanttSessionId();
  }
  if (!headers['Content-Type'] && !headers['content-type']) {
    headers['Content-Type'] = 'application/json';
  }
  return headers;
};
