export const API = process.env.REACT_APP_BACKEND_URL + '/api';

export const getAuthHeaders = () => {
  const token = localStorage.getItem('auth_token');
  return token ? { Authorization: `Bearer ${token}` } : {};
};

export const INTENT_LABELS = {
  'create_invoice': 'Create Invoice',
  'create_quote': 'Create Quote',
  'create_message': 'Send Message',
  'send_message': 'Send Message',
  'create_feed_post': 'Post Update',
  'upload_timeline': 'Upload Timeline',
  'extract_invoice': 'Extract Invoice',
  'extract_quote': 'Extract Quote',
  'extract_timeline': 'Extract Timeline',
  'extract_contacts': 'Extract Contacts',
  'extract_invoice_document': 'Extract Invoice',
  'extract_quote_document': 'Extract Quote',
  'extract_timeline_document': 'Extract Timeline',
  'extract_contacts_document': 'Extract Contacts',
  'upload_document': 'Upload Document',
  'unknown': 'General Action'
};

export const getIntentLabel = (intent) => INTENT_LABELS[intent] || intent;

export const formatCurrency = (amount) => {
  return new Intl.NumberFormat('de-CH', { style: 'currency', currency: 'CHF' }).format(amount || 0);
};

export const getConfidenceDisplay = (confidence) => {
  if (confidence >= 0.8) return { label: 'High', color: 'text-emerald-600 bg-emerald-500/10' };
  if (confidence >= 0.5) return { label: 'Medium', color: 'text-amber-600 bg-amber-500/10' };
  return { label: 'Low', color: 'text-red-600 bg-red-500/10' };
};

export const getSuggestedAction = (intent) => {
  switch (intent) {
    case 'create_invoice':
      return { label: 'Create Invoice', path: '/agent/invoices/new' };
    case 'create_quote':
      return { label: 'Create Quote', path: '/agent/quotes/new' };
    case 'send_message':
      return { label: 'Send Message', path: '/agent/feed' };
    case 'create_feed_post':
      return { label: 'Post Update', path: '/agent/feed' };
    case 'upload_timeline':
    case 'extract_timeline':
      return { label: 'Go to Timeline', path: '/agent/timeline' };
    case 'extract_invoice':
      return { label: 'Upload Invoice', path: '/agent/invoices/new' };
    case 'extract_quote':
      return { label: 'Upload Quote', path: '/agent/quotes/new' };
    case 'upload_document':
      return { label: 'Go to Vault', path: '/agent/vault' };
    default:
      return { label: 'View Dashboard', path: '/agent/dashboard-legacy' };
  }
};
