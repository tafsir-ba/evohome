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
 * Extract canonical error from a failed response.
 * Returns { error, message, request_id, source } or a fallback.
 */
export const parseApiError = async (response) => {
  try {
    const data = await response.json();
    return {
      error: data.error || 'request_failed',
      message: data.message || data.detail || 'An error occurred',
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
