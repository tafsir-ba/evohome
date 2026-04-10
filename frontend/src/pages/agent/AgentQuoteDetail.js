import { useState, useEffect } from 'react';
import { useParams, useNavigate, Link } from 'react-router-dom';
import { AgentLayout } from '../../components/AgentLayout';
import { StatusBadge, formatCurrency, formatDate } from '../../components/StatusBadge';
import { Card, CardContent, CardHeader, CardTitle } from '../../components/ui/card';
import { Button } from '../../components/ui/button';
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from '../../components/ui/alert-dialog';
import { toast } from 'sonner';
import { useSettings } from '../../context/SettingsContext';
import { 
  ArrowLeft, 
  Download, 
  Send,
  Pencil,
  Trash2,
  Building2,
  MapPin,
  Calendar,
  MessageSquare,
  User
} from 'lucide-react';

const API = process.env.REACT_APP_BACKEND_URL + '/api';

export const AgentQuoteDetail = () => {
  const { t } = useSettings();
  const { quoteId } = useParams();
  const navigate = useNavigate();
  const [quote, setQuote] = useState(null);
  const [loading, setLoading] = useState(true);
  const [sendLoading, setSendLoading] = useState(false);
  const [showDeleteDialog, setShowDeleteDialog] = useState(false);
  const [deleting, setDeleting] = useState(false);

  useEffect(() => {
    fetchQuote();
  }, [quoteId]);

  const fetchQuote = async () => {
    try {
      // Use unified documents endpoint
      const response = await fetch(`${API}/documents/${quoteId}`, { credentials: 'include' });
      if (response.ok) {
        setQuote(await response.json());
      } else {
        toast.error('Quote not found');
        navigate('/agent/quotes');
      }
    } catch (error) {
      console.error('Failed to fetch quote:', error);
      toast.error('Failed to load quote');
    } finally {
      setLoading(false);
    }
  };

  const handleSend = async () => {
    setSendLoading(true);
    try {
      const response = await fetch(`${API}/documents/${quoteId}/send`, {
        method: 'POST',
        credentials: 'include'
      });

      const data = await response.json();
      
      if (response.ok) {
        // Show detailed delivery status
        if (data.delivery?.email_sent) {
          toast.success(`Quote sent to ${data.recipient?.name || 'buyer'}. Email notification delivered.`);
        } else if (data.warnings?.length > 0) {
          toast.warning(`Quote sent, but email notification may have failed: ${data.warnings[0]}`);
        } else {
          toast.success('Quote sent to buyer');
        }
        fetchQuote();
      } else {
        toast.error(data.detail || 'Failed to send quote');
      }
    } catch (error) {
      toast.error('Failed to send quote. Please check your connection and try again.');
    } finally {
      setSendLoading(false);
    }
  };

  const handleDownloadPDF = async () => {
    try {
      const response = await fetch(`${API}/documents/${quoteId}/pdf`, { credentials: 'include' });
      if (response.ok) {
        const blob = await response.blob();
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `quote_${quote.document_number}.pdf`;
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

  const handleDelete = async () => {
    setDeleting(true);
    try {
      const response = await fetch(`${API}/documents/${quoteId}`, {
        method: 'DELETE',
        credentials: 'include'
      });
      
      if (response.ok) {
        toast.success('Quote deleted');
        navigate('/agent/quotes');
      } else {
        const error = await response.json();
        toast.error(error.detail || 'Failed to delete quote');
      }
    } catch (error) {
      toast.error('Failed to delete quote');
    } finally {
      setDeleting(false);
      setShowDeleteDialog(false);
    }
  };

  const handleEdit = () => {
    navigate(`/agent/quotes/edit/${quoteId}`);
  };

  if (loading) {
    return (
      <AgentLayout>
        <div className="animate-pulse space-y-6">
          <div className="h-8 w-64 bg-gray-200 rounded" />
          <div className="h-96 bg-gray-200 rounded-sm" />
        </div>
      </AgentLayout>
    );
  }

  if (!quote) return null;

  const canEdit = quote.status === 'Draft' || quote.status === 'Change Requested';
  const canSend = quote.status === 'Draft' || quote.status === 'Change Requested';

  return (
    <AgentLayout>
      <div className="space-y-6" data-testid="agent-quote-detail">
        {/* Header */}
        <div className="flex flex-col sm:flex-row sm:items-start sm:justify-between gap-4">
          <div>
            <Link 
              to="/agent/quotes" 
              className="inline-flex items-center text-sm text-muted-foreground hover:text-primary mb-4 transition-colors"
              data-testid="back-link"
            >
              <ArrowLeft className="w-4 h-4 mr-2" />
              {t('common.back')} {t('documents.quotes')}
            </Link>
            <h1 className="text-2xl sm:text-3xl font-outfit font-semibold text-foreground tracking-tight">
              {quote.title}
            </h1>
            <div className="flex items-center gap-4 mt-2">
              <p className="text-muted-foreground">{quote.document_number}</p>
              <StatusBadge status={quote.status} />
            </div>
          </div>
          <div className="flex gap-2">
            <Button
              variant="outline"
              size="icon"
              className="rounded-lg"
              onClick={handleEdit}
              data-testid="edit-quote-btn"
            >
              <Pencil className="w-4 h-4" />
            </Button>
            <Button
              variant="outline"
              size="icon"
              className="rounded-lg text-destructive hover:text-destructive hover:bg-destructive/10"
              onClick={() => setShowDeleteDialog(true)}
              data-testid="delete-quote-btn"
            >
              <Trash2 className="w-4 h-4" />
            </Button>
            <Button
              variant="outline"
              className="rounded-lg"
              onClick={handleDownloadPDF}
              data-testid="download-pdf-btn"
            >
              <Download className="w-4 h-4 mr-2" />
              Download PDF
            </Button>
            {canSend && (
              <Button
                className="bg-primary hover:bg-primary/90 rounded-lg"
                onClick={handleSend}
                disabled={sendLoading}
                data-testid="send-quote-btn"
              >
                <Send className="w-4 h-4 mr-2" />
                {sendLoading ? 'Sending...' : 'Send to Buyer'}
              </Button>
            )}
          </div>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Main Content */}
          <div className="lg:col-span-2 space-y-6">
            {/* Change Request Alert */}
            {quote.change_request_comment && (
              <Card className="border-amber-200 bg-amber-50/50 rounded-sm">
                <CardContent className="p-6">
                  <div className="flex items-start gap-3">
                    <MessageSquare className="w-5 h-5 text-amber-600 mt-0.5" />
                    <div>
                      <p className="font-medium text-amber-800">Change Requested by Buyer</p>
                      <p className="text-sm text-amber-700 mt-1">{quote.change_request_comment}</p>
                    </div>
                  </div>
                </CardContent>
              </Card>
            )}

            {/* Quote Details */}
            <Card className="border-[#E2E8F0] rounded-sm">
              <CardHeader className="border-b border-[#E2E8F0]">
                <CardTitle className="text-lg font-outfit font-semibold">Quote Details</CardTitle>
              </CardHeader>
              <CardContent className="p-6">
                {quote.description && (
                  <p className="text-muted-foreground mb-6">{quote.description}</p>
                )}

                {/* Line Items */}
                <table className="table-swiss">
                  <thead>
                    <tr>
                      <th>Description</th>
                      <th className="text-right">Qty</th>
                      <th className="text-right">Unit Price</th>
                      <th className="text-right">Total</th>
                    </tr>
                  </thead>
                  <tbody>
                    {(quote.items || quote.line_items || []).map((item, index) => (
                      <tr key={index}>
                        <td>{item.description}</td>
                        <td className="text-right">{item.quantity}</td>
                        <td className="text-right">{formatCurrency(item.unit_price)}</td>
                        <td className="text-right font-medium">{formatCurrency(item.total)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>

                <div className="mt-6 pt-6 border-t border-[#E2E8F0] flex justify-end">
                  <div className="text-right">
                    <p className="text-xs font-medium tracking-widest uppercase text-muted-foreground">Total Amount</p>
                    <p className="text-3xl font-outfit font-semibold text-[#1A1A1A] mt-1">
                      {formatCurrency(quote.amount)}
                    </p>
                  </div>
                </div>

                {quote.notes && (
                  <div className="mt-6 pt-6 border-t border-[#E2E8F0]">
                    <p className="text-xs font-medium tracking-widest uppercase text-muted-foreground mb-2">Notes</p>
                    <p className="text-sm text-muted-foreground">{quote.notes}</p>
                  </div>
                )}
              </CardContent>
            </Card>
          </div>

          {/* Sidebar */}
          <div className="space-y-6">
            {/* Client Info */}
            <Card className="border-[#E2E8F0] rounded-sm">
              <CardHeader className="border-b border-[#E2E8F0]">
                <CardTitle className="text-sm font-medium flex items-center gap-2">
                  <User className="w-4 h-4" />
                  Client
                </CardTitle>
              </CardHeader>
              <CardContent className="p-4">
                <p className="font-medium text-[#1A1A1A]">{quote.client?.name}</p>
                <p className="text-sm text-muted-foreground mt-1">{quote.client?.email}</p>
                {quote.client?.phone && (
                  <p className="text-sm text-muted-foreground">{quote.client?.phone}</p>
                )}
              </CardContent>
            </Card>

            {/* Project Info */}
            <Card className="border-[#E2E8F0] rounded-sm">
              <CardHeader className="border-b border-[#E2E8F0]">
                <CardTitle className="text-sm font-medium flex items-center gap-2">
                  <Building2 className="w-4 h-4" />
                  Project
                </CardTitle>
              </CardHeader>
              <CardContent className="p-4">
                <p className="font-medium text-[#1A1A1A]">{quote.project?.name}</p>
                <div className="flex items-start gap-2 mt-2 text-sm text-muted-foreground">
                  <MapPin className="w-4 h-4 mt-0.5 flex-shrink-0" />
                  <p>{quote.project?.address}</p>
                </div>
              </CardContent>
            </Card>

            {/* Unit Info */}
            <Card className="border-[#E2E8F0] rounded-sm">
              <CardHeader className="border-b border-[#E2E8F0]">
                <CardTitle className="text-sm font-medium">Unit Reference</CardTitle>
              </CardHeader>
              <CardContent className="p-4">
                <p className="font-medium text-[#1A1A1A]">{quote.unit_reference}</p>
              </CardContent>
            </Card>

            {/* Dates */}
            <Card className="border-[#E2E8F0] rounded-sm">
              <CardHeader className="border-b border-[#E2E8F0]">
                <CardTitle className="text-sm font-medium flex items-center gap-2">
                  <Calendar className="w-4 h-4" />
                  Dates
                </CardTitle>
              </CardHeader>
              <CardContent className="p-4 space-y-3">
                <div>
                  <p className="text-xs text-muted-foreground">Created</p>
                  <p className="text-sm font-medium">{formatDate(quote.created_at)}</p>
                </div>
                <div>
                  <p className="text-xs text-muted-foreground">Last Updated</p>
                  <p className="text-sm font-medium">{formatDate(quote.updated_at)}</p>
                </div>
              </CardContent>
            </Card>
          </div>
        </div>
      </div>

      {/* Delete Confirmation Dialog */}
      <AlertDialog open={showDeleteDialog} onOpenChange={setShowDeleteDialog}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Delete Quote</AlertDialogTitle>
            <AlertDialogDescription>
              Are you sure you want to delete quote "{quote.document_number}"? 
              This action cannot be undone.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel disabled={deleting}>Cancel</AlertDialogCancel>
            <AlertDialogAction 
              onClick={handleDelete}
              disabled={deleting}
              className="bg-destructive hover:bg-destructive/90"
            >
              {deleting ? 'Deleting...' : 'Delete'}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </AgentLayout>
  );
};
