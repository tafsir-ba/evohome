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
import { formatDocContext } from '../../lib/utils';
import { 
  Plus, 
  Search, 
  FileText,
  ArrowRight,
  Download,
  Trash2,
  Edit
} from 'lucide-react';

const API = process.env.REACT_APP_BACKEND_URL + '/api';

const getAuthHeaders = () => {
  const token = localStorage.getItem('auth_token');
  return token ? { 'Authorization': `Bearer ${token}` } : {};
};

export const AgentQuotes = () => {
  const { t } = useSettings();
  const [quotes, setQuotes] = useState([]);
  const [loading, setLoading] = useState(true);
  const [searchQuery, setSearchQuery] = useState('');
  const [statusFilter, setStatusFilter] = useState('all');
  const [deletingId, setDeletingId] = useState(null);

  useEffect(() => {
    fetchQuotes();
  }, []);

  const fetchQuotes = async () => {
    try {
      const response = await fetch(`${API}/documents?doc_type=quote`, { credentials: 'include', headers: getAuthHeaders() });
      if (response.ok) {
        setQuotes(await response.json());
      }
    } catch (error) {
      console.error('Failed to fetch quotes:', error);
      toast.error('Failed to load quotes');
    } finally {
      setLoading(false);
    }
  };

  const handleDelete = async (e, quoteId, quoteStatus) => {
    e.preventDefault();
    e.stopPropagation();
    
    if (quoteStatus !== 'Draft') {
      toast.error('Can only delete drafts');
      return;
    }
    
    if (!window.confirm('Delete this quote? This cannot be undone.')) {
      return;
    }
    
    setDeletingId(quoteId);
    try {
      const response = await fetch(`${API}/documents/${quoteId}`, {
        method: 'DELETE',
        credentials: 'include'
      });
      
      if (response.ok) {
        toast.success('Quote deleted');
        setQuotes(quotes.filter(q => q.document_id !== quoteId));
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

  const handleDownloadPDF = async (e, quoteId, quoteNumber) => {
    e.preventDefault();
    e.stopPropagation();
    
    try {
      const response = await fetch(`${API}/documents/${quoteId}/source-pdf`, { credentials: 'include', headers: getAuthHeaders() });
      if (response.ok) {
        const blob = await response.blob();
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `quote_${quoteNumber}.pdf`;
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

  const filteredQuotes = quotes.filter(quote => {
    const quoteNumber = quote.document_number || '';
    const matchesSearch = quote.title.toLowerCase().includes(searchQuery.toLowerCase()) ||
                          quoteNumber.toLowerCase().includes(searchQuery.toLowerCase()) ||
                          quote.unit_reference.toLowerCase().includes(searchQuery.toLowerCase());
    const matchesStatus = statusFilter === 'all' || quote.status === statusFilter;
    return matchesSearch && matchesStatus;
  });

  // Updated statuses for unified document model
  const statuses = ['all', 'Draft', 'Sent', 'Change Requested', 'Approved', 'Rejected'];

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
      <div className="space-y-6" data-testid="agent-quotes">
        {/* Header */}
        <div className="flex flex-col sm:flex-row sm:items-start sm:justify-between gap-4">
          <div>
            <h1 className="text-2xl sm:text-3xl font-outfit font-semibold text-foreground tracking-tight">
              {t('documents.quotes')}
            </h1>
            <p className="text-muted-foreground mt-1">{quotes.length} {t('documents.quotes').toLowerCase()}</p>
          </div>
          <Link to="/agent/quotes/new">
            <Button className="rounded-lg" data-testid="create-quote-btn">
              <Plus className="w-4 h-4 mr-2" />
              {t('documents.newQuote')}
            </Button>
          </Link>
        </div>

        {/* Filters */}
        <div className="flex flex-col sm:flex-row gap-4">
          <div className="relative flex-1 max-w-md">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
            <Input
              placeholder={`${t('common.search')} ${t('documents.quotes').toLowerCase()}...`}
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="pl-10 rounded-lg"
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
                  {status === 'all' ? t('common.viewAll') : t(`status.${status.toLowerCase().replace(' ', '')}`) || status}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>

        {/* Quotes List */}
        <div className="space-y-4">
          {filteredQuotes.length > 0 ? (
            filteredQuotes.map((quote) => {
              const id = quote.document_id;
              const number = quote.document_number;
              const amount = quote.amount;
              return (
              <Link 
                key={id} 
                to={`/agent/quotes/${id}`}
                data-testid={`quote-item-${id}`}
              >
                <Card className="border-[#E2E8F0] rounded-sm hover:border-primary/20 transition-colors">
                  <CardContent className="p-6">
                    <div className="flex items-start justify-between">
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-3">
                          <h3 className="font-medium text-[#1A1A1A] truncate">{quote.title}</h3>
                          <StatusBadge status={quote.status} />
                        </div>
                        <p className="text-sm text-muted-foreground mt-1">
                          {formatDocContext({ document_number: number, client_name: quote.client_name, project_name: quote.project_name, unit_reference: quote.unit_reference })}
                        </p>
                        <p className="text-sm text-muted-foreground mt-0.5">
                          Created {formatDate(quote.created_at)}
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
                        {quote.status === 'Draft' && (
                          <Button
                            variant="ghost"
                            size="icon"
                            className="rounded-sm text-destructive hover:text-destructive hover:bg-destructive/10"
                            onClick={(e) => handleDelete(e, id, quote.status)}
                            disabled={deletingId === id}
                            data-testid={`delete-quote-${id}`}
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
              <FileText className="w-12 h-12 text-muted-foreground/30 mx-auto mb-4" />
              <p className="text-muted-foreground">
                {searchQuery || statusFilter !== 'all' ? 'No quotes found matching your filters' : 'No quotes yet'}
              </p>
              {!searchQuery && statusFilter === 'all' && (
                <Link to="/agent/quotes/new">
                  <Button className="mt-4 bg-primary hover:bg-primary/90 rounded-sm">
                    Create your first quote
                  </Button>
                </Link>
              )}
            </div>
          )}
        </div>
      </div>
    </AgentLayout>
  );
};
