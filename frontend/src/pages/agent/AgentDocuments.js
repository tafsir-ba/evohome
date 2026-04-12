import { useState, useEffect } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
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
  Plus, Search, FileText, ArrowRight, Download, Trash2
} from 'lucide-react';

const API = process.env.REACT_APP_BACKEND_URL + '/api';

const getAuthHeaders = () => {
  const token = localStorage.getItem('auth_token');
  return token ? { 'Authorization': `Bearer ${token}` } : {};
};

const STATUSES = ['all', 'Draft', 'Sent', 'Change Requested', 'Approved', 'Rejected', 'Paid'];

export const AgentDocuments = () => {
  const { t } = useSettings();
  const [searchParams] = useSearchParams();
  const category = searchParams.get('category') || 'all';
  
  const [documents, setDocuments] = useState([]);
  const [loading, setLoading] = useState(true);
  const [searchQuery, setSearchQuery] = useState('');
  const [statusFilter, setStatusFilter] = useState('all');
  const [categoryFilter, setCategoryFilter] = useState(category);
  const [deletingId, setDeletingId] = useState(null);

  useEffect(() => {
    if (category !== 'all') setCategoryFilter(category);
  }, [category]);

  useEffect(() => {
    fetchDocuments();
  }, []);

  const fetchDocuments = async () => {
    try {
      const response = await fetch(`${API}/documents`, { credentials: 'include', headers: getAuthHeaders() });
      if (response.ok) {
        setDocuments(await response.json());
      }
    } catch (error) {
      console.error('Failed to fetch documents:', error);
      toast.error('Failed to load documents');
    } finally {
      setLoading(false);
    }
  };

  const handleDelete = async (e, docId, docStatus) => {
    e.preventDefault();
    e.stopPropagation();
    if (docStatus !== 'Draft') {
      toast.error('Can only delete drafts');
      return;
    }
    if (!window.confirm('Delete this document? This cannot be undone.')) return;
    
    setDeletingId(docId);
    try {
      const response = await fetch(`${API}/documents/${docId}`, {
        method: 'DELETE', credentials: 'include', headers: getAuthHeaders()
      });
      if (response.ok) {
        toast.success('Document deleted');
        setDocuments(documents.filter(d => d.document_id !== docId));
      } else {
        const error = await response.json();
        toast.error(error.message || error.detail || 'Failed to delete');
      }
    } catch {
      toast.error('Delete failed');
    } finally {
      setDeletingId(null);
    }
  };

  const handleDownloadPDF = async (e, docId, docNumber) => {
    e.preventDefault();
    e.stopPropagation();
    try {
      const response = await fetch(`${API}/documents/${docId}/source-pdf`, { credentials: 'include', headers: getAuthHeaders() });
      if (response.ok) {
        const blob = await response.blob();
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `document_${docNumber}.pdf`;
        document.body.appendChild(a);
        a.click();
        window.URL.revokeObjectURL(url);
        document.body.removeChild(a);
        toast.success('PDF downloaded');
      } else {
        toast.error('Failed to download PDF');
      }
    } catch {
      toast.error('Download failed');
    }
  };

  const filtered = documents.filter(doc => {
    const matchesCategory = categoryFilter === 'all' || doc.type === categoryFilter;
    const matchesSearch = !searchQuery || 
      (doc.title || '').toLowerCase().includes(searchQuery.toLowerCase()) ||
      (doc.document_number || '').toLowerCase().includes(searchQuery.toLowerCase()) ||
      (doc.client_name || '').toLowerCase().includes(searchQuery.toLowerCase()) ||
      (doc.unit_reference || '').toLowerCase().includes(searchQuery.toLowerCase());
    const matchesStatus = statusFilter === 'all' || doc.status === statusFilter;
    return matchesCategory && matchesSearch && matchesStatus;
  });

  const pageTitle = categoryFilter === 'quote' ? t('nav.quotes') 
    : categoryFilter === 'invoice' ? t('nav.invoices') 
    : t('nav.quotes') + ' / ' + t('nav.invoices');

  if (loading) {
    return (
      <AgentLayout>
        <div className="animate-pulse space-y-6">
          <div className="h-8 w-48 bg-gray-200 rounded" />
          <div className="space-y-4">
            {[1, 2, 3].map(i => <div key={i} className="h-24 bg-gray-200 rounded-sm" />)}
          </div>
        </div>
      </AgentLayout>
    );
  }

  return (
    <AgentLayout>
      <div className="space-y-6" data-testid="agent-documents">
        {/* Header */}
        <div className="flex flex-col sm:flex-row sm:items-start sm:justify-between gap-4">
          <div>
            <h1 className="text-2xl sm:text-3xl font-outfit font-semibold text-foreground tracking-tight">
              {pageTitle}
            </h1>
            <p className="text-muted-foreground mt-1">{filtered.length} document{filtered.length !== 1 ? 's' : ''}</p>
          </div>
          <div className="flex gap-2">
            <Link to="/agent/documents/new?type=quote">
              <Button className="rounded-lg" data-testid="create-quote-btn">
                <Plus className="w-4 h-4 mr-2" />
                New Quote
              </Button>
            </Link>
            <Link to="/agent/documents/new?type=invoice">
              <Button variant="outline" className="rounded-lg" data-testid="create-invoice-btn">
                <Plus className="w-4 h-4 mr-2" />
                New Invoice
              </Button>
            </Link>
          </div>
        </div>

        {/* Filters */}
        <div className="flex flex-col sm:flex-row gap-4">
          <div className="relative flex-1 max-w-md">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
            <Input
              placeholder="Search documents..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="pl-10 rounded-lg"
              data-testid="search-input"
            />
          </div>
          <Select value={categoryFilter} onValueChange={setCategoryFilter}>
            <SelectTrigger className="w-[150px] rounded-lg" data-testid="category-filter">
              <SelectValue placeholder="Category" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">All Types</SelectItem>
              <SelectItem value="quote">Quotes</SelectItem>
              <SelectItem value="invoice">Invoices</SelectItem>
            </SelectContent>
          </Select>
          <Select value={statusFilter} onValueChange={setStatusFilter}>
            <SelectTrigger className="w-[180px] rounded-lg" data-testid="status-filter">
              <SelectValue placeholder="Status" />
            </SelectTrigger>
            <SelectContent>
              {STATUSES.map(status => (
                <SelectItem key={status} value={status}>
                  {status === 'all' ? 'All Statuses' : status}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>

        {/* Documents List */}
        <div className="space-y-4">
          {filtered.length > 0 ? (
            filtered.map((doc) => {
              const id = doc.document_id;
              return (
                <Link 
                  key={id} 
                  to={`/agent/documents/${id}`}
                  data-testid={`document-item-${id}`}
                >
                  <Card className="border-[#E2E8F0] rounded-sm hover:border-primary/20 transition-colors">
                    <CardContent className="p-6">
                      <div className="flex items-start justify-between">
                        <div className="flex-1 min-w-0">
                          <div className="flex items-center gap-3">
                            <span className={`text-xs font-medium px-2 py-0.5 rounded ${doc.type === 'invoice' ? 'bg-blue-100 text-blue-700' : 'bg-emerald-100 text-emerald-700'}`}>
                              {doc.type === 'invoice' ? 'Invoice' : 'Quote'}
                            </span>
                            <h3 className="font-medium text-foreground truncate">{doc.title}</h3>
                            <StatusBadge status={doc.status} />
                          </div>
                          <p className="text-sm text-muted-foreground mt-1">
                            {formatDocContext({ document_number: doc.document_number, client_name: doc.client_name, project_name: doc.project_name, unit_reference: doc.unit_reference })}
                          </p>
                          <p className="text-sm text-muted-foreground mt-0.5">
                            Created {formatDate(doc.created_at)}
                            {doc.due_date && ` · Due ${formatDate(doc.due_date)}`}
                          </p>
                          {doc.change_request_comment && (
                            <p className="text-sm text-orange-600 mt-1 italic">CR: "{doc.change_request_comment}"</p>
                          )}
                        </div>
                        <div className="flex items-center gap-2">
                          <div className="text-right mr-2">
                            <p className="text-lg font-semibold text-foreground">{formatCurrency(doc.amount)}</p>
                          </div>
                          {doc.pdf_stored_filename && (
                            <Button variant="ghost" size="icon" className="rounded-sm"
                              onClick={(e) => handleDownloadPDF(e, id, doc.document_number)}
                              data-testid={`download-pdf-${id}`} title="Download PDF">
                              <Download className="w-4 h-4" />
                            </Button>
                          )}
                          {(doc.status === 'Draft' || doc.status === 'Rejected') && (
                            <Button variant="ghost" size="icon"
                              className="rounded-sm text-destructive hover:text-destructive hover:bg-destructive/10"
                              onClick={(e) => handleDelete(e, id, doc.status)}
                              disabled={deletingId === id}
                              data-testid={`delete-doc-${id}`} title="Delete">
                              <Trash2 className="w-4 h-4" />
                            </Button>
                          )}
                          <ArrowRight className="w-4 h-4 text-muted-foreground" />
                        </div>
                      </div>
                    </CardContent>
                  </Card>
                </Link>
              );
            })
          ) : (
            <div className="text-center py-12">
              <FileText className="w-12 h-12 text-muted-foreground/30 mx-auto mb-4" />
              <p className="text-muted-foreground">
                {searchQuery || statusFilter !== 'all' || categoryFilter !== 'all' ? 'No documents found matching your filters' : 'No documents yet'}
              </p>
              {!searchQuery && statusFilter === 'all' && (
                <Link to="/agent/documents/new?type=quote">
                  <Button className="mt-4 rounded-sm">Create your first document</Button>
                </Link>
              )}
            </div>
          )}
        </div>
      </div>
    </AgentLayout>
  );
};
