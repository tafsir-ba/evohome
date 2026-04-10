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
  CheckCircle,
  Building2,
  MapPin,
  Calendar,
  CreditCard,
  User,
  Pencil,
  Trash2
} from 'lucide-react';

const API = process.env.REACT_APP_BACKEND_URL + '/api';

export const AgentInvoiceDetail = () => {
  const { t } = useSettings();
  const { invoiceId } = useParams();
  const navigate = useNavigate();
  const [invoice, setInvoice] = useState(null);
  const [loading, setLoading] = useState(true);
  const [markingPaid, setMarkingPaid] = useState(false);
  const [showDeleteDialog, setShowDeleteDialog] = useState(false);
  const [deleting, setDeleting] = useState(false);

  useEffect(() => {
    fetchInvoice();
  }, [invoiceId]);

  const fetchInvoice = async () => {
    try {
      const response = await fetch(`${API}/documents/${invoiceId}`, { credentials: 'include' });
      if (response.ok) {
        setInvoice(await response.json());
      } else {
        toast.error('Invoice not found');
        navigate('/agent/invoices');
      }
    } catch (error) {
      console.error('Failed to fetch invoice:', error);
      toast.error('Failed to load invoice');
    } finally {
      setLoading(false);
    }
  };

  const handleMarkPaid = async () => {
    setMarkingPaid(true);
    try {
      // Use document action endpoint with confirm_payment action
      const response = await fetch(`${API}/documents/${invoiceId}/action`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
        body: JSON.stringify({ action: 'confirm_payment' })
      });

      if (response.ok) {
        toast.success('Invoice marked as paid');
        fetchInvoice();
      } else {
        const error = await response.json();
        toast.error(error.detail);
      }
    } catch (error) {
      toast.error('Failed to mark invoice as paid');
    } finally {
      setMarkingPaid(false);
    }
  };

  const handleDownloadPDF = async () => {
    try {
      const response = await fetch(`${API}/documents/${invoiceId}/pdf`, { credentials: 'include' });
      if (response.ok) {
        const blob = await response.blob();
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `invoice_${invoice.document_number}.pdf`;
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
      const response = await fetch(`${API}/documents/${invoiceId}`, {
        method: 'DELETE',
        credentials: 'include'
      });
      
      if (response.ok) {
        toast.success('Invoice deleted');
        navigate('/agent/invoices');
      } else {
        const error = await response.json();
        toast.error(error.detail || 'Failed to delete invoice');
      }
    } catch (error) {
      toast.error('Failed to delete invoice');
    } finally {
      setDeleting(false);
      setShowDeleteDialog(false);
    }
  };

  const handleEdit = () => {
    // Navigate to edit page with invoice data
    navigate(`/agent/invoices/edit/${invoiceId}`);
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

  if (!invoice) return null;

  return (
    <AgentLayout>
      <div className="space-y-6" data-testid="agent-invoice-detail">
        {/* Header */}
        <div className="flex items-start justify-between">
          <div>
            <Link 
              to="/agent/invoices" 
              className="inline-flex items-center text-sm text-muted-foreground hover:text-primary mb-4 transition-colors"
              data-testid="back-link"
            >
              <ArrowLeft className="w-4 h-4 mr-2" />
              Back to Invoices
            </Link>
            <h1 className="text-3xl font-outfit font-semibold text-[#1A1A1A] tracking-tight">
              Invoice {invoice.document_number}
            </h1>
            <div className="flex items-center gap-4 mt-2">
              <p className="text-muted-foreground">{invoice.title}</p>
              <StatusBadge status={invoice.status} />
            </div>
          </div>
          <div className="flex gap-2">
            <Button
              variant="outline"
              size="icon"
              className="rounded-lg"
              onClick={handleEdit}
              data-testid="edit-invoice-btn"
            >
              <Pencil className="w-4 h-4" />
            </Button>
            <Button
              variant="outline"
              size="icon"
              className="rounded-lg text-destructive hover:text-destructive hover:bg-destructive/10"
              onClick={() => setShowDeleteDialog(true)}
              data-testid="delete-invoice-btn"
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
            {invoice.status !== 'Paid' && (
              <Button
                className="bg-[#10B981] hover:bg-[#059669] rounded-lg"
                onClick={handleMarkPaid}
                disabled={markingPaid}
                data-testid="mark-paid-btn"
              >
                <CheckCircle className="w-4 h-4 mr-2" />
                {markingPaid ? 'Processing...' : 'Mark as Paid'}
              </Button>
            )}
          </div>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Main Content */}
          <div className="lg:col-span-2 space-y-6">
            {/* Invoice Details */}
            <Card className="border-[#E2E8F0] rounded-sm">
              <CardHeader className="border-b border-[#E2E8F0]">
                <CardTitle className="text-lg font-outfit font-semibold">Invoice Details</CardTitle>
              </CardHeader>
              <CardContent className="p-6">
                {invoice.description && (
                  <p className="text-muted-foreground mb-6">{invoice.description}</p>
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
                    {(invoice.line_items || invoice.items || []).map((item, index) => (
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
                    <p className="text-xs font-medium tracking-widest uppercase text-muted-foreground">Amount Due</p>
                    <p className="text-3xl font-outfit font-semibold text-primary mt-1">
                      {formatCurrency(invoice.amount)}
                    </p>
                  </div>
                </div>
              </CardContent>
            </Card>

            {/* Payment Status */}
            <Card className="border-[#E2E8F0] rounded-sm">
              <CardHeader className="border-b border-[#E2E8F0]">
                <CardTitle className="text-lg font-outfit font-semibold flex items-center gap-2">
                  <CreditCard className="w-5 h-5" />
                  Payment Status
                </CardTitle>
              </CardHeader>
              <CardContent className="p-6">
                {invoice.status === 'Paid' ? (
                  <div className="flex items-center gap-3 p-4 bg-green-50 rounded-sm">
                    <CheckCircle className="w-6 h-6 text-green-600" />
                    <div>
                      <p className="font-medium text-green-800">Payment Received</p>
                      <p className="text-sm text-green-600">Paid on {formatDate(invoice.paid_date)}</p>
                    </div>
                  </div>
                ) : (
                  <div className="p-4 bg-amber-50 rounded-sm">
                    <p className="font-medium text-amber-800">Awaiting Payment</p>
                    <p className="text-sm text-amber-600 mt-1">Due date: {formatDate(invoice.due_date)}</p>
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
                <p className="font-medium text-[#1A1A1A]">{invoice.client?.name}</p>
                <p className="text-sm text-muted-foreground mt-1">{invoice.client?.email}</p>
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
                <p className="font-medium text-[#1A1A1A]">{invoice.project?.name}</p>
                <div className="flex items-start gap-2 mt-2 text-sm text-muted-foreground">
                  <MapPin className="w-4 h-4 mt-0.5 flex-shrink-0" />
                  <p>{invoice.project?.address}</p>
                </div>
              </CardContent>
            </Card>

            {/* Unit Info */}
            <Card className="border-[#E2E8F0] rounded-sm">
              <CardHeader className="border-b border-[#E2E8F0]">
                <CardTitle className="text-sm font-medium">Unit Reference</CardTitle>
              </CardHeader>
              <CardContent className="p-4">
                <p className="font-medium text-[#1A1A1A]">{invoice.unit_reference}</p>
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
                  <p className="text-xs text-muted-foreground">Issue Date</p>
                  <p className="text-sm font-medium">{formatDate(invoice.issue_date)}</p>
                </div>
                <div>
                  <p className="text-xs text-muted-foreground">Due Date</p>
                  <p className="text-sm font-medium">{formatDate(invoice.due_date)}</p>
                </div>
                {invoice.paid_date && (
                  <div>
                    <p className="text-xs text-muted-foreground">Paid Date</p>
                    <p className="text-sm font-medium text-green-600">{formatDate(invoice.paid_date)}</p>
                  </div>
                )}
              </CardContent>
            </Card>
          </div>
        </div>
      </div>

      {/* Delete Confirmation Dialog */}
      <AlertDialog open={showDeleteDialog} onOpenChange={setShowDeleteDialog}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Delete Invoice</AlertDialogTitle>
            <AlertDialogDescription>
              Are you sure you want to delete invoice "{invoice.document_number}"? 
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
