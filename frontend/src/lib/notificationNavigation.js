/**
 * Normalize notification deep links for in-app navigation.
 * Legacy rows may use /buyer?... instead of /buyer/dashboard?...
 */
export function normalizeNotificationPath(link, role) {
  if (!link || typeof link !== 'string') {
    if (role === 'agent') return '/agent/home';
    return '/buyer/dashboard';
  }
  let path = link.trim();
  if (path.startsWith('/buyer?') || path === '/buyer') {
    const rest = path.startsWith('/buyer?') ? path.slice(7) : '';
    path = rest ? `/buyer/dashboard?${rest}` : '/buyer/dashboard';
  }
  return path;
}
