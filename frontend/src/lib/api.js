/**
 * Authenticated fetch wrapper.
 * Adds Authorization header from localStorage token alongside credentials: 'include'.
 * Use this for ALL API calls to ensure auth works in production (cookies + bearer token).
 */
const API = process.env.REACT_APP_BACKEND_URL + '/api';

export const authFetch = async (url, options = {}) => {
  const token = localStorage.getItem('auth_token');
  const headers = { ...options.headers };

  if (token && !headers['Authorization']) {
    headers['Authorization'] = `Bearer ${token}`;
  }

  return fetch(url, {
    ...options,
    credentials: 'include',
    headers,
  });
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
