import { useState, useEffect } from 'react';
import { useParams, useNavigate, Link } from 'react-router-dom';
import { AgentLayout } from '../../components/AgentLayout';
import { StatusBadge } from '../../components/StatusBadge';
import { Card, CardContent, CardHeader, CardTitle } from '../../components/ui/card';
import { Button } from '../../components/ui/button';
import { Input } from '../../components/ui/input';
import { Label } from '../../components/ui/label';
import { Textarea } from '../../components/ui/textarea';
import { toast } from 'sonner';
import { 
  ArrowLeft, 
  Save, 
  Send, 
  MessageSquare, 
  Eye, 
  Loader2,
  Upload,
  X,
  FileText,
  Receipt
} from 'lucide-react';
import { cn } from '../../lib/utils';
import {
  PdfUploadZone,
  LineItemsEditor,
  HeroImageUploader,
  DocumentFormActions,
  formatCurrency
} from '../../components/DocumentForm';

const API = process.env.REACT_APP_BACKEND_URL + '/api';

const getAuthHeaders = () => {
  const token = localStorage.getItem('auth_token');
  return token ? { 'Authorization': `Bearer ${token}` } : {};
};

export const AgentQuoteEdit = () => {
  const { quoteId } = useParams();
  const navigate = useNavigate();
  const [quote, setQuote] = useState(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [sending, setSending] = useState(false);
  const [converting, setConverting] = useState(false);
  
  // Reupload state
  const [showReupload, setShowReupload] = useState(false);
  const [newFile, setNewFile] = useState(null);
  const [dragActive, setDragActive] = useState(false);
  const [uploading, setUploading] = useState(false);
  
  const [formData, setFormData] = useState({
    title: '',
    description: '',
    amount: '',
    supplier_name: '',
    notes: '',
    summary: '',
    line_items: []
  });

  useEffect(() => {
    fetchQuote();
  }, [quoteId]);

  const fetchQuote = async () => {
    try {
      const response = await fetch(`${API}/documents/${quoteId}`, { credentials: 'include', headers: getAuthHeaders() });
      if (response.ok) {
        const data = await response.json();
        setQuote(data);
        setFormData({
          title: data.title,
          description: data.description || '',
          amount: String(data.amount || ''),
          supplier_name: data.supplier_name || '',
          notes: data.notes || '',
          summary: data.summary || '',
          line_items: (data.line_items || data.items || []).map(item => ({...item}))
        });
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

  const handleConvertToInvoice = async () => {
    setConverting(true);
    try {
      const res = await fetch(`${API}/documents/${quoteId}/action`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', ...getAuthHeaders() },
        credentials: 'include',
        body: JSON.stringify({ action: 'convert_to_invoice' })
      });
      
      if (res.ok) {
        const data = await res.json();
        toast.success(`Invoice ${data.document_number} created`);
        navigate('/agent/invoices');
      } else {
        const err = await res.json();
        throw new Error(err.detail || 'Failed to convert');
      }
    } catch (error) {
      toast.error(error.message || 'Failed to convert to invoice');
    } finally {
      setConverting(false);
    }
  };

  const handleReupload = async () => {
    if (!newFile) return;

    setUploading(true);
    const formDataUpload = new FormData();
    formDataUpload.append('file', newFile);

    try {
      const res = await fetch(`${API}/documents/${quoteId}/reupload`, {
        method: 'POST',
        credentials: 'include',
        headers: getAuthHeaders(),
        body: formDataUpload
      });

      if (res.ok) {
        const data = await res.json();
        setQuote(data);
        setFormData({
          title: data.title,
          description: data.description || '',
          amount: String(data.amount || ''),
          supplier_name: data.supplier_name || '',
          notes: data.notes || '',
          summary: data.summary || '',
          line_items: (data.line_items || data.items || []).map(item => ({...item}))
        });
        setShowReupload(false);
        setNewFile(null);
        toast.success('New PDF uploaded and analyzed');
        
        if (data.extraction_warning) {
          toast.warning('Price could not be extracted. Please verify the amount.');
        }
      } else {
        const error = await res.json();
        throw new Error(error.detail || 'Reupload failed');
      }
    } catch (error) {
      toast.error(error.message || 'Failed to reupload PDF');
    } finally {
      setUploading(false);
    }
  };

  const handleSave = async (andSend = false) => {
    const totalAmount = parseFloat(formData.amount);
    if (!totalAmount || totalAmount <= 0) {
      toast.error('Please enter a valid total amount');
      return;
    }

    if (andSend) {
      setSending(true);
    } else {
      setSaving(true);
    }

    try {
      const updateData = {
        title: formData.title,
        amount: totalAmount,
        supplier_name: formData.supplier_name,
        notes: formData.notes,
        summary: formData.summary
      };
      
      if (formData.line_items.length > 0) {
        updateData.items = formData.line_items;
      }

      const saveRes = await fetch(`${API}/documents/${quoteId}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json', ...getAuthHeaders() },
        credentials: 'include',
        body: JSON.stringify(updateData)
      });

      if (!saveRes.ok) {
        throw new Error('Failed to save');
      }

      if (andSend) {
        const sendRes = await fetch(`${API}/documents/${quoteId}/send`, {
          method: 'POST',
          credentials: 'include'
        });

        if (sendRes.ok) {
          toast.success(quote.status === 'Change Requested' ? 'Quote resent to buyer' : 'Quote sent to buyer');
          navigate('/agent/quotes');
        } else {
          throw new Error('Failed to send');
        }
      } else {
        toast.success('Quote saved');
        navigate('/agent/quotes');
      }
    } catch (error) {
      toast.error(error.message || 'Failed to save quote');
    } finally {
      setSaving(false);
      setSending(false);
    }
  };

  if (loading) {
    return (
      <AgentLayout>
        <div className="flex items-center justify-center h-64">
          <Loader2 className="w-8 h-8 animate-spin text-primary" />
        </div>
      </AgentLayout>
    );
  }

  if (!quote) {
    return (
      <AgentLayout>
        <div className="text-center py-12">
          <p className="text-muted-foreground">Quote not found</p>
          <Button asChild className="mt-4">
            <Link to="/agent/quotes">Back to Quotes</Link>
          </Button>
        </div>
      </AgentLayout>
    );
  }

  const canEdit = ['Draft', 'Change Requested'].includes(quote.status);
  const canSend = canEdit && formData.amount && parseFloat(formData.amount) > 0;
  const canConvert = quote.status === 'Approved';

  return (
    <AgentLayout>
      <div className="max-w-4xl mx-auto space-y-6" data-testid="quote-edit-page">
        {/* Header */}
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
          <div className="flex items-center gap-4">
            <Button variant="ghost" size="icon" asChild>
              <Link to="/agent/quotes">
                <ArrowLeft className="w-5 h-5" />
              </Link>
            </Button>
            <div>
              <div className="flex items-center gap-3">
                <h1 className="text-xl sm:text-2xl font-outfit font-semibold text-foreground">
                  Edit Quote
                </h1>
                <StatusBadge status={quote.status} />
              </div>
              <p className="text-sm text-muted-foreground">{quote.document_number}</p>
            </div>
          </div>
          <div className="flex gap-2">
            {quote.pdf_filename && (
              <Button
                variant="outline"
                size="sm"
                onClick={() => window.open(`${API}/documents/${quoteId}/source-pdf`, '_blank')}
              >
                <Eye className="w-4 h-4 mr-2" />
                View PDF
              </Button>
            )}
            {canConvert && (
              <Button
                onClick={handleConvertToInvoice}
                disabled={converting}
                size="sm"
              >
                {converting ? (
                  <Loader2 className="w-4 h-4 animate-spin" />
                ) : (
                  <>
                    <Receipt className="w-4 h-4 mr-2" />
                    Convert to Invoice
                  </>
                )}
              </Button>
            )}
          </div>
        </div>

        {/* Change Request Alert */}
        {quote.status === 'Change Requested' && quote.change_request_comment && (
          <Card className="border-amber-500/50 bg-amber-500/5">
            <CardContent className="py-4">
              <div className="flex items-start gap-3">
                <MessageSquare className="w-5 h-5 text-amber-600 flex-shrink-0 mt-0.5" />
                <div>
                  <p className="font-medium text-foreground">Buyer requested changes</p>
                  <p className="text-sm text-muted-foreground mt-1">{quote.change_request_comment}</p>
                </div>
              </div>
            </CardContent>
          </Card>
        )}

        {/* Reupload PDF Section */}
        {canEdit && (
          <Card>
            <CardHeader className="pb-3">
              <div className="flex items-center justify-between">
                <CardTitle className="text-base font-medium">Source PDF</CardTitle>
                {!showReupload && (
                  <Button variant="outline" size="sm" onClick={() => setShowReupload(true)}>
                    <Upload className="w-4 h-4 mr-2" />
                    Replace PDF
                  </Button>
                )}
              </div>
            </CardHeader>
            {showReupload && (
              <CardContent>
                <PdfUploadZone
                  file={newFile}
                  setFile={setNewFile}
                  dragActive={dragActive}
                  setDragActive={setDragActive}
                  onUpload={handleReupload}
                  uploading={uploading}
                  disabled={false}
                  docType="quote"
                />
                <div className="flex justify-end gap-2 mt-4">
                  <Button variant="ghost" size="sm" onClick={() => { setShowReupload(false); setNewFile(null); }}>
                    Cancel
                  </Button>
                </div>
              </CardContent>
            )}
          </Card>
        )}

        {/* Edit Form */}
        <Card>
          <CardHeader>
            <CardTitle className="text-lg">Quote Details</CardTitle>
          </CardHeader>
          <CardContent className="space-y-6">
            {/* Basic Info */}
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <div className="sm:col-span-2">
                <Label htmlFor="title">Quote Title *</Label>
                <Input
                  id="title"
                  value={formData.title}
                  onChange={(e) => setFormData(prev => ({ ...prev, title: e.target.value }))}
                  disabled={!canEdit}
                  className="mt-1"
                  data-testid="title-input"
                />
              </div>
              
              <div>
                <Label htmlFor="amount">Total Amount (CHF) *</Label>
                <Input
                  id="amount"
                  type="number"
                  step="0.01"
                  value={formData.amount}
                  onChange={(e) => setFormData(prev => ({ ...prev, amount: e.target.value }))}
                  disabled={!canEdit}
                  className="mt-1"
                  data-testid="total-input"
                />
              </div>
              
              <div>
                <Label htmlFor="supplier">Supplier Name</Label>
                <Input
                  id="supplier"
                  value={formData.supplier_name}
                  onChange={(e) => setFormData(prev => ({ ...prev, supplier_name: e.target.value }))}
                  disabled={!canEdit}
                  className="mt-1"
                />
              </div>
            </div>

            {/* Line Items */}
            <LineItemsEditor
              items={formData.line_items}
              onChange={(items) => setFormData(prev => ({ ...prev, line_items: items }))}
            />

            <div>
              <Label htmlFor="notes">Notes for Buyer</Label>
              <Textarea
                id="notes"
                value={formData.notes}
                onChange={(e) => setFormData(prev => ({ ...prev, notes: e.target.value }))}
                disabled={!canEdit}
                className="mt-1"
                rows={2}
              />
            </div>

            <div>
              <Label htmlFor="summary">Card Summary</Label>
              <p className="text-xs text-muted-foreground mb-1">
                Short description shown on the buyer's timeline card
              </p>
              <Textarea
                id="summary"
                value={formData.summary}
                onChange={(e) => setFormData(prev => ({ ...prev, summary: e.target.value }))}
                disabled={!canEdit}
                className="mt-1"
                rows={2}
                data-testid="summary-input"
              />
            </div>

            {/* Hero Image */}
            <HeroImageUploader
              documentId={quoteId}
              heroImageUrl={quote.hero_image_url}
              onUpdate={(url) => setQuote(prev => ({ ...prev, hero_image_url: url }))}
            />

            {/* Total Summary */}
            <div className="p-4 bg-muted rounded-lg">
              <div className="flex items-center justify-between">
                <span className="text-muted-foreground">Quote Total</span>
                <span className="text-2xl font-bold text-foreground">
                  CHF {formatCurrency(parseFloat(formData.amount) || 0)}
                </span>
              </div>
            </div>

            {/* Actions */}
            {canEdit && (
              <DocumentFormActions
                onSaveDraft={() => handleSave(false)}
                onSend={() => handleSave(true)}
                saving={saving}
                sending={sending}
                canSend={canSend}
                sendLabel={quote.status === 'Change Requested' ? 'Resend to Buyer' : 'Send to Buyer'}
              />
            )}

            {/* Read-only state message */}
            {!canEdit && (
              <div className="p-4 bg-muted/50 rounded-lg text-center">
                <p className="text-sm text-muted-foreground">
                  This quote is in "{quote.status}" status and cannot be edited.
                </p>
              </div>
            )}
          </CardContent>
        </Card>
      </div>
    </AgentLayout>
  );
};
