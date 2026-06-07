export const parseApiError = (errBody, fallback = 'Request failed') => {
  const detail = errBody?.detail;
  if (typeof detail === 'string') return detail;
  if (Array.isArray(detail)) {
    return detail.map((item) => item?.msg || String(item)).join(', ');
  }
  return fallback;
};

/** Auth headers for Gantt API (session cookie + optional bearer token). */
export const getGanttHeaders = (extra = {}) => {
  const headers = { ...extra };
  const token = localStorage.getItem('auth_token');
  if (token) {
    headers.Authorization = `Bearer ${token}`;
  }
  if (!headers['Content-Type'] && !headers['content-type']) {
    headers['Content-Type'] = 'application/json';
  }
  return headers;
};
