import { useState, useEffect, useCallback } from 'react';
import { useNavigate, useParams, useSearchParams } from 'react-router-dom';
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

export const AgentDocumentUpload = () => {
  const navigate = useNavigate();
  const { documentId } = useParams();
  const [searchParams] = useSearchParams();
  const isEditMode = !!documentId;
  
  // Document type from URL param or from loaded document
  const [docType, setDocType] = useState(searchParams.get('type') || 'quote');
  
  const [clients, setClients] = useState([]);
  const [selectedClient, setSelectedClient] = useState('');
  const [loading, setLoading] = useState(true);
  const [uploading, setUploading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [sending, setSending] = useState(false);
  
  const [file, setFile] = useState(null);
  const [dragActive, setDragActive] = useState(false);
  
  const [docData, setDocData] = useState(null);
  const [extractionWarning, setExtractionWarning] = useState(false);
  
  const [editedData, setEditedData] = useState({
    title: '',
    description: '',
    amount: '',
    supplier_name: '',
    notes: '',
    summary: '',
    due_date: '',
    line_items: []
  });
  const [unitRecipients, setUnitRecipients] = useState([]);
  const [approverClientIds, setApproverClientIds] = useState([]);
  const [approvalMode, setApprovalMode] = useState('any');
  const [approvalRequiredCount, setApprovalRequiredCount] = useState(1);

  useEffect(() => {
    fetchClients();
    if (isEditMode) fetchExistingDoc();
  }, [documentId]);

  useEffect(() => {
    const selected = clients.find((c) => c.client_id === selectedClient);
    if (!selected) {
      setUnitRecipients([]);
      setApproverClientIds([]);
      setApprovalRequiredCount(1);
      return;
    }
    const hasUnit = !!selected.unit_id;
    const recipients = hasUnit
      ? clients.filter((c) => c.project_id === selected.project_id && c.unit_id === selected.unit_id)
      : [selected];
    setUnitRecipients(recipients);
    const ids = recipients.map((r) => r.client_id);
    setApproverClientIds((prev) => {
      const kept = prev.filter((id) => ids.includes(id));
      return kept.length > 0 ? kept : ids;
    });
    setApprovalRequiredCount((prev) => Math.max(1, Math.min(prev, ids.length || 1)));
  }, [clients, selectedClient]);

  useEffect(() => {
    if (docData?.is_preview) {
      const handler = (e) => { e.preventDefault(); e.returnValue = ''; };
      window.addEventListener('beforeunload', handler);
      return () => window.removeEventListener('beforeunload', handler);
    }
  }, [docData?.is_preview]);

  const fetchExistingDoc = async () => {
    try {
      const res = await fetch(`${API}/documents/${documentId}`, { credentials: 'include', headers: getAuthHeaders() });
      if (res.ok) {
        const data = await res.json();
        setDocData(data);
        setDocType(data.type || 'quote');
        setSelectedClient(data.client_id || '');
        setApproverClientIds(data.approver_client_ids || []);
        setApprovalRequiredCount(data.approval_required_count || 1);
        setApprovalMode(data.approval_required_count > 1 ? 'custom' : 'any');
        setEditedData({
          title: data.title || '',
          description: data.description || data.summary || '',
          amount: (data.amount || 0).toString(),
          supplier_name: data.supplier_name || '',
          notes: data.notes || '',
          summary: data.summary || '',
          due_date: data.due_date || '',
          line_items: data.items || data.line_items || []
        });
      } else {
        toast.error('Document not found');
        navigate('/agent/documents');
      }
    } catch {
      toast.error('Failed to load document');
    }
  };

  const fetchClients = async () => {
    try {
      const res = await fetch(`${API}/clients`, { credentials: 'include', headers: getAuthHeaders() });
      if (res.ok) {
        const data = await res.json();
        setClients(data);
        if (data.length === 1) setSelectedClient(data[0].client_id);
      }
    } catch {
      console.error('Failed to fetch clients');
    } finally {
      setLoading(false);
    }
  };

  const handleFileSelect = async (selectedFile) => {
    const fileToUpload = (selectedFile instanceof File) ? selectedFile : file;
    if (!fileToUpload) {
      toast.error('No file selected');
      return;
    }
    if (fileToUpload.type !== 'application/pdf') {
      toast.error('Please upload a PDF file');
      return;
    }
    if (!selectedClient) {
      toast.error('Please select a client first');
      return;
    }
    setUploading(true);
    
    const formData = new FormData();
    formData.append('file', fileToUpload);
    formData.append('client_id', selectedClient);
    formData.append('doc_type', docType);

    try {
      const res = await fetch(`${API}/documents/upload`, {
        method: 'POST', credentials: 'include', headers: getAuthHeaders(),
        body: formData
      });
      if (res.ok) {
        const data = await res.json();
        setDocData(data);
        setExtractionWarning(data.extraction_warning || false);
        setEditedData({
          title: data.title || '',
          description: data.summary || data.description || '',
          amount: (data.amount || 0).toString(),
          supplier_name: data.supplier_name || '',
          notes: data.notes || '',
          summary: data.summary || '',
          due_date: data.due_date || '',
          line_items: data.items || []
        });
        toast.success('PDF uploaded and analyzed');
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
    if (!docData) return;
    const totalAmount = parseFloat(editedData.amount);
    if (!totalAmount || totalAmount <= 0) {
      toast.error('Please enter a valid total amount');
      return;
    }
    if (andSend) setSending(true); else setSaving(true);

    try {
      let docId = docData.document_id;
      
      if (docData.is_preview) {
        const client = clients.find(c => c.client_id === selectedClient);
        const createRes = await fetch(`${API}/documents/create`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json', ...getAuthHeaders() },
          credentials: 'include',
          body: JSON.stringify({
            preview_id: docData.preview_id,
            type: docType,
            client_id: selectedClient,
            project_id: client?.project_id || null,
            unit_id: client?.unit_id || null,
            title: editedData.title,
            amount: totalAmount,
            items: editedData.line_items?.length > 0 ? editedData.line_items : undefined,
            supplier_name: editedData.supplier_name,
            summary: editedData.summary || editedData.description,
            notes: editedData.notes,
            due_date: editedData.due_date || undefined,
            pdf_filename: docData.pdf_filename,
            pdf_stored_filename: docData.pdf_stored_filename,
            ai_extraction_confidence: docData.ai_extraction_confidence,
            approver_client_ids: approverClientIds,
            approval_required_count: approvalMode === 'all'
              ? approverClientIds.length
              : approvalMode === 'any'
                ? 1
                : approvalRequiredCount
          })
        });
        if (!createRes.ok) {
          const err = await createRes.json();
          throw new Error(err.detail || 'Failed to create document');
        }
        const created = await createRes.json();
        docId = created.document_id;
        setDocData({ ...created, is_preview: false });
        toast.success(`${docType === 'invoice' ? 'Invoice' : 'Quote'} created as draft`);
      } else {
        const updateRes = await fetch(`${API}/documents/${docId}`, {
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
            due_date: editedData.due_date || undefined,
            items: editedData.line_items?.length > 0 ? editedData.line_items : undefined,
            approver_client_ids: approverClientIds,
            approval_required_count: approvalMode === 'all'
              ? approverClientIds.length
              : approvalMode === 'any'
                ? 1
                : approvalRequiredCount
          })
        });
        if (!updateRes.ok) throw new Error('Failed to save document');
      }

      if (andSend) {
        const sendRes = await fetch(`${API}/documents/${docId}/send`, {
          method: 'POST',
          credentials: 'include',
          headers: { 'Content-Type': 'application/json', ...getAuthHeaders() },
          body: JSON.stringify({
            approver_client_ids: approverClientIds,
            approval_mode: approvalMode,
            approval_required_count: approvalMode === 'all'
              ? approverClientIds.length
              : approvalMode === 'any'
                ? 1
                : approvalRequiredCount,
          }),
        });
        if (sendRes.ok) {
          toast.success(`${docType === 'invoice' ? 'Invoice' : 'Quote'} sent to unit recipients`);
          navigate('/agent/documents');
        } else throw new Error('Failed to send');
      } else {
        navigate('/agent/documents');
      }
    } catch (error) {
      console.error('Save error:', error);
      toast.error(error.message || 'Failed to save');
    } finally {
      setSaving(false);
      setSending(false);
    }
  };

  const currentDocId = docData?.document_id;

  const autoSaveDraft = async () => {
    if (!docData || !docData.is_preview) return docData?.document_id;
    const totalAmount = parseFloat(editedData.amount) || 0;
    try {
      const client = clients.find(c => c.client_id === selectedClient);
      const createRes = await fetch(`${API}/documents/create`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', ...getAuthHeaders() },
        credentials: 'include',
        body: JSON.stringify({
          preview_id: docData.preview_id,
          type: docType,
          client_id: selectedClient,
          project_id: client?.project_id || null,
          unit_id: client?.unit_id || null,
          title: editedData.title,
          amount: totalAmount,
          items: editedData.line_items?.length > 0 ? editedData.line_items : undefined,
          supplier_name: editedData.supplier_name,
          summary: editedData.summary || editedData.description,
          notes: editedData.notes,
          due_date: editedData.due_date || undefined,
          pdf_filename: docData.pdf_filename,
          pdf_stored_filename: docData.pdf_stored_filename,
          ai_extraction_confidence: docData.ai_extraction_confidence,
          approver_client_ids: approverClientIds,
          approval_required_count: approvalMode === 'all'
            ? approverClientIds.length
            : approvalMode === 'any'
              ? 1
              : approvalRequiredCount,
        })
      });
      if (!createRes.ok) return null;
      const created = await createRes.json();
      setDocData({ ...created, is_preview: false });
      toast.success('Draft saved');
      return created.document_id;
    } catch { return null; }
  };

  const handlePreviewPDF = () => {
    if (currentDocId) {
      window.open(`${API}/documents/${currentDocId}/source-pdf`, '_blank');
    }
  };

  const clearFile = () => {
    setFile(null);
    setDocData(null);
    setEditedData({ title: '', description: '', amount: '', supplier_name: '', notes: '', summary: '', due_date: '', line_items: [] });
    setExtractionWarning(false);
  };

  const updateLineItem = (index, field, value) => {
    const items = [...editedData.line_items];
    items[index] = { ...items[index], [field]: value };
    if (field === 'quantity' || field === 'unit_price') {
      items[index].total = (parseFloat(items[index].quantity) || 0) * (parseFloat(items[index].unit_price) || 0);
    }
    setEditedData({ ...editedData, line_items: items });
    const total = items.reduce((sum, item) => sum + (parseFloat(item.total) || 0), 0);
    if (total > 0) setEditedData(prev => ({ ...prev, line_items: items, amount: total.toFixed(2) }));
  };

  const addLineItem = () => {
    setEditedData({
      ...editedData,
      line_items: [...editedData.line_items, { description: '', quantity: 1, unit_price: 0, total: 0 }]
    });
  };

  const removeLineItem = (index) => {
    const items = editedData.line_items.filter((_, i) => i !== index);
    setEditedData({ ...editedData, line_items: items });
  };

  const typeLabel = docType === 'invoice' ? 'Invoice' : 'Quote';

  if (loading) {
    return <AgentLayout><div className="flex items-center justify-center min-h-[400px]"><Loader2 className="w-8 h-8 animate-spin text-primary" /></div></AgentLayout>;
  }

  return (
    <AgentLayout>
      <div className="max-w-4xl mx-auto space-y-6" data-testid="document-upload">
        {/* Header */}
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-outfit font-semibold text-foreground">
              {isEditMode ? `Edit ${typeLabel} Details` : `Review & Edit ${typeLabel} Details`}
            </h1>
            <p className="text-muted-foreground mt-1">
              {isEditMode ? `Update ${typeLabel.toLowerCase()} details` : `Upload a supplier ${typeLabel.toLowerCase()} PDF and we'll extract the details`}
            </p>
          </div>
        </div>

        {/* Client Selection */}
        {!isEditMode && (
          <ClientSelector
            clients={clients}
            selectedClient={selectedClient}
            onSelect={setSelectedClient}
            subtitle={selectedClient ? formatContextSubtitle(clients.find(c => c.client_id === selectedClient)) : ''}
          />
        )}

        {/* PDF Upload or Extraction Status */}
        {!isEditMode && !docData && (
          <PdfUploadZone
            file={file}
            setFile={setFile}
            dragActive={dragActive}
            setDragActive={setDragActive}
            onUpload={handleFileSelect}
            uploading={uploading}
            disabled={!selectedClient}
            docType={docType}
          />
        )}

        {docData && extractionWarning && (
          <ExtractionStatus confidence={docData.ai_extraction_confidence} />
        )}

        {/* Document Form */}
        {docData && (
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center justify-between">
                <span>{typeLabel} Details</span>
                {docData.pdf_filename && (
                  <Button variant="outline" size="sm" onClick={handlePreviewPDF} disabled={!currentDocId}>
                    View Source PDF
                  </Button>
                )}
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-6">
              {/* Type selector for new docs */}
              {!isEditMode && docData.is_preview && (
                <div className="space-y-2">
                  <Label>Document Type</Label>
                  <div className="flex gap-2">
                    <Button variant={docType === 'quote' ? 'default' : 'outline'} size="sm" onClick={() => setDocType('quote')}>Quote</Button>
                    <Button variant={docType === 'invoice' ? 'default' : 'outline'} size="sm" onClick={() => setDocType('invoice')}>Invoice</Button>
                  </div>
                </div>
              )}

              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div className="space-y-2">
                  <Label>Title</Label>
                  <Input value={editedData.title} onChange={(e) => setEditedData({...editedData, title: e.target.value})} />
                </div>
                <div className="space-y-2">
                  <Label>Supplier Name</Label>
                  <SupplierAutocomplete value={editedData.supplier_name} onChange={(val) => setEditedData({...editedData, supplier_name: val})} />
                </div>
              </div>

              {docType === 'invoice' && (
                <div className="space-y-2">
                  <Label>Due Date</Label>
                  <Input type="date" value={editedData.due_date} onChange={(e) => setEditedData({...editedData, due_date: e.target.value})} />
                </div>
              )}

              <div className="space-y-2">
                <Label>Summary / Description</Label>
                <Textarea value={editedData.summary || editedData.description} onChange={(e) => setEditedData({...editedData, summary: e.target.value, description: e.target.value})} rows={3} />
              </div>

              <div className="space-y-2">
                <Label>Notes</Label>
                <Textarea value={editedData.notes} onChange={(e) => setEditedData({...editedData, notes: e.target.value})} rows={2} placeholder="Internal notes..." />
              </div>

              {/* Line Items */}
              <LineItemsEditor
                items={editedData.line_items}
                onUpdateItem={updateLineItem}
                onAddItem={addLineItem}
                onRemoveItem={removeLineItem}
              />

              {/* Hero Image */}
              <HeroImageUploader
                documentId={currentDocId}
                heroImageUrl={docData?.hero_image_url}
                onUpdate={(url) => setDocData(prev => ({ ...prev, hero_image_url: url }))}
                onAutoSave={autoSaveDraft}
              />

              {/* Unit Recipients and Approval */}
              {selectedClient && unitRecipients.length > 0 && (
                <div className="space-y-3 rounded-lg border p-4">
                  <Label>Recipients and approvals</Label>
                  <p className="text-xs text-muted-foreground">
                    This {typeLabel.toLowerCase()} will be sent to all owners on this unit ({unitRecipients.length} recipient{unitRecipients.length > 1 ? 's' : ''}).
                  </p>
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
                    {unitRecipients.map((recipient) => (
                      <label key={recipient.client_id} className="flex items-center gap-2 text-sm">
                        <input
                          type="checkbox"
                          checked={approverClientIds.includes(recipient.client_id)}
                          onChange={(e) => {
                            if (e.target.checked) {
                              setApproverClientIds((prev) => [...prev, recipient.client_id]);
                            } else {
                              setApproverClientIds((prev) => prev.filter((id) => id !== recipient.client_id));
                            }
                          }}
                        />
                        <span>{recipient.name} ({recipient.email})</span>
                      </label>
                    ))}
                  </div>
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                    <div className="space-y-1">
                      <Label>Approval rule</Label>
                      <select
                        className="w-full rounded-md border bg-background px-3 py-2 text-sm"
                        value={approvalMode}
                        onChange={(e) => setApprovalMode(e.target.value)}
                      >
                        <option value="any">Any 1 approval</option>
                        <option value="all">All selected approvers</option>
                        <option value="custom">Custom number</option>
                      </select>
                    </div>
                    {approvalMode === 'custom' && (
                      <div className="space-y-1">
                        <Label>Required approvals</Label>
                        <Input
                          type="number"
                          min={1}
                          max={Math.max(1, approverClientIds.length)}
                          value={approvalRequiredCount}
                          onChange={(e) => setApprovalRequiredCount(Number(e.target.value || 1))}
                        />
                      </div>
                    )}
                  </div>
                </div>
              )}

              {/* Total */}
              <div className="p-4 bg-muted rounded-lg">
                <div className="flex items-center justify-between">
                  <span className="text-muted-foreground">{typeLabel} Total</span>
                  <span className="text-2xl font-bold text-foreground">
                    CHF {formatCurrency(editedData.amount)}
                  </span>
                </div>
                <div className="mt-2">
                  <Label className="text-sm">Total Amount (CHF)</Label>
                  <Input type="number" value={editedData.amount} onChange={(e) => setEditedData({...editedData, amount: e.target.value})} className="mt-1 max-w-xs" />
                </div>
              </div>

              {/* Actions */}
              <DocumentFormActions
                onSaveDraft={() => handleSave(false)}
                onSend={() => handleSave(true)}
                saving={saving}
                sending={sending}
                sendLabel={`Send ${typeLabel} to Unit`}
                canSend={
                  !!editedData.title &&
                  !!editedData.amount &&
                  !!selectedClient &&
                  approverClientIds.length > 0 &&
                  (
                    approvalMode !== 'custom' ||
                    (approvalRequiredCount >= 1 && approvalRequiredCount <= approverClientIds.length)
                  )
                }
              />
            </CardContent>
          </Card>
        )}
      </div>
    </AgentLayout>
  );
};
