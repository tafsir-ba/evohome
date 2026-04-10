import { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { AgentLayout } from '../../components/AgentLayout';
import { StatusBadge, formatCurrency, formatDate } from '../../components/StatusBadge';
import { Card, CardContent } from '../../components/ui/card';
import { Button } from '../../components/ui/button';
import { Input } from '../../components/ui/input';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../../components/ui/select';
import { toast } from 'sonner';
import { useSettings } from '../../context/SettingsContext';
import { 
  Search, 
  Receipt,
  ArrowRight,
  Download,
  Plus,
  Trash2
} from 'lucide-react';

const API = process.env.REACT_APP_BACKEND_URL + '/api';

export const AgentInvoices = () => {
  const { t } = useSettings();
  const [invoices, setInvoices] = useState([]);
  const [loading, setLoading] = useState(true);
  const [searchQuery, setSearchQuery] = useState('');
  const [statusFilter, setStatusFilter] = useState('all');
  const [deletingId, setDeletingId] = useState(null);

  useEffect(() => {
    fetchInvoices();
  }, []);

  const fetchInvoices = async () => {
    try {
      const response = await fetch(`${API}/documents?doc_type=invoice`, { credentials: 'include' });
      if (response.ok) {
        setInvoices(await response.json());
      }
    } catch (error) {
      console.error('Failed to fetch invoices:', error);
      toast.error('Failed to load invoices');
    } finally {
      setLoading(false);
    }
  };

  const handleDelete = async (e, invoiceId, status) => {
    e.preventDefault();
    e.stopPropagation();
    
    if (status !== 'Draft') {
      toast.error('Can only delete drafts');
      return;
    }
    
    if (!window.confirm('Delete this invoice? This cannot be undone.')) {
      return;
    }
    
    setDeletingId(invoiceId);
    try {
      const response = await fetch(`${API}/documents/${invoiceId}`, {
        method: 'DELETE',
        credentials: 'include'
      });
      
      if (response.ok) {
        toast.success('Invoice deleted');
        setInvoices(invoices.filter(i => i.document_id !== invoiceId));
      } else {
        const error = await response.json();
        toast.error(error.detail || 'Failed to delete');
      }
    } catch (error) {
      toast.error('Delete failed');
    } finally {
      setDeletingId(null);
    }
  };

  const handleDownloadPDF = async (e, invoiceId, invoiceNumber) => {
    e.preventDefault();
    e.stopPropagation();
    
    try {
      const response = await fetch(`${API}/documents/${invoiceId}/source-pdf`, { credentials: 'include' });
      if (response.ok) {
        const blob = await response.blob();
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `invoice_${invoiceNumber}.pdf`;
        document.body.appendChild(a);
        a.click();
        window.URL.revokeObjectURL(url);
        document.body.removeChild(a);
        toast.success('PDF downloaded');
      } else {
        toast.error('Failed to download PDF');
      }
    } catch (error) {
      toast.error('Download failed');
    }
  };

  const filteredInvoices = invoices.filter(invoice => {
    const invoiceNumber = invoice.document_number || '';
    const matchesSearch = invoice.title.toLowerCase().includes(searchQuery.toLowerCase()) ||
                          invoiceNumber.toLowerCase().includes(searchQuery.toLowerCase()) ||
                          invoice.unit_reference.toLowerCase().includes(searchQuery.toLowerCase());
    const matchesStatus = statusFilter === 'all' || invoice.status === statusFilter;
    return matchesSearch && matchesStatus;
  });

  // Updated statuses for unified document model
  const statuses = ['all', 'Draft', 'Sent', 'Paid'];

  if (loading) {
    return (
      <AgentLayout>
        <div className="animate-pulse space-y-6">
          <div className="h-8 w-48 bg-gray-200 rounded" />
          <div className="space-y-4">
            {[1, 2, 3].map(i => (
              <div key={i} className="h-24 bg-gray-200 rounded-sm" />
            ))}
          </div>
        </div>
      </AgentLayout>
    );
  }

  return (
    <AgentLayout>
      <div className="space-y-6" data-testid="agent-invoices">
        {/* Header */}
        <div className="flex flex-col sm:flex-row sm:items-start sm:justify-between gap-4">
          <div>
            <h1 className="text-2xl sm:text-3xl font-outfit font-semibold text-foreground tracking-tight">
              {t('documents.invoices')}
            </h1>
            <p className="text-muted-foreground mt-1">{invoices.length} {t('documents.invoices').toLowerCase()}</p>
          </div>
          <Link to="/agent/invoices/new">
            <Button className="rounded-lg" data-testid="create-invoice-btn">
              <Plus className="w-4 h-4 mr-2" />
              {t('documents.newInvoice')}
            </Button>
          </Link>
        </div>

        {/* Filters */}
        <div className="flex flex-col sm:flex-row gap-4">
          <div className="relative flex-1 max-w-md">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
            <Input
              placeholder={`${t('common.search')} ${t('documents.invoices').toLowerCase()}...`}
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="pl-10 rounded-lg border-border"
              data-testid="search-input"
            />
          </div>
          <Select value={statusFilter} onValueChange={setStatusFilter}>
            <SelectTrigger className="w-[180px] rounded-lg" data-testid="status-filter">
              <SelectValue placeholder={t('documents.status')} />
            </SelectTrigger>
            <SelectContent>
              {statuses.map(status => (
                <SelectItem key={status} value={status}>
                  {status === 'all' ? t('common.viewAll') : status}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>

        {/* Invoices List */}
        <div className="space-y-4">
          {filteredInvoices.length > 0 ? (
            filteredInvoices.map((invoice) => {
              const id = invoice.document_id;
              const number = invoice.document_number;
              const amount = invoice.amount;
              return (
              <Link 
                key={id} 
                to={`/agent/invoices/${id}`}
                data-testid={`invoice-item-${id}`}
              >
                <Card className="border-[#E2E8F0] rounded-sm hover:border-primary/20 transition-colors">
                  <CardContent className="p-6">
                    <div className="flex items-start justify-between">
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-3">
                          <h3 className="font-medium text-[#1A1A1A] truncate">{invoice.title}</h3>
                          <StatusBadge status={invoice.status} />
                        </div>
                        <p className="text-sm text-muted-foreground mt-1">
                          {number} · {invoice.unit_reference}
                        </p>
                        <p className="text-sm text-muted-foreground mt-0.5">
                          Due {formatDate(invoice.due_date)}
                          {invoice.paid_date && ` · Paid ${formatDate(invoice.paid_date)}`}
                        </p>
                      </div>
                      <div className="flex items-center gap-2">
                        <div className="text-right mr-2">
                          <p className="text-lg font-semibold text-[#1A1A1A]">{formatCurrency(amount)}</p>
                        </div>
                        <Button
                          variant="ghost"
                          size="icon"
                          className="rounded-sm"
                          onClick={(e) => handleDownloadPDF(e, id, number)}
                          data-testid={`download-pdf-${id}`}
                          title="Download PDF"
                        >
                          <Download className="w-4 h-4" />
                        </Button>
                        {invoice.status === 'Draft' && (
                          <Button
                            variant="ghost"
                            size="icon"
                            className="rounded-sm text-destructive hover:text-destructive hover:bg-destructive/10"
                            onClick={(e) => handleDelete(e, id, invoice.status)}
                            disabled={deletingId === id}
                            data-testid={`delete-invoice-${id}`}
                            title="Delete draft"
                          >
                            <Trash2 className="w-4 h-4" />
                          </Button>
                        )}
                        <ArrowRight className="w-4 h-4 text-muted-foreground" />
                      </div>
                    </div>
                  </CardContent>
                </Card>
              </Link>
            );})
          ) : (
            <div className="text-center py-12">
              <Receipt className="w-12 h-12 text-muted-foreground/30 mx-auto mb-4" />
              <p className="text-muted-foreground">
                {searchQuery || statusFilter !== 'all' ? 'No invoices found matching your filters' : 'No invoices yet'}
              </p>
              <p className="text-sm text-muted-foreground mt-2">
                Invoices are automatically generated when quotes are approved
              </p>
            </div>
          )}
        </div>
      </div>
    </AgentLayout>
  );
};
