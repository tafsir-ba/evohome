import { useState, useEffect, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { Card, CardContent, CardHeader, CardTitle } from './ui/card';
import { Button } from './ui/button';
import { Input } from './ui/input';
import { Textarea } from './ui/textarea';
import { Label } from './ui/label';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from './ui/select';
import { toast } from 'sonner';
import { 
  Upload, 
  FileText, 
  Receipt,
  Loader2, 
  AlertTriangle, 
  CheckCircle, 
  X,
  Plus,
  Trash2,
  Send,
  Save,
  Eye,
  ImageIcon
} from 'lucide-react';
import { cn } from '../lib/utils';

const API = process.env.REACT_APP_BACKEND_URL + '/api';

const getAuthHeaders = () => {
  const token = localStorage.getItem('auth_token');
  return token ? { 'Authorization': `Bearer ${token}` } : {};
};

// Format currency helper
const formatCurrency = (amount) => {
  return new Intl.NumberFormat('de-CH', { 
    style: 'decimal', 
    minimumFractionDigits: 2,
    maximumFractionDigits: 2 
  }).format(amount || 0);
};

// PDF Upload Zone Component
export const PdfUploadZone = ({ 
  file, 
  setFile, 
  dragActive, 
  setDragActive,
  onUpload,
  uploading,
  disabled,
  docType = 'quote'
}) => {
  const handleDrag = useCallback((e) => {
    e.preventDefault();
    e.stopPropagation();
    if (e.type === "dragenter" || e.type === "dragover") {
      setDragActive(true);
    } else if (e.type === "dragleave") {
      setDragActive(false);
    }
  }, [setDragActive]);

  const handleDrop = useCallback((e) => {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(false);
    
    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      const droppedFile = e.dataTransfer.files[0];
      if (droppedFile.type === 'application/pdf') {
        setFile(droppedFile);
      } else {
        toast.error('Please upload a PDF file');
      }
    }
  }, [setFile, setDragActive]);

  const handleFileChange = (e) => {
    if (e.target.files && e.target.files[0]) {
      const selectedFile = e.target.files[0];
      if (selectedFile.type === 'application/pdf') {
        setFile(selectedFile);
      } else {
        toast.error('Please upload a PDF file');
      }
    }
  };

  const Icon = docType === 'invoice' ? Receipt : FileText;

  return (
    <div className="space-y-4">
      <div
        className={cn(
          "border-2 border-dashed rounded-xl p-8 text-center transition-all cursor-pointer",
          dragActive && "border-primary bg-primary/5",
          file && "border-emerald-500 bg-emerald-500/5",
          !dragActive && !file && "border-border hover:border-primary/50"
        )}
        onDragEnter={handleDrag}
        onDragLeave={handleDrag}
        onDragOver={handleDrag}
        onDrop={handleDrop}
        onClick={() => document.getElementById(`pdf-upload-${docType}`)?.click()}
      >
        <input
          type="file"
          id={`pdf-upload-${docType}`}
          accept=".pdf"
          className="hidden"
          onChange={handleFileChange}
          data-testid="file-input"
        />
        
        {file ? (
          <div className="flex items-center justify-center gap-4">
            <div className="w-12 h-12 rounded-lg bg-emerald-500/10 flex items-center justify-center">
              <Icon className="w-6 h-6 text-emerald-600" />
            </div>
            <div className="text-left">
              <p className="font-medium text-foreground">{file.name}</p>
              <p className="text-sm text-muted-foreground">{(file.size / 1024).toFixed(1)} KB</p>
            </div>
            <Button
              variant="ghost"
              size="icon"
              onClick={(e) => { e.stopPropagation(); setFile(null); }}
              className="text-muted-foreground hover:text-destructive"
            >
              <X className="w-4 h-4" />
            </Button>
          </div>
        ) : (
          <>
            <Upload className="w-10 h-10 text-muted-foreground mx-auto mb-4" />
            <p className="text-foreground font-medium mb-1">
              Drop your {docType} PDF here
            </p>
            <p className="text-sm text-muted-foreground">or click to browse</p>
          </>
        )}
      </div>

      {file && onUpload && (
        <Button
          className="w-full"
          onClick={onUpload}
          disabled={uploading || disabled}
          data-testid="upload-btn"
        >
          {uploading ? (
            <>
              <Loader2 className="w-4 h-4 mr-2 animate-spin" />
              Analyzing PDF...
            </>
          ) : (
            <>
              <Upload className="w-4 h-4 mr-2" />
              Upload & Extract
            </>
          )}
        </Button>
      )}
    </div>
  );
};

// Line Items Editor Component
export const LineItemsEditor = ({ items, onChange }) => {
  const addItem = () => {
    onChange([...items, { description: '', quantity: 1, unit_price: 0, total: 0 }]);
  };

  const updateItem = (index, field, value) => {
    const newItems = [...items];
    newItems[index] = { ...newItems[index], [field]: value };
    
    if (field === 'quantity' || field === 'unit_price') {
      const qty = field === 'quantity' ? parseFloat(value) || 0 : parseFloat(newItems[index].quantity) || 0;
      const price = field === 'unit_price' ? parseFloat(value) || 0 : parseFloat(newItems[index].unit_price) || 0;
      newItems[index].total = qty * price;
    }
    
    onChange(newItems);
  };

  const removeItem = (index) => {
    onChange(items.filter((_, i) => i !== index));
  };

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <Label>Line Items (Optional)</Label>
        <Button variant="outline" size="sm" onClick={addItem}>
          <Plus className="w-4 h-4 mr-1" />
          Add Item
        </Button>
      </div>
      
      {items.length > 0 ? (
        <div className="space-y-2">
          {items.map((item, idx) => (
            <div key={idx} className="flex items-center gap-2 p-3 bg-muted/50 rounded-lg">
              <Input
                placeholder="Description"
                value={item.description}
                onChange={(e) => updateItem(idx, 'description', e.target.value)}
                className="flex-1"
              />
              <Input
                type="number"
                placeholder="Qty"
                value={item.quantity}
                onChange={(e) => updateItem(idx, 'quantity', e.target.value)}
                className="w-20"
              />
              <Input
                type="number"
                step="0.01"
                placeholder="Price"
                value={item.unit_price}
                onChange={(e) => updateItem(idx, 'unit_price', e.target.value)}
                className="w-28"
              />
              <span className="text-sm font-medium text-muted-foreground w-24 text-right">
                CHF {formatCurrency(item.total)}
              </span>
              <Button
                variant="ghost"
                size="icon"
                onClick={() => removeItem(idx)}
                className="text-muted-foreground hover:text-destructive"
              >
                <Trash2 className="w-4 h-4" />
              </Button>
            </div>
          ))}
        </div>
      ) : (
        <p className="text-sm text-muted-foreground p-4 bg-muted/50 rounded-lg text-center">
          No line items. You can add them manually.
        </p>
      )}
    </div>
  );
};

// Hero Image Uploader Component
export const HeroImageUploader = ({ documentId, heroImageUrl, onUpdate }) => {
  const [uploading, setUploading] = useState(false);

  const handleUpload = async (e) => {
    const file = e.target.files?.[0];
    if (!file || !documentId) return;

    const allowedTypes = ['image/jpeg', 'image/jpg', 'image/png', 'image/webp'];
    if (!allowedTypes.includes(file.type)) {
      toast.error('Please upload a JPEG, PNG, or WebP image');
      return;
    }

    setUploading(true);
    const formData = new FormData();
    formData.append('file', file);

    try {
      const token = localStorage.getItem('auth_token');
      const res = await fetch(`${API}/documents/${documentId}/hero-image`, {
        method: 'POST',
        credentials: 'include',
        headers: token ? { 'Authorization': `Bearer ${token}` } : {},
        body: formData
      });

      if (res.ok) {
        const data = await res.json();
        onUpdate(data.hero_image_url);
        toast.success('Hero image uploaded');
      } else {
        const error = await res.json();
        throw new Error(error.detail || 'Upload failed');
      }
    } catch (error) {
      toast.error(error.message || 'Failed to upload hero image');
    } finally {
      setUploading(false);
    }
  };

  const handleDelete = async () => {
    if (!documentId) return;
    
    try {
      const token = localStorage.getItem('auth_token');
      const res = await fetch(`${API}/documents/${documentId}/hero-image`, {
        method: 'DELETE',
        credentials: 'include',
        headers: token ? { 'Authorization': `Bearer ${token}` } : {},
      });

      if (res.ok) {
        onUpdate(null);
        toast.success('Hero image removed');
      }
    } catch (error) {
      toast.error('Failed to remove hero image');
    }
  };

  return (
    <div className="space-y-2">
      <Label>Hero Image (Optional)</Label>
      <p className="text-xs text-muted-foreground">
        Banner image shown on the buyer's timeline card
      </p>
      {heroImageUrl ? (
        <div className="relative group">
          <img
            src={`${API.replace('/api', '')}${heroImageUrl}`}
            alt="Hero"
            className="w-full h-32 object-cover rounded-lg border border-border"
          />
          <div className="absolute inset-0 bg-black/50 opacity-0 group-hover:opacity-100 transition-opacity rounded-lg flex items-center justify-center gap-2">
            <label className="cursor-pointer">
              <input
                type="file"
                accept="image/jpeg,image/jpg,image/png,image/webp"
                onChange={handleUpload}
                className="hidden"
                disabled={uploading}
              />
              <Button variant="secondary" size="sm" asChild disabled={uploading}>
                <span>
                  {uploading ? <Loader2 className="w-4 h-4 animate-spin" /> : 'Replace'}
                </span>
              </Button>
            </label>
            <Button variant="destructive" size="sm" onClick={handleDelete}>
              <X className="w-4 h-4 mr-1" /> Remove
            </Button>
          </div>
        </div>
      ) : (
        <label className="cursor-pointer">
          <input
            type="file"
            accept="image/jpeg,image/jpg,image/png,image/webp"
            onChange={handleUpload}
            className="hidden"
            disabled={uploading}
          />
          <div className={cn(
            "border-2 border-dashed rounded-lg p-4 text-center transition-colors hover:border-primary hover:bg-primary/5",
            uploading ? "border-primary bg-primary/5" : "border-border"
          )}>
            {uploading ? (
              <div className="flex items-center justify-center gap-2">
                <Loader2 className="w-5 h-5 animate-spin text-primary" />
                <span className="text-sm text-muted-foreground">Uploading...</span>
              </div>
            ) : (
              <>
                <ImageIcon className="w-6 h-6 text-muted-foreground mx-auto mb-1" />
                <p className="text-xs text-muted-foreground">Click to upload image</p>
              </>
            )}
          </div>
        </label>
      )}
    </div>
  );
};

// Extraction Status Banner
export const ExtractionStatus = ({ hasWarning, confidence, documentId }) => {
  return (
    <Card className={cn(
      hasWarning ? "border-amber-500/50 bg-amber-500/5" : "border-emerald-500/50 bg-emerald-500/5"
    )}>
      <CardContent className="py-4">
        <div className="flex items-center gap-3">
          {hasWarning ? (
            <AlertTriangle className="w-5 h-5 text-amber-600" />
          ) : (
            <CheckCircle className="w-5 h-5 text-emerald-600" />
          )}
          <div>
            <p className="font-medium text-foreground">
              {hasWarning ? 'Manual Review Required' : 'Extraction Successful'}
            </p>
            <p className="text-sm text-muted-foreground">
              {hasWarning 
                ? 'Price could not be detected. Please enter it manually below.'
                : `Confidence: ${confidence || 'N/A'}`
              }
            </p>
          </div>
          {documentId && (
            <div className="ml-auto">
              <Button
                variant="outline"
                size="sm"
                onClick={() => window.open(`${API}/documents/${documentId}/source-pdf`, '_blank')}
              >
                <Eye className="w-4 h-4 mr-1" />
                View PDF
              </Button>
            </div>
          )}
        </div>
      </CardContent>
    </Card>
  );
};

// Client Selector Component
export const ClientSelector = ({ clients, selectedClient, onSelect, loading }) => {
  if (loading) {
    return (
      <div className="flex items-center justify-center h-20">
        <Loader2 className="w-6 h-6 animate-spin text-primary" />
      </div>
    );
  }

  return (
    <div className="space-y-2">
      <Select value={selectedClient} onValueChange={onSelect}>
        <SelectTrigger className="w-full" data-testid="client-selector">
          <SelectValue placeholder="Choose a client" />
        </SelectTrigger>
        <SelectContent>
          {clients.map(client => (
            <SelectItem key={client.client_id} value={client.client_id}>
              {client.name}
              {(client.project_name || client.unit_reference) && (
                <span className="text-muted-foreground ml-1">
                  ({[client.project_name, client.unit_reference].filter(Boolean).join(' / ')})
                </span>
              )}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>
      {clients.length === 0 && (
        <p className="text-sm text-muted-foreground">
          No clients found. <a href="/agent/clients" className="text-primary hover:underline">Create a client first</a>.
        </p>
      )}
    </div>
  );
};

// Document Form Actions
export const DocumentFormActions = ({ 
  onSaveDraft, 
  onSend, 
  saving, 
  sending, 
  canSend,
  sendLabel = 'Send to Buyer'
}) => {
  return (
    <div className="flex gap-3 pt-4">
      <Button
        variant="outline"
        className="flex-1"
        onClick={onSaveDraft}
        disabled={saving || sending}
        data-testid="save-draft-btn"
      >
        {saving ? (
          <Loader2 className="w-4 h-4 animate-spin" />
        ) : (
          <>
            <Save className="w-4 h-4 mr-2" />
            Save Draft
          </>
        )}
      </Button>
      <Button
        className="flex-1 bg-primary hover:bg-primary/90"
        onClick={onSend}
        disabled={saving || sending || !canSend}
        data-testid="send-btn"
      >
        {sending ? (
          <Loader2 className="w-4 h-4 animate-spin" />
        ) : (
          <>
            <Send className="w-4 h-4 mr-2" />
            {sendLabel}
          </>
        )}
      </Button>
    </div>
  );
};

// Export helper
export { formatCurrency };
