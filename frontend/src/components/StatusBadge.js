import { cn } from '../lib/utils';

const statusConfig = {
  'Draft': { className: 'status-draft', label: 'Draft' },
  'Sent': { className: 'status-sent', label: 'Sent' },
  'Change Requested': { className: 'status-change-requested', label: 'Change Requested' },
  'Approved': { className: 'status-approved', label: 'Approved' },
  'Invoiced': { className: 'status-invoiced', label: 'Invoiced' },
  'Payment Pending': { className: 'status-sent', label: 'Payment Pending' },
  'Paid': { className: 'status-paid', label: 'Paid' },
  'Declined': { className: 'status-declined', label: 'Declined' },
};

export const StatusBadge = ({ status, className }) => {
  const config = statusConfig[status] || { className: 'status-draft', label: status };
  
  return (
    <span className={cn('status-badge', config.className, className)} data-testid={`status-badge-${status?.toLowerCase().replace(' ', '-')}`}>
      {config.label}
    </span>
  );
};

export const formatCurrency = (amount, currency = 'CHF') => {
  return new Intl.NumberFormat('de-CH', {
    style: 'currency',
    currency: currency,
    minimumFractionDigits: 2,
  }).format(amount);
};

export const formatDate = (dateString) => {
  if (!dateString) return '-';
  const date = new Date(dateString);
  return new Intl.DateTimeFormat('de-CH', {
    day: '2-digit',
    month: 'short',
    year: 'numeric'
  }).format(date);
};

export const formatDateTime = (dateString) => {
  if (!dateString) return '-';
  const date = new Date(dateString);
  return new Intl.DateTimeFormat('de-CH', {
    day: '2-digit',
    month: 'short',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit'
  }).format(date);
};
