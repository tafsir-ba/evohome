export const parseApiError = (errBody, fallback = 'Request failed') => {
  const detail = errBody?.detail;
  if (typeof detail === 'string') return detail;
  if (Array.isArray(detail)) {
    return detail.map((item) => item?.msg || String(item)).join(', ');
  }
  return fallback;
};
