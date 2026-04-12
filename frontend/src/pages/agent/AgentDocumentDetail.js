import { useState, useEffect, useCallback } from 'react';
import { useParams, useNavigate, Link, useSearchParams } from 'react-router-dom';
import { AgentLayout } from '../../components/AgentLayout';
import { StatusBadge, formatCurrency, formatDate } from '../../components/StatusBadge';
import { ChangeRequestPanel } from '../../components/ChangeRequestPanel';
import { Card, CardContent, CardHeader, CardTitle } from '../../components/ui/card';
import { Button } from '../../components/ui/button';
import {
  AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent,
  AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle,
} from '../../components/ui/alert-dialog';
import { toast } from 'sonner';
import { useSettings } from '../../context/SettingsContext';
import { 
  ArrowLeft, Download, Send, Pencil, Trash2, Building2, MapPin,
  Calendar, MessageSquare, User, CheckCircle, CreditCard, AlertCircle
} from 'lucide-react';

const API = process.env.REACT_APP_BACKEND_URL + '/api';
const getAuthHeaders = () => {
  const token = localStorage.getItem('auth_token');
  return token ? { 'Authorization': `Bearer ${token}` } : {};
};

export const AgentDocumentDetail = () => {
  const { t } = useSettings();
  const { documentId, quoteId, invoiceId } = useParams();
  const id = documentId || quoteId || invoiceId;
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();
  const highlightChangeRequestId = searchParams.get('change_request_id');
  const clearChangeRequestHighlight = useCallback(() => {
    setSearchParams((prev) => {
      const n = new URLSearchParams(prev);
      n.delete('change_request_id');
      return n;
    }, { replace: true });
  }, [setSearchParams]);
  const [doc, setDoc] = useState(null);
  const [loading, setLoading] = useState(true);
  const [sendLoading, setSendLoading] = useState(false);
  const [markingPaid, setMarkingPaid] = useState(false);
  const [showDeleteDialog, setShowDeleteDialog] = useState(false);
  const [deleting, setDeleting] = useState(false);

  useEffect(() => { fetchDoc(); }, [id]);

  const fetchDoc = async () => {
    try {
      const res = await fetch(`${API}/documents/${id}`, { credentials: 'include', headers: getAuthHeaders() });
      if (res.ok) setDoc(await res.json());
      else { toast.error('Document not found'); navigate('/agent/documents'); }
    } catch { toast.error('Failed to load document'); }
    finally { setLoading(false); }
  };

  const handleSend = async () => {
    setSendLoading(true);
    try {
      const res = await fetch(`${API}/documents/${id}/send`, { method: 'POST', credentials: 'include', headers: getAuthHeaders() });
      const data = await res.json();
      if (res.ok) {
        if (data.delivery?.email_sent) toast.success(`Sent to ${data.recipient?.name || 'buyer'}. Email delivered.`);
        else toast.success('Sent to buyer');
        fetchDoc();
      } else toast.error(data.message || data.detail || 'Failed to send');
    } catch { toast.error('Failed to send'); }
    finally { setSendLoading(false); }
  };

  const handleMarkPaid = async () => {
    setMarkingPaid(true);
    try {
      const res = await fetch(`${API}/documents/${id}/action`, {
        method: 'POST', headers: { 'Content-Type': 'application/json', ...getAuthHeaders() },
        credentials: 'include', body: JSON.stringify({ action: 'confirm_payment' })
      });
      if (res.ok) { toast.success('Marked as paid'); fetchDoc(); }
      else { const err = await res.json(); toast.error(err.message || 'Failed'); }
    } catch { toast.error('Failed'); }
    finally { setMarkingPaid(false); }
  };

  const handleResend = async () => {
    try {
      const res = await fetch(`${API}/documents/${id}/action`, {
        method: 'POST', headers: { 'Content-Type': 'application/json', ...getAuthHeaders() },
        credentials: 'include', body: JSON.stringify({ action: 'send' })
      });
      if (res.ok) { toast.success('Resent to buyer'); fetchDoc(); }
      else { const err = await res.json(); toast.error(err.message || 'Failed to resend'); }
    } catch { toast.error('Failed to resend'); }
  };

  const handleDownloadPDF = async () => {
    try {
      const res = await fetch(`${API}/documents/${id}/source-pdf`, { credentials: 'include', headers: getAuthHeaders() });
      if (res.ok) {
        const blob = await res.blob();
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url; a.download = `${doc.type}_${doc.document_number}.pdf`;
        document.body.appendChild(a); a.click();
        window.URL.revokeObjectURL(url); document.body.removeChild(a);
      } else toast.error('Failed to download PDF');
    } catch { toast.error('Download failed'); }
  };

  const handleDelete = async () => {
    setDeleting(true);
    try {
      const res = await fetch(`${API}/documents/${id}`, { method: 'DELETE', credentials: 'include', headers: getAuthHeaders() });
      if (res.ok) { toast.success('Document deleted'); navigate('/agent/documents'); }
      else { const err = await res.json(); toast.error(err.message || 'Failed to delete'); }
    } catch { toast.error('Failed to delete'); }
    finally { setDeleting(false); setShowDeleteDialog(false); }
  };

  if (loading) return <AgentLayout><div className="animate-pulse space-y-6"><div className="h-8 w-64 bg-gray-200 rounded" /><div className="h-96 bg-gray-200 rounded-sm" /></div></AgentLayout>;
  if (!doc) return null;

  const isInvoice = doc.type === 'invoice';
  const typeLabel = isInvoice ? 'Invoice' : 'Quote';
  const canEdit = ['Draft', 'Change Requested', 'Rejected'].includes(doc.status);
  const canSend = ['Draft', 'Change Requested', 'Rejected'].includes(doc.status);
  const items = doc.items || doc.line_items || [];

  return (
    <AgentLayout>
      <div className="space-y-6" data-testid="document-detail">
        {/* Header */}
        <div className="flex flex-col sm:flex-row sm:items-start sm:justify-between gap-4">
          <div>
            <Link to="/agent/documents" className="inline-flex items-center text-sm text-muted-foreground hover:text-primary mb-4 transition-colors" data-testid="back-link">
              <ArrowLeft className="w-4 h-4 mr-2" /> Back to Documents
            </Link>
            <h1 className="text-2xl sm:text-3xl font-outfit font-semibold text-foreground tracking-tight">{doc.title}</h1>
            <div className="flex items-center gap-4 mt-2">
              <span className={`text-xs font-medium px-2 py-0.5 rounded ${isInvoice ? 'bg-blue-100 text-blue-700' : 'bg-emerald-100 text-emerald-700'}`}>{typeLabel}</span>
              <p className="text-muted-foreground">{doc.document_number}</p>
              <StatusBadge status={doc.status} />
            </div>
          </div>
          <div className="flex gap-2">
            {canEdit && (
              <Button variant="outline" size="icon" className="rounded-lg" onClick={() => navigate(`/agent/documents/edit/${id}`)} data-testid="edit-doc-btn">
                <Pencil className="w-4 h-4" />
              </Button>
            )}
            <Button variant="outline" size="icon" className="rounded-lg text-destructive hover:text-destructive hover:bg-destructive/10" onClick={() => setShowDeleteDialog(true)} data-testid="delete-doc-btn">
              <Trash2 className="w-4 h-4" />
            </Button>
            {doc.pdf_stored_filename && (
              <Button variant="outline" className="rounded-lg" onClick={handleDownloadPDF} data-testid="download-pdf-btn">
                <Download className="w-4 h-4 mr-2" /> Download PDF
              </Button>
            )}
            {canSend && (
              <Button className="bg-primary hover:bg-primary/90 rounded-lg" onClick={handleSend} disabled={sendLoading} data-testid="send-doc-btn">
                <Send className="w-4 h-4 mr-2" /> {sendLoading ? 'Sending...' : `Send ${typeLabel}`}
              </Button>
            )}
            {isInvoice && doc.status !== 'Paid' && doc.status !== 'Draft' && (
              <Button className="bg-emerald-600 hover:bg-emerald-700 rounded-lg" onClick={handleMarkPaid} disabled={markingPaid} data-testid="mark-paid-btn">
                <CheckCircle className="w-4 h-4 mr-2" /> {markingPaid ? 'Processing...' : 'Mark as Paid'}
              </Button>
            )}
          </div>
        </div>

        {/* Change Request Alert */}
        {doc.change_request_comment && (
          <Card className="border-amber-200 bg-amber-50/50 rounded-sm">
            <CardContent className="p-6">
              <div className="flex items-start gap-3">
                <AlertCircle className="w-5 h-5 text-amber-600 mt-0.5" />
                <div className="flex-1">
                  <p className="font-medium text-amber-800">Change Requested by Buyer</p>
                  <p className="text-sm text-amber-700 mt-1 whitespace-pre-wrap">{doc.change_request_comment}</p>
                  <div className="flex gap-2 mt-4">
                    <Button size="sm" variant="outline" className="border-amber-500/30 text-amber-700 hover:bg-amber-500/10" onClick={() => navigate(`/agent/documents/edit/${id}`)}>
                      <Pencil className="w-4 h-4 mr-2" /> Edit {typeLabel}
                    </Button>
                    <Button size="sm" variant="outline" className="border-amber-500/30 text-amber-700 hover:bg-amber-500/10" onClick={handleResend}>
                      <Send className="w-4 h-4 mr-2" /> Resend to Buyer
                    </Button>
                  </div>
                </div>
              </div>
            </CardContent>
          </Card>
        )}

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Main Content */}
          <div className="lg:col-span-2 space-y-6">
            <Card className="border-[#E2E8F0] rounded-sm">
              <CardHeader className="border-b border-[#E2E8F0]">
                <CardTitle className="text-lg font-outfit font-semibold">{typeLabel} Details</CardTitle>
              </CardHeader>
              <CardContent className="p-6">
                {(doc.description || doc.summary) && (
                  <p className="text-muted-foreground mb-6">{doc.description || doc.summary}</p>
                )}
                {items.length > 0 && (
                  <table className="table-swiss">
                    <thead><tr><th>Description</th><th className="text-right">Qty</th><th className="text-right">Unit Price</th><th className="text-right">Total</th></tr></thead>
                    <tbody>
                      {items.map((item, i) => (
                        <tr key={`item-${i}`}><td>{item.description}</td><td className="text-right">{item.quantity}</td><td className="text-right">{formatCurrency(item.unit_price)}</td><td className="text-right font-medium">{formatCurrency(item.total)}</td></tr>
                      ))}
                    </tbody>
                  </table>
                )}
                <div className="mt-6 pt-6 border-t border-[#E2E8F0] flex justify-end">
                  <div className="text-right">
                    <p className="text-xs font-medium tracking-widest uppercase text-muted-foreground">{isInvoice ? 'Amount Due' : 'Total Amount'}</p>
                    <p className="text-3xl font-outfit font-semibold text-foreground mt-1">{formatCurrency(doc.amount)}</p>
                  </div>
                </div>
                {doc.notes && (
                  <div className="mt-6 pt-6 border-t border-[#E2E8F0]">
                    <p className="text-xs font-medium tracking-widest uppercase text-muted-foreground mb-2">Notes</p>
                    <p className="text-sm text-muted-foreground">{doc.notes}</p>
                  </div>
                )}
              </CardContent>
            </Card>

            {/* Payment Status (invoice only) */}
            {isInvoice && (
              <Card className="border-[#E2E8F0] rounded-sm">
                <CardHeader className="border-b border-[#E2E8F0]">
                  <CardTitle className="text-lg font-outfit font-semibold flex items-center gap-2"><CreditCard className="w-5 h-5" /> Payment Status</CardTitle>
                </CardHeader>
                <CardContent className="p-6">
                  {doc.status === 'Paid' ? (
                    <div className="flex items-center gap-3 p-4 bg-green-50 rounded-sm"><CheckCircle className="w-6 h-6 text-green-600" /><div><p className="font-medium text-green-800">Payment Received</p><p className="text-sm text-green-600">Paid on {formatDate(doc.paid_date)}</p></div></div>
                  ) : (
                    <div className="p-4 bg-amber-50 rounded-sm"><p className="font-medium text-amber-800">Awaiting Payment</p>{doc.due_date && <p className="text-sm text-amber-600 mt-1">Due date: {formatDate(doc.due_date)}</p>}</div>
                  )}
                </CardContent>
              </Card>
            )}
          </div>

          {/* Sidebar */}
          <div className="space-y-6">
            <Card className="border-[#E2E8F0] rounded-sm">
              <CardHeader className="border-b border-[#E2E8F0]"><CardTitle className="text-sm font-medium flex items-center gap-2"><User className="w-4 h-4" /> Client</CardTitle></CardHeader>
              <CardContent className="p-4">
                <p className="font-medium text-foreground">{doc.client?.name || doc.client_name}</p>
                <p className="text-sm text-muted-foreground mt-1">{doc.client?.email}</p>
                {doc.client?.phone && <p className="text-sm text-muted-foreground">{doc.client?.phone}</p>}
              </CardContent>
            </Card>
            <Card className="border-[#E2E8F0] rounded-sm">
              <CardHeader className="border-b border-[#E2E8F0]"><CardTitle className="text-sm font-medium flex items-center gap-2"><Building2 className="w-4 h-4" /> Project</CardTitle></CardHeader>
              <CardContent className="p-4">
                <p className="font-medium text-foreground">{doc.project_name || doc.project?.name}</p>
                {(doc.project?.address) && <div className="flex items-start gap-2 mt-2 text-sm text-muted-foreground"><MapPin className="w-4 h-4 mt-0.5 flex-shrink-0" /><p>{doc.project?.address}</p></div>}
              </CardContent>
            </Card>
            {doc.unit_reference && (
              <Card className="border-[#E2E8F0] rounded-sm">
                <CardHeader className="border-b border-[#E2E8F0]"><CardTitle className="text-sm font-medium">Unit Reference</CardTitle></CardHeader>
                <CardContent className="p-4"><p className="font-medium text-foreground">{doc.unit_reference}</p></CardContent>
              </Card>
            )}
            <Card className="border-[#E2E8F0] rounded-sm">
              <CardHeader className="border-b border-[#E2E8F0]"><CardTitle className="text-sm font-medium flex items-center gap-2"><Calendar className="w-4 h-4" /> Dates</CardTitle></CardHeader>
              <CardContent className="p-4 space-y-3">
                <div><p className="text-xs text-muted-foreground">Created</p><p className="text-sm font-medium">{formatDate(doc.created_at)}</p></div>
                <div><p className="text-xs text-muted-foreground">Last Updated</p><p className="text-sm font-medium">{formatDate(doc.updated_at)}</p></div>
                {isInvoice && doc.due_date && <div><p className="text-xs text-muted-foreground">Due Date</p><p className="text-sm font-medium">{formatDate(doc.due_date)}</p></div>}
                {doc.paid_date && <div><p className="text-xs text-muted-foreground">Paid Date</p><p className="text-sm font-medium text-green-600">{formatDate(doc.paid_date)}</p></div>}
              </CardContent>
            </Card>
            <ChangeRequestPanel
              entityType={doc.type?.toLowerCase() || 'quote'}
              entityId={id}
              isAgent={true}
              highlightChangeRequestId={highlightChangeRequestId}
              onHighlightConsumed={clearChangeRequestHighlight}
            />
          </div>
        </div>
      </div>

      <AlertDialog open={showDeleteDialog} onOpenChange={setShowDeleteDialog}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Delete {typeLabel}</AlertDialogTitle>
            <AlertDialogDescription>Are you sure you want to delete {typeLabel.toLowerCase()} "{doc.document_number}"? This cannot be undone.</AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel disabled={deleting}>Cancel</AlertDialogCancel>
            <AlertDialogAction onClick={handleDelete} disabled={deleting} className="bg-destructive hover:bg-destructive/90">{deleting ? 'Deleting...' : 'Delete'}</AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </AgentLayout>
  );
};
