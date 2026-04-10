import { useState, useEffect } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { AgentLayout } from '../../components/AgentLayout';
import { Card, CardContent, CardHeader, CardTitle } from '../../components/ui/card';
import { Button } from '../../components/ui/button';
import { Input } from '../../components/ui/input';
import { Textarea } from '../../components/ui/textarea';
import { Label } from '../../components/ui/label';
import { toast } from 'sonner';
import { Loader2, Eye, CheckCircle, X } from 'lucide-react';
import { cn } from '../../lib/utils';
import { SupplierAutocomplete } from '../../components/SupplierAutocomplete';
import {
  PdfUploadZone,
  LineItemsEditor,
  HeroImageUploader,
  ExtractionStatus,
  ClientSelector,
  DocumentFormActions,
  formatCurrency
} from '../../components/DocumentForm';

const API = process.env.REACT_APP_BACKEND_URL + '/api';

export const AgentInvoiceUpload = () => {
  const navigate = useNavigate();
  const { invoiceId } = useParams(); // For edit mode
  const isEditMode = !!invoiceId;
  
  const [clients, setClients] = useState([]);
  const [selectedClient, setSelectedClient] = useState('');
  const [loading, setLoading] = useState(true);
  const [uploading, setUploading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [sending, setSending] = useState(false);
  
  // Upload state
  const [file, setFile] = useState(null);
  const [dragActive, setDragActive] = useState(false);
  
  // Extracted data state
  const [invoiceData, setInvoiceData] = useState(null);
  const [extractionWarning, setExtractionWarning] = useState(false);
  
  // Editing state
  const [editedData, setEditedData] = useState({
    title: '',
    total_amount: '',
    supplier_name: '',
    notes: '',
    summary: '',
    line_items: [],
    due_date: ''
  });

  useEffect(() => {
    fetchClients();
    if (isEditMode) {
      fetchExistingInvoice();
    }
  }, [invoiceId]);

  const fetchExistingInvoice = async () => {
    try {
      const res = await fetch(`${API}/documents/${invoiceId}`, { credentials: 'include' });
      if (res.ok) {
        const data = await res.json();
        setInvoiceData(data);
        setSelectedClient(data.client_id || '');
        // Handle both field name variations (amount vs total_amount, items vs line_items)
        const amount = data.amount || data.total_amount || 0;
        const lineItems = data.items || data.line_items || [];
        setEditedData({
          title: data.title || '',
          total_amount: amount.toString(),
          supplier_name: data.supplier_name || '',
          notes: data.notes || '',
          summary: data.summary || '',
          line_items: lineItems,
          due_date: data.due_date ? data.due_date.split('T')[0] : ''
        });
      } else {
        toast.error('Invoice not found');
        navigate('/agent/invoices');
      }
    } catch (error) {
      toast.error('Failed to load invoice');
    }
  };

  const fetchClients = async () => {
    try {
      const res = await fetch(`${API}/clients`, { credentials: 'include' });
      if (res.ok) {
        const data = await res.json();
        setClients(data);
      }
    } catch (error) {
      console.error('Failed to fetch clients:', error);
      toast.error('Failed to load clients');
    } finally {
      setLoading(false);
    }
  };

  const handleUpload = async () => {
    if (!file || !selectedClient) {
      toast.error('Please select a client and upload a PDF');
      return;
    }

    setUploading(true);
    const formData = new FormData();
    formData.append('file', file);
    formData.append('client_id', selectedClient);

    try {
      // Step 1: Upload and extract - this does NOT create a document
      const res = await fetch(`${API}/documents/upload?doc_type=invoice`, {
        method: 'POST',
        credentials: 'include',
        body: formData
      });

      if (res.ok) {
        const data = await res.json();
        // Store preview data (not a saved document yet)
        setInvoiceData({
          ...data,
          is_preview: true  // Flag to indicate this is unsaved preview
        });
        setExtractionWarning(data.extraction_warning);
        
        // Calculate due date (30 days from now)
        const dueDate = new Date();
        dueDate.setDate(dueDate.getDate() + 30);
        
        setEditedData({
          title: data.title || '',
          total_amount: String(data.amount || ''),
          supplier_name: data.supplier_name || '',
          notes: data.notes || '',
          summary: data.summary || '',
          line_items: (data.items || []).map(item => ({
            description: item.description || '',
            quantity: item.quantity || 1,
            unit_price: item.unit_price || 0,
            total: item.total || 0
          })),
          due_date: dueDate.toISOString().split('T')[0]
        });
        
        toast.success('PDF uploaded and analyzed - please review before saving');
      } else {
        const err = await res.json();
        throw new Error(err.detail || 'Upload failed');
      }
    } catch (error) {
      toast.error(error.message || 'Failed to upload PDF');
    } finally {
      setUploading(false);
    }
  };

  const handleSave = async (send = false) => {
    if (!invoiceData) return;
    
    if (send && (!editedData.total_amount || parseFloat(editedData.total_amount) <= 0)) {
      toast.error('Please enter a valid total amount before sending');
      return;
    }

    if (send) {
      setSending(true);
    } else {
      setSaving(true);
    }
    
    try {
      let documentId = invoiceData.document_id;
      
      // If this is a preview (not yet saved), create the document first
      if (invoiceData.is_preview) {
        const createRes = await fetch(`${API}/documents/create`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          credentials: 'include',
          body: JSON.stringify({
            preview_id: invoiceData.preview_id,
            type: 'invoice',
            client_id: selectedClient,
            title: editedData.title,
            amount: parseFloat(editedData.total_amount) || 0,
            items: editedData.line_items.filter(item => item.description),
            supplier_name: editedData.supplier_name,
            summary: editedData.summary,
            notes: editedData.notes,
            due_date: editedData.due_date,
            pdf_filename: invoiceData.pdf_filename,
            pdf_path: invoiceData.pdf_path,
            ai_extraction_confidence: invoiceData.ai_extraction_confidence
          })
        });

        if (!createRes.ok) {
          const err = await createRes.json();
          throw new Error(err.detail || 'Failed to create invoice');
        }

        const createdDoc = await createRes.json();
        documentId = createdDoc.document_id;
        
        // Update local state with saved document
        setInvoiceData({
          ...createdDoc,
          is_preview: false
        });
        
        toast.success('Invoice created as draft');
      } else {
        // Existing document - just update it
        const updateRes = await fetch(`${API}/documents/${documentId}`, {
          method: 'PUT',
          headers: { 'Content-Type': 'application/json' },
          credentials: 'include',
          body: JSON.stringify({
            title: editedData.title,
            amount: parseFloat(editedData.total_amount) || 0,
            supplier_name: editedData.supplier_name,
            notes: editedData.notes,
            summary: editedData.summary,
            items: editedData.line_items.filter(item => item.description),
            due_date: editedData.due_date
          })
        });

        if (!updateRes.ok) {
          const err = await updateRes.json();
          throw new Error(err.detail || 'Failed to save invoice');
        }
      }

      if (send) {
        const sendRes = await fetch(`${API}/documents/${documentId}/send`, {
          method: 'POST',
          credentials: 'include'
        });

        if (!sendRes.ok) {
          const err = await sendRes.json();
          throw new Error(err.detail || 'Failed to send invoice');
        }

        toast.success('Invoice sent to buyer');
        navigate('/agent/invoices');
      } else {
        navigate(`/agent/invoices/${documentId}`);
      }
    } catch (error) {
      toast.error(error.message || 'Failed to save invoice');
    } finally {
      setSaving(false);
      setSending(false);
    }
  };

  const handlePreviewPDF = () => {
    if (invoiceData?.document_id) {
      window.open(`${API}/documents/${invoiceData.document_id}/source-pdf`, '_blank');
    }
  };

  const clearFile = () => {
    setFile(null);
    setInvoiceData(null);
    setEditedData({
      title: '',
      total_amount: '',
      supplier_name: '',
      notes: '',
      summary: '',
      line_items: [],
      due_date: ''
    });
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

  return (
    <AgentLayout>
      <div className="max-w-4xl mx-auto space-y-6" data-testid="invoice-upload-page">
        {/* Header */}
        <div>
          <h1 className="text-2xl sm:text-3xl font-outfit font-semibold text-foreground tracking-tight">
            {isEditMode ? 'Edit Invoice' : 'New Invoice'}
          </h1>
          <p className="text-muted-foreground mt-1 text-sm sm:text-base">
            {isEditMode ? 'Update invoice details' : "Upload a supplier invoice PDF and we'll extract the details"}
          </p>
        </div>

        {/* Step 1: Select Client */}
        {!isEditMode && (
        <Card className="border-border rounded-lg">
          <CardHeader>
            <CardTitle className="text-base font-medium flex items-center gap-2">
              <span className="w-6 h-6 bg-primary text-primary-foreground rounded-full flex items-center justify-center text-sm">1</span>
              Select Client
            </CardTitle>
          </CardHeader>
          <CardContent>
            <ClientSelector
              clients={clients}
              selectedClient={selectedClient}
              onSelect={setSelectedClient}
              loading={false}
            />
          </CardContent>
        </Card>
        )}

        {/* Step 2: Upload PDF - only for new invoices */}
        {!isEditMode && (
        <Card className="border-border rounded-lg">
          <CardHeader>
            <CardTitle className="text-base font-medium flex items-center gap-2">
              <span className="w-6 h-6 bg-primary text-primary-foreground rounded-full flex items-center justify-center text-sm">2</span>
              Upload Invoice PDF
            </CardTitle>
          </CardHeader>
          <CardContent>
            {!invoiceData ? (
              <PdfUploadZone
                file={file}
                setFile={setFile}
                dragActive={dragActive}
                setDragActive={setDragActive}
                onUpload={handleUpload}
                uploading={uploading}
                disabled={!selectedClient}
                docType="invoice"
              />
            ) : (
              <div className="flex items-center justify-between p-4 bg-emerald-500/10 rounded-lg">
                <div className="flex items-center gap-3">
                  <CheckCircle className="w-5 h-5 text-emerald-600" />
                  <span className="font-medium text-foreground">PDF uploaded and analyzed</span>
                </div>
                <div className="flex gap-2">
                  <Button variant="outline" size="sm" onClick={handlePreviewPDF}>
                    <Eye className="w-4 h-4 mr-2" />
                    Preview
                  </Button>
                  <Button variant="outline" size="sm" onClick={clearFile}>
                    <X className="w-4 h-4 mr-2" />
                    Remove
                  </Button>
                </div>
              </div>
            )}
          </CardContent>
        </Card>
        )}

        {/* Step 3: Review & Edit Extracted Data - show in edit mode OR after upload */}
        {invoiceData && (
          <Card className="border-border rounded-lg">
            <CardHeader>
              <CardTitle className="text-base font-medium flex items-center gap-2">
                {!isEditMode && (
                  <span className="w-6 h-6 bg-primary text-primary-foreground rounded-full flex items-center justify-center text-sm">3</span>
                )}
                {isEditMode ? 'Edit Invoice Details' : 'Review & Edit Invoice Details'}
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-6">
              {extractionWarning && !isEditMode && (
                <ExtractionStatus
                  hasWarning={true}
                  confidence={null}
                  documentId={null}
                />
              )}

              {/* Basic Info */}
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div className="space-y-2">
                  <Label>Invoice Title</Label>
                  <Input
                    value={editedData.title}
                    onChange={(e) => setEditedData(prev => ({ ...prev, title: e.target.value }))}
                    placeholder="e.g., Bathroom Renovation Materials"
                    data-testid="title-input"
                  />
                </div>
                <div className="space-y-2">
                  <Label>Total Amount (CHF)</Label>
                  <Input
                    type="number"
                    step="0.01"
                    value={editedData.total_amount}
                    onChange={(e) => setEditedData(prev => ({ ...prev, total_amount: e.target.value }))}
                    placeholder="0.00"
                    className={cn(!editedData.total_amount && "border-amber-500")}
                    data-testid="amount-input"
                  />
                </div>
                <div className="space-y-2">
                  <Label>Supplier Name</Label>
                  <SupplierAutocomplete
                    value={editedData.supplier_name}
                    onChange={(value) => setEditedData(prev => ({ ...prev, supplier_name: value }))}
                    onContactSelect={(contact) => {
                      // Auto-populate related fields if we want to extend this later
                      setEditedData(prev => ({ 
                        ...prev, 
                        supplier_name: contact.supplier_name 
                      }));
                    }}
                    placeholder="Search suppliers or enter new..."
                    data-testid="supplier-input"
                  />
                </div>
                <div className="space-y-2">
                  <Label>Due Date</Label>
                  <Input
                    type="date"
                    value={editedData.due_date}
                    onChange={(e) => setEditedData(prev => ({ ...prev, due_date: e.target.value }))}
                    data-testid="due-date-input"
                  />
                </div>
              </div>

              {/* Line Items */}
              <LineItemsEditor
                items={editedData.line_items}
                onChange={(items) => {
                  setEditedData(prev => ({ ...prev, line_items: items }));
                  // Auto-update total from line items
                  const total = items.reduce((sum, item) => sum + (parseFloat(item.total) || 0), 0);
                  if (total > 0) {
                    setEditedData(prev => ({ ...prev, total_amount: String(total) }));
                  }
                }}
              />

              {/* Notes */}
              <div className="space-y-2">
                <Label>Notes (Optional)</Label>
                <Textarea
                  value={editedData.notes}
                  onChange={(e) => setEditedData(prev => ({ ...prev, notes: e.target.value }))}
                  placeholder="Add any notes for the buyer..."
                  rows={3}
                />
              </div>

              {/* Summary */}
              <div className="space-y-2">
                <Label>Card Summary</Label>
                <p className="text-xs text-muted-foreground">
                  This short description appears on the buyer's timeline card
                </p>
                <Textarea
                  value={editedData.summary}
                  onChange={(e) => setEditedData(prev => ({ ...prev, summary: e.target.value }))}
                  placeholder="e.g., Premium kitchen upgrade materials - marble countertops and fixtures"
                  rows={2}
                  data-testid="summary-input"
                />
              </div>

              {/* Hero Image */}
              <HeroImageUploader
                documentId={invoiceData.document_id}
                heroImageUrl={invoiceData.hero_image_url}
                onUpdate={(url) => setInvoiceData(prev => ({ ...prev, hero_image_url: url }))}
              />

              {/* Total Summary */}
              <div className="flex justify-end p-4 bg-muted/50 rounded-lg">
                <div className="text-right">
                  <p className="text-sm text-muted-foreground">Total Amount</p>
                  <p className="text-2xl font-semibold text-foreground">
                    CHF {formatCurrency(editedData.total_amount)}
                  </p>
                </div>
              </div>

              {/* Actions */}
              <DocumentFormActions
                onSaveDraft={() => handleSave(false)}
                onSend={() => handleSave(true)}
                saving={saving}
                sending={sending}
                canSend={editedData.total_amount && parseFloat(editedData.total_amount) > 0}
                sendLabel="Send to Buyer"
              />
            </CardContent>
          </Card>
        )}
      </div>
    </AgentLayout>
  );
};
