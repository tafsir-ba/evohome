import { isGanttHost } from '../components/gantt/ganttHostUtils';

/**
 * API base URL. On app.carib-recon.org use same-origin /api (DO routes to backend).
 * On evohome CMP use REACT_APP_BACKEND_URL to avoid cross-origin CORS blocks.
 */
export function getApiBaseUrl() {
  if (typeof window !== 'undefined' && isGanttHost()) {
    return `${window.location.origin}/api`;
  }
  const base = (process.env.REACT_APP_BACKEND_URL || '').replace(/\/$/, '');
  return `${base}/api`;
}

/**
 * Authenticated fetch wrapper.
 * Adds Authorization header from localStorage token alongside credentials: 'include'.
 * Captures X-Request-ID from responses for error correlation.
 * Use this for ALL API calls to ensure auth works in production (cookies + bearer token).
 */
const API = process.env.REACT_APP_BACKEND_URL + '/api';

export const authFetch = async (url, options = {}) => {
  const token = localStorage.getItem('auth_token');
  const headers = { ...options.headers };

  if (token && !headers['Authorization']) {
    headers['Authorization'] = `Bearer ${token}`;
  }

  const response = await fetch(url, {
    ...options,
    credentials: 'include',
    headers,
  });

  // Capture request_id for error correlation
  if (!response.ok) {
    const requestId = response.headers.get('X-Request-ID');
    if (requestId) {
      response._requestId = requestId;
    }
  }

  return response;
};

/**
 * Pick human-readable message from API JSON (canonical shape or legacy FastAPI).
 */
function pickErrorMessage(data) {
  if (!data || typeof data !== 'object') return null;
  if (typeof data.message === 'string' && data.message.trim()) return data.message.trim();
  const d = data.detail;
  if (typeof d === 'string' && d.trim()) return d.trim();
  if (Array.isArray(d) && d.length) {
    return d
      .map((e) => `${(e.loc || []).join('.')}: ${e.msg || 'invalid'}`)
      .filter(Boolean)
      .join('; ');
  }
  if (d && typeof d === 'object' && typeof d.message === 'string' && d.message.trim()) {
    return d.message.trim();
  }
  return null;
}

/**
 * Extract canonical error from a failed response.
 * Returns { error, message, request_id, source } or a fallback.
 */
export const parseApiError = async (response) => {
  try {
    const data = await response.json();
    const message = pickErrorMessage(data) || `HTTP ${response.status}`;
    return {
      error: data.error || 'request_failed',
      message,
      request_id: data.request_id || response._requestId || null,
      source: data.source || 'unknown',
    };
  } catch {
    return {
      error: 'request_failed',
      message: `HTTP ${response.status}`,
      request_id: response._requestId || null,
      source: 'unknown',
    };
  }
};

/**
 * Shorthand for JSON POST/PUT/DELETE with auth.
 */
export const authJsonFetch = async (url, method, body) => {
  return authFetch(url, {
    method,
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
};

export { API };
