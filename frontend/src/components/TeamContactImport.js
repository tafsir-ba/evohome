import { useState, useCallback } from 'react';
import { 
  Dialog, 
  DialogContent, 
  DialogHeader, 
  DialogTitle,
  DialogDescription,
  DialogFooter 
} from './ui/dialog';
import { Button } from './ui/button';
import { Card, CardContent } from './ui/card';
import { Input } from './ui/input';
import { Label } from './ui/label';
import { Badge } from './ui/badge';
import { Checkbox } from './ui/checkbox';
import { toast } from 'sonner';
import { cn } from '../lib/utils';
import {
  Upload,
  FileText,
  Loader2,
  Users,
  Building2,
  User,
  Mail,
  Phone,
  Globe,
  MapPin,
  Check,
  X,
  Pencil,
  Sparkles,
  AlertCircle
} from 'lucide-react';

const API = process.env.REACT_APP_BACKEND_URL + '/api';

export const TeamContactImport = ({ 
  open, 
  onOpenChange, 
  projectId, 
  onImportComplete 
}) => {
  const [step, setStep] = useState('upload'); // upload, extracting, review, importing
  const [file, setFile] = useState(null);
  const [dragActive, setDragActive] = useState(false);
  const [extractedContacts, setExtractedContacts] = useState([]);
  const [selectedContacts, setSelectedContacts] = useState(new Set());
  const [editingContact, setEditingContact] = useState(null);
  const [error, setError] = useState(null);

  const handleDrag = useCallback((e) => {
    e.preventDefault();
    e.stopPropagation();
    if (e.type === 'dragenter' || e.type === 'dragover') {
      setDragActive(true);
    } else if (e.type === 'dragleave') {
      setDragActive(false);
    }
  }, []);

  const handleDrop = useCallback((e) => {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(false);
    
    const droppedFile = e.dataTransfer.files[0];
    if (droppedFile) {
      validateAndSetFile(droppedFile);
    }
  }, []);

  const validateAndSetFile = (file) => {
    const allowedExtensions = ['.pdf', '.doc', '.docx', '.xls', '.xlsx', '.png', '.jpg', '.jpeg', '.webp'];
    const ext = '.' + file.name.split('.').pop().toLowerCase();
    
    if (!allowedExtensions.includes(ext)) {
      toast.error(`Unsupported file type. Allowed: ${allowedExtensions.join(', ')}`);
      return;
    }
    
    if (file.size > 20 * 1024 * 1024) { // 20MB limit
      toast.error('File too large. Maximum size is 20MB');
      return;
    }
    
    setFile(file);
    setError(null);
  };

  const handleFileSelect = (e) => {
    const selectedFile = e.target.files[0];
    if (selectedFile) {
      validateAndSetFile(selectedFile);
    }
  };

  const handleExtract = async () => {
    if (!file) return;
    
    setStep('extracting');
    setError(null);
    
    const formData = new FormData();
    formData.append('file', file);
    
    try {
      const res = await fetch(`${API}/team/extract-contacts`, {
        method: 'POST',
        credentials: 'include',
        body: formData
      });
      
      if (res.ok) {
        const data = await res.json();
        
        if (data.contacts && data.contacts.length > 0) {
          setExtractedContacts(data.contacts);
          // Select all by default
          setSelectedContacts(new Set(data.contacts.map((_, i) => i)));
          setStep('review');
          toast.success(`Found ${data.contacts.length} contact(s)`);
        } else {
          setError('No contacts could be extracted from this document');
          setStep('upload');
        }
      } else {
        const err = await res.json();
        throw new Error(err.detail || 'Extraction failed');
      }
    } catch (error) {
      console.error('Extraction error:', error);
      setError(error.message || 'Failed to extract contacts');
      setStep('upload');
      toast.error(error.message || 'Failed to extract contacts');
    }
  };

  const handleToggleContact = (index) => {
    const newSelected = new Set(selectedContacts);
    if (newSelected.has(index)) {
      newSelected.delete(index);
    } else {
      newSelected.add(index);
    }
    setSelectedContacts(newSelected);
  };

  const handleToggleAll = () => {
    if (selectedContacts.size === extractedContacts.length) {
      setSelectedContacts(new Set());
    } else {
      setSelectedContacts(new Set(extractedContacts.map((_, i) => i)));
    }
  };

  const handleEditContact = (index) => {
    setEditingContact({
      index,
      ...extractedContacts[index]
    });
  };

  const handleSaveEdit = () => {
    if (editingContact) {
      const newContacts = [...extractedContacts];
      const { index, ...contactData } = editingContact;
      newContacts[index] = contactData;
      setExtractedContacts(newContacts);
      setEditingContact(null);
    }
  };

  const handleImport = async () => {
    const contactsToImport = extractedContacts.filter((_, i) => selectedContacts.has(i));
    
    if (contactsToImport.length === 0) {
      toast.error('Please select at least one contact to import');
      return;
    }
    
    setStep('importing');
    
    try {
      const res = await fetch(`${API}/projects/${projectId}/team/bulk`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
        body: JSON.stringify({ contacts: contactsToImport })
      });
      
      if (res.ok) {
        const result = await res.json();
        toast.success(`Imported ${result.created} contact(s)${result.skipped > 0 ? ` (${result.skipped} duplicates skipped)` : ''}`);
        onImportComplete?.();
        handleClose();
      } else {
        const err = await res.json();
        throw new Error(err.detail || 'Import failed');
      }
    } catch (error) {
      toast.error(error.message || 'Failed to import contacts');
      setStep('review');
    }
  };

  const handleClose = () => {
    setStep('upload');
    setFile(null);
    setExtractedContacts([]);
    setSelectedContacts(new Set());
    setEditingContact(null);
    setError(null);
    onOpenChange(false);
  };

  return (
    <Dialog open={open} onOpenChange={handleClose}>
      <DialogContent className={cn(
        "max-w-2xl",
        step === 'review' && "max-w-3xl"
      )}>
        <DialogHeader>
          <DialogTitle className="font-outfit flex items-center gap-2">
            <Sparkles className="w-5 h-5 text-primary" />
            Import Contacts from Document
          </DialogTitle>
          <DialogDescription>
            {step === 'upload' && 'Upload a document and AI will extract contact information'}
            {step === 'extracting' && 'Analyzing document...'}
            {step === 'review' && 'Review extracted contacts before importing'}
            {step === 'importing' && 'Importing contacts...'}
          </DialogDescription>
        </DialogHeader>

        {/* Upload Step */}
        {step === 'upload' && (
          <div className="space-y-4 py-4">
            <div
              className={cn(
                "border-2 border-dashed rounded-lg p-8 text-center transition-colors",
                dragActive ? "border-primary bg-primary/5" : "border-border",
                file ? "bg-muted/50" : ""
              )}
              onDragEnter={handleDrag}
              onDragOver={handleDrag}
              onDragLeave={handleDrag}
              onDrop={handleDrop}
            >
              {file ? (
                <div className="flex items-center justify-center gap-3">
                  <FileText className="w-10 h-10 text-primary" />
                  <div className="text-left">
                    <p className="font-medium">{file.name}</p>
                    <p className="text-sm text-muted-foreground">
                      {(file.size / 1024 / 1024).toFixed(2)} MB
                    </p>
                  </div>
                  <Button
                    variant="ghost"
                    size="icon"
                    onClick={() => setFile(null)}
                    className="ml-4"
                  >
                    <X className="w-4 h-4" />
                  </Button>
                </div>
              ) : (
                <>
                  <Upload className="w-10 h-10 text-muted-foreground mx-auto mb-3" />
                  <p className="font-medium mb-1">Drop your document here</p>
                  <p className="text-sm text-muted-foreground mb-3">
                    PDF, Word, Excel, or image files
                  </p>
                  <label>
                    <input
                      type="file"
                      accept=".pdf,.doc,.docx,.xls,.xlsx,.png,.jpg,.jpeg,.webp"
                      onChange={handleFileSelect}
                      className="hidden"
                    />
                    <Button variant="outline" asChild>
                      <span>Browse Files</span>
                    </Button>
                  </label>
                </>
              )}
            </div>
            
            {error && (
              <div className="flex items-center gap-2 p-3 bg-destructive/10 text-destructive rounded-lg">
                <AlertCircle className="w-4 h-4 flex-shrink-0" />
                <p className="text-sm">{error}</p>
              </div>
            )}
          </div>
        )}

        {/* Extracting Step */}
        {step === 'extracting' && (
          <div className="py-12 text-center">
            <Loader2 className="w-12 h-12 animate-spin text-primary mx-auto mb-4" />
            <p className="text-muted-foreground">
              AI is analyzing your document...
            </p>
            <p className="text-sm text-muted-foreground mt-1">
              This may take a few seconds
            </p>
          </div>
        )}

        {/* Review Step */}
        {step === 'review' && !editingContact && (
          <div className="space-y-4 py-4">
            <div className="flex items-center justify-between">
              <p className="text-sm text-muted-foreground">
                {selectedContacts.size} of {extractedContacts.length} selected
              </p>
              <Button variant="ghost" size="sm" onClick={handleToggleAll}>
                {selectedContacts.size === extractedContacts.length ? 'Deselect All' : 'Select All'}
              </Button>
            </div>
            
            <div className="max-h-[400px] overflow-y-auto space-y-2 pr-2">
              {extractedContacts.map((contact, index) => (
                <Card 
                  key={index}
                  className={cn(
                    "border cursor-pointer transition-all",
                    selectedContacts.has(index) 
                      ? "border-primary/50 bg-primary/5" 
                      : "border-border hover:border-muted-foreground/50"
                  )}
                  data-testid={`extracted-contact-${index}`}
                >
                  <CardContent className="py-3 px-4">
                    <div className="flex items-start gap-3">
                      <Checkbox
                        checked={selectedContacts.has(index)}
                        onCheckedChange={() => handleToggleContact(index)}
                        className="mt-1"
                      />
                      <div className="flex-1 min-w-0" onClick={() => handleToggleContact(index)}>
                        <div className="flex items-start justify-between">
                          <div>
                            <h4 className="font-medium flex items-center gap-2">
                              <Building2 className="w-4 h-4 text-muted-foreground" />
                              {contact.company_name || contact.contact_name || 'Unknown'}
                            </h4>
                            {contact.contact_name && contact.company_name && (
                              <p className="text-sm text-muted-foreground flex items-center gap-2">
                                <User className="w-3 h-3" />
                                {contact.contact_name}
                              </p>
                            )}
                            {contact.role && (
                              <Badge variant="secondary" className="mt-1 text-xs">
                                {contact.role}
                              </Badge>
                            )}
                          </div>
                          <Button
                            variant="ghost"
                            size="icon"
                            className="h-8 w-8"
                            onClick={(e) => {
                              e.stopPropagation();
                              handleEditContact(index);
                            }}
                          >
                            <Pencil className="w-4 h-4" />
                          </Button>
                        </div>
                        <div className="flex flex-wrap gap-x-4 gap-y-1 mt-2 text-xs text-muted-foreground">
                          {contact.email && (
                            <span className="flex items-center gap-1">
                              <Mail className="w-3 h-3" />
                              {contact.email}
                            </span>
                          )}
                          {contact.phone && (
                            <span className="flex items-center gap-1">
                              <Phone className="w-3 h-3" />
                              {contact.phone}
                            </span>
                          )}
                          {contact.website && (
                            <span className="flex items-center gap-1">
                              <Globe className="w-3 h-3" />
                              {contact.website}
                            </span>
                          )}
                          {contact.address && (
                            <span className="flex items-center gap-1">
                              <MapPin className="w-3 h-3" />
                              {contact.address}
                            </span>
                          )}
                        </div>
                      </div>
                    </div>
                  </CardContent>
                </Card>
              ))}
            </div>
          </div>
        )}

        {/* Edit Contact Form */}
        {step === 'review' && editingContact && (
          <div className="space-y-4 py-4">
            <div className="flex items-center justify-between mb-4">
              <h3 className="font-medium">Edit Contact</h3>
              <Button variant="ghost" size="sm" onClick={() => setEditingContact(null)}>
                Cancel
              </Button>
            </div>
            
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label>Company Name</Label>
                <Input
                  value={editingContact.company_name || ''}
                  onChange={(e) => setEditingContact({
                    ...editingContact,
                    company_name: e.target.value
                  })}
                />
              </div>
              <div className="space-y-2">
                <Label>Contact Name</Label>
                <Input
                  value={editingContact.contact_name || ''}
                  onChange={(e) => setEditingContact({
                    ...editingContact,
                    contact_name: e.target.value
                  })}
                />
              </div>
              <div className="space-y-2">
                <Label>Role</Label>
                <Input
                  value={editingContact.role || ''}
                  onChange={(e) => setEditingContact({
                    ...editingContact,
                    role: e.target.value
                  })}
                />
              </div>
              <div className="space-y-2">
                <Label>Email</Label>
                <Input
                  type="email"
                  value={editingContact.email || ''}
                  onChange={(e) => setEditingContact({
                    ...editingContact,
                    email: e.target.value
                  })}
                />
              </div>
              <div className="space-y-2">
                <Label>Phone</Label>
                <Input
                  value={editingContact.phone || ''}
                  onChange={(e) => setEditingContact({
                    ...editingContact,
                    phone: e.target.value
                  })}
                />
              </div>
              <div className="space-y-2">
                <Label>Website</Label>
                <Input
                  value={editingContact.website || ''}
                  onChange={(e) => setEditingContact({
                    ...editingContact,
                    website: e.target.value
                  })}
                />
              </div>
              <div className="col-span-2 space-y-2">
                <Label>Address</Label>
                <Input
                  value={editingContact.address || ''}
                  onChange={(e) => setEditingContact({
                    ...editingContact,
                    address: e.target.value
                  })}
                />
              </div>
            </div>
            
            <div className="flex justify-end">
              <Button onClick={handleSaveEdit}>
                <Check className="w-4 h-4 mr-2" />
                Save Changes
              </Button>
            </div>
          </div>
        )}

        {/* Importing Step */}
        {step === 'importing' && (
          <div className="py-12 text-center">
            <Loader2 className="w-12 h-12 animate-spin text-primary mx-auto mb-4" />
            <p className="text-muted-foreground">
              Importing contacts to Team Directory...
            </p>
          </div>
        )}

        <DialogFooter>
          {step === 'upload' && (
            <>
              <Button variant="outline" onClick={handleClose}>
                Cancel
              </Button>
              <Button onClick={handleExtract} disabled={!file}>
                <Sparkles className="w-4 h-4 mr-2" />
                Extract Contacts
              </Button>
            </>
          )}
          
          {step === 'review' && !editingContact && (
            <>
              <Button variant="outline" onClick={() => setStep('upload')}>
                Upload Different File
              </Button>
              <Button 
                onClick={handleImport} 
                disabled={selectedContacts.size === 0}
              >
                <Users className="w-4 h-4 mr-2" />
                Import {selectedContacts.size} Contact{selectedContacts.size !== 1 ? 's' : ''}
              </Button>
            </>
          )}
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
};

export default TeamContactImport;
