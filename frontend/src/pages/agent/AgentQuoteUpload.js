import { useState, useEffect } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { AgentLayout } from '../../components/AgentLayout';
import { Card, CardContent, CardHeader, CardTitle } from '../../components/ui/card';
import { Button } from '../../components/ui/button';
import { Input } from '../../components/ui/input';
import { Textarea } from '../../components/ui/textarea';
import { Label } from '../../components/ui/label';
import { toast } from 'sonner';
import { Loader2 } from 'lucide-react';
import { cn, formatContextSubtitle } from '../../lib/utils';
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

const getAuthHeaders = () => {
  const token = localStorage.getItem('auth_token');
  return token ? { 'Authorization': `Bearer ${token}` } : {};
};

export const AgentQuoteUpload = () => {
  const navigate = useNavigate();
  const { quoteId } = useParams(); // For edit mode
  const isEditMode = !!quoteId;
  
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
  const [quoteData, setQuoteData] = useState(null);
  const [extractionWarning, setExtractionWarning] = useState(false);
  
  // Editing state
  const [editedData, setEditedData] = useState({
    title: '',
    description: '',
    amount: '',
    supplier_name: '',
    notes: '',
    summary: '',
    line_items: []
  });

  useEffect(() => {
    fetchClients();
    if (isEditMode) {
      fetchExistingQuote();
    }
  }, [quoteId]);

  const fetchExistingQuote = async () => {
    try {
      const res = await fetch(`${API}/documents/${quoteId}`, { credentials: 'include', headers: getAuthHeaders() });
      if (res.ok) {
        const data = await res.json();
        setQuoteData(data);
        setSelectedClient(data.client_id || '');
        const amount = data.amount || 0;
        const lineItems = data.items || data.line_items || [];
        setEditedData({
          title: data.title || '',
          description: data.description || data.summary || '',
          amount: amount.toString(),
          supplier_name: data.supplier_name || '',
          notes: data.notes || '',
          summary: data.summary || '',
          line_items: lineItems
        });
      } else {
        toast.error('Quote not found');
        navigate('/agent/quotes');
      }
    } catch (error) {
      toast.error('Failed to load quote');
    }
  };

  const fetchClients = async () => {
    try {
      const res = await fetch(`${API}/clients`, { credentials: 'include', headers: getAuthHeaders() });
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

    // Include project_id and unit_id from the selected client
    const client = clients.find(c => c.client_id === selectedClient);
    if (client?.project_id) formData.append('project_id', client.project_id);
    if (client?.unit_id) formData.append('unit_id', client.unit_id);

    try {
      // Step 1: Upload and extract - this does NOT create a document
      const res = await fetch(`${API}/documents/upload?doc_type=quote`, {
        method: 'POST',
        credentials: 'include',
        headers: getAuthHeaders(),
        body: formData
      });

      if (res.ok) {
        const data = await res.json();
        // Store preview data (not a saved document yet)
        setQuoteData({
          ...data,
          is_preview: true  // Flag to indicate this is unsaved preview
        });
        setExtractionWarning(data.extraction_warning);
        
        // AI extraction puts the summary in 'summary' field
        // We map it to 'description' for editing and display
        setEditedData({
          title: data.title || '',
          description: data.summary || data.description || '',
          amount: data.amount ? String(data.amount) : '',
          supplier_name: data.supplier_name || '',
          notes: data.notes || '',
          summary: data.summary || '',
          line_items: data.items || []
        });
        
        toast.success('PDF uploaded and analyzed - please review before saving');
        
        if (data.extraction_warning) {
          toast.warning('Price could not be extracted. Please enter it manually.');
        }
      } else {
        const error = await res.json();
        throw new Error(error.detail || 'Upload failed');
      }
    } catch (error) {
      console.error('Upload error:', error);
      toast.error(error.message || 'Failed to upload PDF');
    } finally {
      setUploading(false);
    }
  };

  const handleSave = async (andSend = false) => {
    if (!quoteData) return;
    
    const totalAmount = parseFloat(editedData.amount);
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
      let documentId = quoteData.document_id;
      
      // If this is a preview (not yet saved), create the document first
      if (quoteData.is_preview) {
        const createRes = await fetch(`${API}/documents/create`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json', ...getAuthHeaders() },
          credentials: 'include',
          body: JSON.stringify({
            preview_id: quoteData.preview_id,
            type: 'quote',
            client_id: selectedClient,
            project_id: clients.find(c => c.client_id === selectedClient)?.project_id || null,
            unit_id: clients.find(c => c.client_id === selectedClient)?.unit_id || null,
            title: editedData.title,
            amount: totalAmount,
            items: editedData.line_items.length > 0 ? editedData.line_items : undefined,
            supplier_name: editedData.supplier_name,
            summary: editedData.summary || editedData.description,
            notes: editedData.notes,
            pdf_filename: quoteData.pdf_filename,
            pdf_stored_filename: quoteData.pdf_stored_filename,
            ai_extraction_confidence: quoteData.ai_extraction_confidence
          })
        });

        if (!createRes.ok) {
          const err = await createRes.json();
          throw new Error(err.detail || 'Failed to create quote');
        }

        const createdDoc = await createRes.json();
        documentId = createdDoc.document_id;
        
        // Update local state with saved document
        setQuoteData({
          ...createdDoc,
          is_preview: false
        });
        
        toast.success('Quote created as draft');
      } else {
        // Existing document - just update it
        const updateRes = await fetch(`${API}/documents/${documentId}`, {
          method: 'PUT',
          headers: { 'Content-Type': 'application/json', ...getAuthHeaders() },
          credentials: 'include',
          body: JSON.stringify({
            title: editedData.title,
            description: editedData.description,
            amount: totalAmount,
            supplier_name: editedData.supplier_name,
            notes: editedData.notes,
            summary: editedData.summary,
            items: editedData.line_items.length > 0 ? editedData.line_items : undefined
          })
        });

        if (!updateRes.ok) {
          throw new Error('Failed to save quote');
        }
      }

      if (andSend) {
        const sendRes = await fetch(`${API}/documents/${documentId}/send`, {
          method: 'POST',
          credentials: 'include',
          headers: getAuthHeaders()
        });

        if (sendRes.ok) {
          toast.success('Quote sent to buyer');
          navigate('/agent/quotes');
        } else {
          throw new Error('Failed to send quote');
        }
      } else {
        navigate('/agent/quotes');
      }
    } catch (error) {
      console.error('Save error:', error);
      toast.error(error.message || 'Failed to save quote');
    } finally {
      setSaving(false);
      setSending(false);
    }
  };

  const documentId = quoteData?.document_id;

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
      <div className="max-w-4xl mx-auto space-y-6" data-testid="quote-upload-page">
        {/* Header */}
        <div>
          <h1 className="text-2xl sm:text-3xl font-outfit font-semibold text-foreground tracking-tight">
            New Quote
          </h1>
          <p className="text-muted-foreground mt-1 text-sm sm:text-base">Upload a supplier PDF to create a quote</p>
        </div>

        {/* Step 1: Select Client */}
        {!quoteData && (
          <Card>
            <CardHeader>
              <CardTitle className="text-lg">1. Select Client</CardTitle>
            </CardHeader>
            <CardContent>
              <ClientSelector
                clients={clients}
                selectedClient={selectedClient}
                onSelect={setSelectedClient}
                loading={false}
              />
              {(() => {
                const c = clients.find(cl => cl.client_id === selectedClient);
                if (!c) return null;
                const subtitle = formatContextSubtitle(c);
                return subtitle ? <p className="text-sm text-muted-foreground mt-2">{subtitle}</p> : null;
              })()}
            </CardContent>
          </Card>
        )}

        {/* Step 2: Upload PDF */}
        {!quoteData && (
          <Card>
            <CardHeader>
              <CardTitle className="text-lg">2. Upload Supplier PDF</CardTitle>
            </CardHeader>
            <CardContent>
              <PdfUploadZone
                file={file}
                setFile={setFile}
                dragActive={dragActive}
                setDragActive={setDragActive}
                onUpload={handleUpload}
                uploading={uploading}
                disabled={!selectedClient}
                docType="quote"
              />
            </CardContent>
          </Card>
        )}

        {/* Step 3: Review & Edit Extraction */}
        {quoteData && (
          <>
            <ExtractionStatus
              hasWarning={extractionWarning}
              confidence={quoteData.ai_extraction_confidence}
              documentId={documentId}
            />

            <Card>
              <CardHeader>
                <CardTitle className="text-lg">3. Review & Edit</CardTitle>
              </CardHeader>
              <CardContent className="space-y-6">
                {/* Basic Info */}
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                  <div className="sm:col-span-2">
                    <Label htmlFor="title">Quote Title *</Label>
                    <Input
                      id="title"
                      value={editedData.title}
                      onChange={(e) => setEditedData(prev => ({ ...prev, title: e.target.value }))}
                      className="mt-1"
                      data-testid="title-input"
                    />
                  </div>
                  
                  <div>
                    <Label htmlFor="amount" className="flex items-center gap-2">
                      Total Amount (CHF) *
                      {extractionWarning && (
                        <span className="text-xs text-amber-600">Required</span>
                      )}
                    </Label>
                    <Input
                      id="amount"
                      type="number"
                      step="0.01"
                      value={editedData.amount}
                      onChange={(e) => setEditedData(prev => ({ ...prev, amount: e.target.value }))}
                      className={cn("mt-1", extractionWarning && !editedData.amount && "border-amber-500")}
                      placeholder="0.00"
                      data-testid="total-input"
                    />
                  </div>
                  
                  <div>
                    <Label htmlFor="supplier">Supplier Name</Label>
                    <SupplierAutocomplete
                      value={editedData.supplier_name}
                      onChange={(value) => setEditedData(prev => ({ ...prev, supplier_name: value }))}
                      onContactSelect={(contact) => {
                        setEditedData(prev => ({ 
                          ...prev, 
                          supplier_name: contact.supplier_name 
                        }));
                      }}
                      placeholder="Search suppliers or enter new..."
                      className="mt-1"
                    />
                  </div>
                </div>

                <div>
                  <Label htmlFor="description">Description</Label>
                  <Textarea
                    id="description"
                    value={editedData.description}
                    onChange={(e) => setEditedData(prev => ({ ...prev, description: e.target.value }))}
                    className="mt-1"
                    rows={3}
                  />
                </div>

                {/* Line Items */}
                <LineItemsEditor
                  items={editedData.line_items}
                  onChange={(items) => setEditedData(prev => ({ ...prev, line_items: items }))}
                />

                <div>
                  <Label htmlFor="notes">Notes for Buyer</Label>
                  <Textarea
                    id="notes"
                    value={editedData.notes}
                    onChange={(e) => setEditedData(prev => ({ ...prev, notes: e.target.value }))}
                    className="mt-1"
                    rows={2}
                    placeholder="Any additional notes..."
                  />
                </div>

                {/* Card Summary */}
                <div>
                  <Label htmlFor="summary">Card Summary</Label>
                  <p className="text-xs text-muted-foreground mb-1">
                    Short description shown on the buyer's timeline card
                  </p>
                  <Textarea
                    id="summary"
                    value={editedData.summary}
                    onChange={(e) => setEditedData(prev => ({ ...prev, summary: e.target.value }))}
                    className="mt-1"
                    rows={2}
                    placeholder="e.g., Premium kitchen upgrade with marble countertops"
                    data-testid="summary-input"
                  />
                </div>

                {/* Hero Image */}
                <HeroImageUploader
                  documentId={documentId}
                  heroImageUrl={quoteData?.hero_image_url}
                  onUpdate={(url) => setQuoteData(prev => ({ ...prev, hero_image_url: url }))}
                />

                {/* Quote Total Summary */}
                <div className="p-4 bg-muted rounded-lg">
                  <div className="flex items-center justify-between">
                    <span className="text-muted-foreground">Quote Total</span>
                    <span className="text-2xl font-bold text-foreground">
                      CHF {formatCurrency(parseFloat(editedData.amount) || 0)}
                    </span>
                  </div>
                </div>

                {/* Actions */}
                <DocumentFormActions
                  onSaveDraft={() => handleSave(false)}
                  onSend={() => handleSave(true)}
                  saving={saving}
                  sending={sending}
                  canSend={editedData.amount && parseFloat(editedData.amount) > 0}
                  sendLabel="Send to Buyer"
                />
              </CardContent>
            </Card>
          </>
        )}
      </div>
    </AgentLayout>
  );
};
