/** Debug Console — API layer */
const API_BASE = window.location.origin + '/api/internal/debug';
let SECRET = sessionStorage.getItem('debug_secret') || '';

function getHeaders() {
  return {'Authorization': 'Bearer ' + SECRET, 'Content-Type': 'application/json'};
}

async function apiFetch(path, opts = {}) {
  try {
    const res = await fetch(API_BASE + path, {headers: getHeaders(), ...opts});
    if (res.status === 401) { sessionStorage.removeItem('debug_secret'); SECRET = ''; render(); return null; }
    if (!res.ok) { console.error('Debug API error:', res.status, await res.text()); return null; }
    return res.json();
  } catch (e) { console.error('Debug API fetch failed:', e); return null; }
}

function setSecret(s) { SECRET = s; sessionStorage.setItem('debug_secret', s); }
