import { useState, useEffect } from 'react';
import { AgentLayout } from '../../components/AgentLayout';
import { useSettings } from '../../context/SettingsContext';
import { useDataContext } from '../../context/DataContext';
import { Card, CardContent, CardHeader, CardTitle } from '../../components/ui/card';
import { Button } from '../../components/ui/button';
import { Input } from '../../components/ui/input';
import { Label } from '../../components/ui/label';
import { Badge } from '../../components/ui/badge';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter } from '../../components/ui/dialog';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../../components/ui/select';
import { toast } from 'sonner';
import { FileDropZone } from '../../components/FileDropZone';
import { PdfViewer } from '../../components/PdfViewer';
import { authFetch } from '../../lib/api';
import {
  FolderArchive, Upload, FileText, FileImage, FileSpreadsheet,
  Trash2, Download, Eye, Pencil, Loader2, Search, Filter,
  Lock, Unlock, Building2, X
} from 'lucide-react';
import { cn } from '../../lib/utils';

const BASE_URL = process.env.REACT_APP_BACKEND_URL;
const API = BASE_URL + '/api';

const CATEGORIES = ['contracts', 'plans', 'permits', 'reports', 'other'];
const CATEGORY_LABELS = {
  contracts: 'Contracts', plans: 'Plans', permits: 'Permits',
  reports: 'Reports', other: 'Other',
};

const getCategoryIcon = (category) => {
  switch (category) {
    case 'contracts': return FileText;
    case 'plans': return FileImage;
    case 'reports': return FileSpreadsheet;
    default: return FileText;
  }
};

const getFileIcon = (contentType) => {
  if (contentType?.includes('pdf')) return FileText;
  if (contentType?.startsWith('image/')) return FileImage;
  if (contentType?.includes('spreadsheet') || contentType?.includes('excel')) return FileSpreadsheet;
  return FileText;
};

const formatFileSize = (bytes) => {
  if (!bytes) return '0 B';
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
};

export const AgentVault = () => {
  const { t } = useSettings();
  const { projects } = useDataContext();

  const [loading, setLoading] = useState(true);
  const [documents, setDocuments] = useState([]);
  const [clients, setClients] = useState([]);
  const [selectedCategory, setSelectedCategory] = useState('all');
  const [searchQuery, setSearchQuery] = useState('');

  // Upload modal
  const [uploadModalOpen, setUploadModalOpen] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [uploadProgress, setUploadProgress] = useState(0);
  const [uploadFile, setUploadFile] = useState(null);
  const [uploadForm, setUploadForm] = useState({
    title: '',
    category: 'other',
    project_id: 'none',
    description: '',
    access_level: 'private',
    client_ids: [],
    doc_type: 'general',
  });

  // Delete
  const [deleteDoc, setDeleteDoc] = useState(null);

  // Preview
  const [previewDoc, setPreviewDoc] = useState(null);

  // Edit
  const [editDoc, setEditDoc] = useState(null);
  const [editForm, setEditForm] = useState({});
  const [savingEdit, setSavingEdit] = useState(false);

  useEffect(() => { fetchVaultData(); }, []);

  const fetchVaultData = async () => {
    try {
      const [docsRes, clientsRes] = await Promise.all([
        authFetch(`${API}/vault/documents`),
        authFetch(`${API}/clients`),
      ]);
      if (docsRes.ok) setDocuments(await docsRes.json());
      if (clientsRes.ok) setClients(await clientsRes.json());
    } catch (error) {
      console.error('Failed to fetch vault data:', error);
      toast.error('Failed to load documents');
    } finally {
      setLoading(false);
    }
  };

  const handleFileSelect = (file) => {
    setUploadFile(file);
    if (file && !uploadForm.title) {
      setUploadForm(prev => ({ ...prev, title: file.name.replace(/\.[^/.]+$/, '') }));
    }
  };

  const handleProjectChange = (projectId) => {
    const clientsInProject = projectId && projectId !== 'none'
      ? clients.filter(c => c.project_id === projectId).map(c => c.client_id)
      : [];
    setUploadForm(prev => ({
      ...prev,
      project_id: projectId,
      client_ids: prev.access_level === 'shared' ? clientsInProject : [],
    }));
  };

  const selectAllInProject = () => {
    const projectId = uploadForm.project_id;
    if (!projectId || projectId === 'none') {
      setUploadForm(prev => ({ ...prev, client_ids: clients.map(c => c.client_id) }));
    } else {
      const ids = clients.filter(c => c.project_id === projectId).map(c => c.client_id);
      setUploadForm(prev => ({ ...prev, client_ids: ids }));
    }
  };

  const handleUpload = async () => {
    if (!uploadFile) { toast.error('Please select a file'); return; }
    if (!uploadForm.title.trim()) { toast.error('Please enter a document name'); return; }
    if (uploadForm.access_level === 'shared' && uploadForm.client_ids.length === 0) {
      toast.error('Please select at least one client to share with'); return;
    }

    setUploading(true);
    setUploadProgress(0);

    try {
      const formData = new FormData();
      formData.append('file', uploadFile);
      formData.append('title', uploadForm.title);
      formData.append('category', uploadForm.category);
      formData.append('project_id', uploadForm.project_id === 'none' ? '' : (uploadForm.project_id || ''));
      formData.append('description', uploadForm.description || '');
      formData.append('access_level', uploadForm.access_level);
      formData.append('doc_type', uploadForm.doc_type || 'general');
      formData.append('client_ids', uploadForm.access_level === 'shared' ? uploadForm.client_ids.join(',') : '');

      const xhr = new XMLHttpRequest();
      const uploadPromise = new Promise((resolve, reject) => {
        xhr.upload.addEventListener('progress', (e) => {
          if (e.lengthComputable) setUploadProgress(Math.round((e.loaded / e.total) * 100));
        });
        xhr.addEventListener('load', () => {
          if (xhr.status >= 200 && xhr.status < 300) {
            resolve(JSON.parse(xhr.responseText));
          } else {
            try {
              const err = JSON.parse(xhr.responseText);
              const detail = err.detail;
              const msg = typeof detail === 'object' && detail.message
                ? detail.message
                : Array.isArray(detail)
                  ? detail.map(e => e.msg).join(', ')
                  : (typeof detail === 'string' ? detail : 'Upload failed');
              reject(new Error(msg));
            } catch { reject(new Error('Upload failed')); }
          }
        });
        xhr.addEventListener('error', () => reject(new Error('Network error during upload')));
        xhr.open('POST', `${API}/vault/upload`);
        xhr.withCredentials = true;
        const token = localStorage.getItem('auth_token');
        if (token) xhr.setRequestHeader('Authorization', `Bearer ${token}`);
        xhr.send(formData);
      });

      const newDoc = await uploadPromise;
      setDocuments(prev => [newDoc, ...prev]);
      setUploadModalOpen(false);
      resetUploadForm();
      toast.success('Document uploaded successfully');
    } catch (error) {
      toast.error(error.message || 'Upload failed');
    } finally {
      setUploading(false);
      setUploadProgress(0);
    }
  };

  const resetUploadForm = () => {
    setUploadFile(null);
    setUploadForm({
      title: '', category: 'other', project_id: 'none', description: '',
      access_level: 'private', client_ids: [], doc_type: 'general',
    });
  };

  const confirmDelete = async () => {
    if (!deleteDoc) return;
    try {
      const res = await authFetch(`${API}/vault/documents/${deleteDoc.vault_document_id}`, { method: 'DELETE' });
      if (res.ok) {
        setDocuments(prev => prev.filter(d => d.vault_document_id !== deleteDoc.vault_document_id));
        toast.success('Document deleted');
      } else { throw new Error('Failed to delete'); }
    } catch (error) {
      toast.error(error.message || 'Failed to delete document');
    } finally { setDeleteDoc(null); }
  };

  const openEdit = (doc) => {
    setEditDoc(doc);
    setEditForm({
      title: doc.title,
      category: doc.category,
      project_id: doc.project_id || 'none',
      description: doc.description || '',
      access_level: doc.access_level || 'private',
      client_ids: doc.client_ids || [],
    });
  };

  const handleEditSave = async () => {
    if (editForm.access_level === 'shared' && (!editForm.client_ids || editForm.client_ids.length === 0)) {
      toast.error('Please select at least one client to share with'); return;
    }
    setSavingEdit(true);
    try {
      const body = {
        title: editForm.title,
        category: editForm.category,
        project_id: editForm.project_id === 'none' ? '' : editForm.project_id,
        description: editForm.description,
        access_level: editForm.access_level,
        client_ids: editForm.access_level === 'shared' ? editForm.client_ids : [],
      };
      const res = await authFetch(`${API}/vault/documents/${editDoc.vault_document_id}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      });
      if (res.ok) {
        const updated = await res.json();
        setDocuments(prev => prev.map(d => d.vault_document_id === editDoc.vault_document_id ? updated : d));
        setEditDoc(null);
        toast.success('Document updated');
      } else { throw new Error('Failed to update'); }
    } catch (error) {
      toast.error(error.message);
    } finally { setSavingEdit(false); }
  };

  const handleDownload = async (doc) => {
    try {
      const res = await authFetch(`${API}/vault/documents/${doc.vault_document_id}/download`);
      if (res.ok) {
        const blob = await res.blob();
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = doc.original_filename || doc.title;
        document.body.appendChild(a);
        a.click();
        window.URL.revokeObjectURL(url);
        document.body.removeChild(a);
      } else { toast.error('Download failed'); }
    } catch { toast.error('Download failed'); }
  };

  const handlePreview = async (doc) => {
    if (doc.content_type === 'application/pdf') {
      try {
        const res = await authFetch(`${API}/vault/documents/${doc.vault_document_id}/download`);
        if (res.ok) {
          const blob = await res.blob();
          const blobUrl = window.URL.createObjectURL(blob);
          setPreviewDoc({ ...doc, blobUrl });
        }
      } catch { toast.error('Preview failed'); }
    } else if (doc.content_type?.startsWith('image/')) {
      try {
        const res = await authFetch(`${API}/vault/documents/${doc.vault_document_id}/download`);
        if (res.ok) {
          const blob = await res.blob();
          const blobUrl = window.URL.createObjectURL(blob);
          window.open(blobUrl, '_blank');
        }
      } catch { toast.error('Preview failed'); }
    } else {
      handleDownload(doc);
    }
  };

  const filteredDocs = documents.filter(doc => {
    const matchesCategory = selectedCategory === 'all' || doc.category === selectedCategory;
    const matchesSearch = !searchQuery ||
      (doc.title || '').toLowerCase().includes(searchQuery.toLowerCase()) ||
      (doc.description || '').toLowerCase().includes(searchQuery.toLowerCase());
    return matchesCategory && matchesSearch;
  });

  const groupedDocs = CATEGORIES.reduce((acc, cat) => {
    acc[cat] = filteredDocs.filter(d => d.category === cat);
    return acc;
  }, {});

  const getProjectName = (projectId) => {
    if (!projectId || projectId === 'none') return 'All Projects';
    const project = projects.find(p => p.project_id === projectId);
    return project?.name || 'All Projects';
  };

  const getSharedWithNames = (clientIds) => {
    if (!clientIds || clientIds.length === 0) return [];
    return clientIds.map(cid => {
      const client = clients.find(c => c.client_id === cid);
      return client ? client.name : 'Unknown';
    });
  };

  if (loading) {
    return (
      <AgentLayout>
        <div className="flex items-center justify-center h-64">
          <Loader2 className="w-8 h-8 animate-spin text-muted-foreground" />
        </div>
      </AgentLayout>
    );
  }

  return (
    <AgentLayout>
      <div className="space-y-6">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
          <div>
            <h1 className="text-2xl font-outfit font-semibold">Document Vault</h1>
            <p className="text-muted-foreground">Store and organize critical project documents</p>
          </div>
          <Button onClick={() => setUploadModalOpen(true)} data-testid="upload-vault-doc-btn">
            <Upload className="w-4 h-4 mr-2" />Upload Document
          </Button>
        </div>

        <Card className="border-border">
          <CardContent className="p-4">
            <div className="flex flex-col sm:flex-row gap-4">
              <div className="relative flex-1">
                <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
                <Input placeholder="Search documents..." value={searchQuery} onChange={(e) => setSearchQuery(e.target.value)} className="pl-9" data-testid="vault-search-input" />
              </div>
              <Select value={selectedCategory} onValueChange={setSelectedCategory}>
                <SelectTrigger className="w-[180px]" data-testid="vault-category-filter">
                  <Filter className="w-4 h-4 mr-2" /><SelectValue placeholder="All Categories" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">All Categories</SelectItem>
                  {CATEGORIES.map(cat => (<SelectItem key={cat} value={cat}>{CATEGORY_LABELS[cat]}</SelectItem>))}
                </SelectContent>
              </Select>
            </div>
          </CardContent>
        </Card>

        {selectedCategory === 'all' ? (
          <div className="space-y-6">
            {CATEGORIES.map(category => {
              const categoryDocs = groupedDocs[category];
              if (!categoryDocs || categoryDocs.length === 0) return null;
              const CatIcon = getCategoryIcon(category);
              return (
                <Card key={category} className="border-border">
                  <CardHeader className="pb-3">
                    <CardTitle className="text-lg font-outfit flex items-center gap-2">
                      <CatIcon className="w-5 h-5" />{CATEGORY_LABELS[category]}
                      <Badge variant="secondary" className="ml-2">{categoryDocs.length}</Badge>
                    </CardTitle>
                  </CardHeader>
                  <CardContent>
                    <DocumentGrid documents={categoryDocs} onPreview={handlePreview} onEdit={openEdit} onDelete={setDeleteDoc} onDownload={handleDownload} getProjectName={getProjectName} getSharedWithNames={getSharedWithNames} />
                  </CardContent>
                </Card>
              );
            })}
            {filteredDocs.length === 0 && <EmptyState onUpload={() => setUploadModalOpen(true)} />}
          </div>
        ) : (
          <Card className="border-border">
            <CardHeader className="pb-3">
              <CardTitle className="text-lg font-outfit flex items-center gap-2">
                {(() => { const Icon = getCategoryIcon(selectedCategory); return <Icon className="w-5 h-5" />; })()}
                {CATEGORY_LABELS[selectedCategory]}
                <Badge variant="secondary" className="ml-2">{filteredDocs.length}</Badge>
              </CardTitle>
            </CardHeader>
            <CardContent>
              {filteredDocs.length > 0 ? (
                <DocumentGrid documents={filteredDocs} onPreview={handlePreview} onEdit={openEdit} onDelete={setDeleteDoc} onDownload={handleDownload} getProjectName={getProjectName} getSharedWithNames={getSharedWithNames} />
              ) : (<EmptyState onUpload={() => setUploadModalOpen(true)} category={CATEGORY_LABELS[selectedCategory]} />)}
            </CardContent>
          </Card>
        )}
      </div>

      {/* Upload Modal */}
      <Dialog open={uploadModalOpen} onOpenChange={setUploadModalOpen}>
        <DialogContent className="sm:max-w-lg">
          <DialogHeader>
            <DialogTitle>Upload Document</DialogTitle>
            <DialogDescription>Add a document to your vault</DialogDescription>
          </DialogHeader>
          <div className="space-y-4 py-4">
            <FileDropZone onFileSelect={handleFileSelect} accept="application/pdf,image/*,.xlsx,.xls,.docx,.doc" maxSizeMB={50} placeholder="Drag & drop your document, or click to browse" data-testid="vault-file-drop" />
            {uploadFile && (
              <div className="space-y-4">
                <div className="space-y-2">
                  <Label htmlFor="doc-title">Document Name *</Label>
                  <Input id="doc-title" value={uploadForm.title} onChange={(e) => setUploadForm(prev => ({ ...prev, title: e.target.value }))} placeholder="e.g., Construction Contract" data-testid="vault-doc-name-input" />
                </div>
                <div className="grid grid-cols-2 gap-4">
                  <div className="space-y-2">
                    <Label>Category</Label>
                    <Select value={uploadForm.category} onValueChange={(v) => setUploadForm(prev => ({ ...prev, category: v }))}>
                      <SelectTrigger data-testid="vault-category-select"><SelectValue /></SelectTrigger>
                      <SelectContent>
                        {CATEGORIES.map(cat => (<SelectItem key={cat} value={cat}>{CATEGORY_LABELS[cat]}</SelectItem>))}
                      </SelectContent>
                    </Select>
                  </div>
                  <div className="space-y-2">
                    <Label>Project (Optional)</Label>
                    <Select value={uploadForm.project_id} onValueChange={handleProjectChange}>
                      <SelectTrigger data-testid="vault-project-select"><SelectValue placeholder="All Projects" /></SelectTrigger>
                      <SelectContent>
                        <SelectItem value="none">All Projects</SelectItem>
                        {projects.map(p => (<SelectItem key={p.project_id} value={p.project_id}>{p.name}</SelectItem>))}
                      </SelectContent>
                    </Select>
                  </div>
                </div>
                <div className="space-y-2">
                  <Label>Document Type</Label>
                  <div className="flex gap-2">
                    <Button type="button" variant={uploadForm.doc_type === 'general' ? 'default' : 'outline'} size="sm" onClick={() => setUploadForm(prev => ({ ...prev, doc_type: 'general' }))} className="flex-1">General</Button>
                    <Button type="button" variant={uploadForm.doc_type === 'action_required' ? 'default' : 'outline'} size="sm" onClick={() => setUploadForm(prev => ({ ...prev, doc_type: 'action_required' }))} className="flex-1 text-amber-600 border-amber-300">Action Required</Button>
                  </div>
                </div>
                <div className="space-y-2">
                  <Label htmlFor="doc-desc">Description (Optional)</Label>
                  <Input id="doc-desc" value={uploadForm.description} onChange={(e) => setUploadForm(prev => ({ ...prev, description: e.target.value }))} placeholder="Brief description..." data-testid="vault-doc-desc-input" />
                </div>
                <AccessLevelPicker
                  accessLevel={uploadForm.access_level}
                  clientIds={uploadForm.client_ids}
                  clients={clients}
                  projectId={uploadForm.project_id}
                  onAccessLevelChange={(level) => setUploadForm(prev => ({ ...prev, access_level: level, client_ids: level === 'private' ? [] : prev.client_ids }))}
                  onClientIdsChange={(ids) => setUploadForm(prev => ({ ...prev, client_ids: ids }))}
                  onSelectAll={selectAllInProject}
                />
              </div>
            )}
          </div>
          {uploading && (
            <div className="space-y-2 py-2">
              <div className="flex justify-between text-sm">
                <span className="text-muted-foreground">Uploading...</span>
                <span className="font-medium">{uploadProgress}%</span>
              </div>
              <div className="h-2 bg-muted rounded-full overflow-hidden">
                <div className="h-full bg-primary transition-all duration-300 ease-out" style={{ width: `${uploadProgress}%` }} />
              </div>
            </div>
          )}
          <DialogFooter>
            <Button variant="outline" onClick={() => { setUploadModalOpen(false); resetUploadForm(); }} disabled={uploading}>Cancel</Button>
            <Button onClick={handleUpload} disabled={!uploadFile || !uploadForm.title || uploading} data-testid="vault-upload-submit">
              {uploading ? <Loader2 className="w-4 h-4 animate-spin mr-2" /> : <Upload className="w-4 h-4 mr-2" />}
              {uploading ? 'Uploading...' : 'Upload'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Edit Modal */}
      <Dialog open={!!editDoc} onOpenChange={() => setEditDoc(null)}>
        <DialogContent className="sm:max-w-lg">
          <DialogHeader><DialogTitle>Edit Document</DialogTitle></DialogHeader>
          <div className="space-y-4 py-4">
            <div className="space-y-2">
              <Label>Document Name</Label>
              <Input value={editForm.title || ''} onChange={(e) => setEditForm(prev => ({ ...prev, title: e.target.value }))} data-testid="vault-edit-name-input" />
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label>Category</Label>
                <Select value={editForm.category} onValueChange={(v) => setEditForm(prev => ({ ...prev, category: v }))}>
                  <SelectTrigger><SelectValue /></SelectTrigger>
                  <SelectContent>{CATEGORIES.map(cat => (<SelectItem key={cat} value={cat}>{CATEGORY_LABELS[cat]}</SelectItem>))}</SelectContent>
                </Select>
              </div>
              <div className="space-y-2">
                <Label>Project</Label>
                <Select value={editForm.project_id || 'none'} onValueChange={(v) => setEditForm(prev => ({ ...prev, project_id: v }))}>
                  <SelectTrigger><SelectValue placeholder="All Projects" /></SelectTrigger>
                  <SelectContent>
                    <SelectItem value="none">All Projects</SelectItem>
                    {projects.map(p => (<SelectItem key={p.project_id} value={p.project_id}>{p.name}</SelectItem>))}
                  </SelectContent>
                </Select>
              </div>
            </div>
            <div className="space-y-2">
              <Label>Description</Label>
              <Input value={editForm.description || ''} onChange={(e) => setEditForm(prev => ({ ...prev, description: e.target.value }))} />
            </div>
            <AccessLevelPicker
              accessLevel={editForm.access_level || 'private'}
              clientIds={editForm.client_ids || []}
              clients={clients}
              projectId={editForm.project_id}
              onAccessLevelChange={(level) => setEditForm(prev => ({ ...prev, access_level: level, client_ids: level === 'private' ? [] : prev.client_ids }))}
              onClientIdsChange={(ids) => setEditForm(prev => ({ ...prev, client_ids: ids }))}
              onSelectAll={() => {
                const pid = editForm.project_id;
                const ids = (!pid || pid === 'none') ? clients.map(c => c.client_id) : clients.filter(c => c.project_id === pid).map(c => c.client_id);
                setEditForm(prev => ({ ...prev, client_ids: ids }));
              }}
            />
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setEditDoc(null)}>Cancel</Button>
            <Button onClick={handleEditSave} disabled={savingEdit} data-testid="vault-edit-save">
              {savingEdit ? <Loader2 className="w-4 h-4 animate-spin mr-2" /> : null}Save Changes
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Delete Modal */}
      <Dialog open={!!deleteDoc} onOpenChange={() => setDeleteDoc(null)}>
        <DialogContent className="sm:max-w-md">
          <DialogHeader><DialogTitle>Delete Document</DialogTitle></DialogHeader>
          <div className="py-4">
            <p className="text-muted-foreground">Are you sure you want to delete <span className="font-medium text-foreground">"{deleteDoc?.title}"</span>?</p>
            <p className="text-sm text-destructive mt-2">This action cannot be undone.</p>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setDeleteDoc(null)}>Cancel</Button>
            <Button variant="destructive" onClick={confirmDelete}><Trash2 className="w-4 h-4 mr-2" />Delete</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* PDF Preview */}
      {previewDoc && (
        <PdfViewer url={previewDoc.blobUrl} title={previewDoc.title} onClose={() => { if (previewDoc.blobUrl) window.URL.revokeObjectURL(previewDoc.blobUrl); setPreviewDoc(null); }} />
      )}
    </AgentLayout>
  );
};

// ── Shared Components ──

const AccessLevelPicker = ({ accessLevel, clientIds, clients, projectId, onAccessLevelChange, onClientIdsChange, onSelectAll }) => (
  <div className="space-y-2">
    <Label>Access Level</Label>
    <div className="flex gap-2">
      <Button type="button" variant={accessLevel === 'private' ? 'default' : 'outline'} size="sm" onClick={() => onAccessLevelChange('private')} className="flex-1" data-testid="vault-access-private">
        <Lock className="w-4 h-4 mr-2" />Private
      </Button>
      <Button type="button" variant={accessLevel === 'shared' ? 'default' : 'outline'} size="sm" onClick={() => onAccessLevelChange('shared')} className="flex-1" data-testid="vault-access-shared">
        <Unlock className="w-4 h-4 mr-2" />Share with Buyers
      </Button>
    </div>
    <p className="text-xs text-muted-foreground">{accessLevel === 'private' ? 'Only you can see this document' : 'Select which buyers can view this document'}</p>
    {accessLevel === 'shared' && (
      <div className="mt-3 space-y-2">
        <div className="flex items-center justify-between">
          <Label className="text-sm font-medium">Select Buyers</Label>
          <Button type="button" variant="ghost" size="sm" onClick={onSelectAll} className="text-xs h-7">Select all{projectId !== 'none' ? ' in project' : ''}</Button>
        </div>
        <div className="max-h-40 overflow-y-auto border border-border rounded-lg p-2 space-y-1">
          {clients.length === 0 ? (
            <p className="text-xs text-muted-foreground py-2 text-center">No clients available</p>
          ) : (
            clients.filter(c => !projectId || projectId === 'none' || c.project_id === projectId).map(client => (
              <label key={client.client_id} className="flex items-center gap-2 p-2 rounded hover:bg-muted/50 cursor-pointer">
                <input type="checkbox" checked={clientIds.includes(client.client_id)} onChange={(e) => {
                  onClientIdsChange(e.target.checked ? [...clientIds, client.client_id] : clientIds.filter(id => id !== client.client_id));
                }} className="rounded border-border" />
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-medium truncate">{client.name}</p>
                  <p className="text-xs text-muted-foreground truncate">{client.unit_reference || 'No unit'} &middot; {client.email}</p>
                </div>
              </label>
            ))
          )}
        </div>
        {clientIds.length > 0 && <p className="text-xs text-muted-foreground">Sharing with {clientIds.length} buyer(s)</p>}
      </div>
    )}
  </div>
);

const DocumentGrid = ({ documents, onPreview, onEdit, onDelete, onDownload, getProjectName, getSharedWithNames }) => (
  <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
    {documents.map(doc => {
      const FileIcon = getFileIcon(doc.content_type);
      const isShared = doc.access_level === 'shared';
      const sharedNames = isShared ? getSharedWithNames(doc.client_ids) : [];
      return (
        <div key={doc.vault_document_id} className="group border border-border rounded-lg p-4 hover:border-primary/50 transition-colors bg-card" data-testid={`vault-doc-${doc.vault_document_id}`}>
          <div className="flex items-start gap-3">
            <div className={cn("w-10 h-10 rounded-lg flex items-center justify-center shrink-0",
              doc.doc_type === 'action_required' ? 'bg-amber-100 text-amber-600 dark:bg-amber-900/30 dark:text-amber-400' :
              doc.content_type === 'application/pdf' ? 'bg-red-100 text-red-600 dark:bg-red-900/30 dark:text-red-400' :
              doc.content_type?.startsWith('image/') ? 'bg-blue-100 text-blue-600 dark:bg-blue-900/30 dark:text-blue-400' :
              'bg-muted text-muted-foreground'
            )}>
              <FileIcon className="w-5 h-5" />
            </div>
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-2">
                <h4 className="font-medium text-sm truncate">{doc.title}</h4>
                {doc.doc_type === 'action_required' && <Badge variant="outline" className="text-xs text-amber-600 border-amber-300 shrink-0">Action</Badge>}
              </div>
              {doc.description && <p className="text-xs text-muted-foreground truncate mt-0.5">{doc.description}</p>}
              <div className="flex items-center gap-2 mt-2 text-xs text-muted-foreground">
                <span>{formatFileSize(doc.file_size)}</span><span>&middot;</span>
                <span>{new Date(doc.created_at).toLocaleDateString()}</span>
              </div>
              <div className="flex flex-wrap items-center gap-2 mt-2">
                {doc.project_id && <Badge variant="secondary" className="text-xs"><Building2 className="w-3 h-3 mr-1" />{getProjectName(doc.project_id)}</Badge>}
                {isShared && sharedNames.length > 0 && (
                  <Badge variant="outline" className="text-xs text-blue-600 border-blue-200" title={`Shared with: ${sharedNames.join(', ')}`}>
                    <Unlock className="w-3 h-3 mr-1" />{sharedNames.length === 1 ? sharedNames[0] : `${sharedNames.length} buyers`}
                  </Badge>
                )}
                {!isShared && <Badge variant="outline" className="text-xs text-muted-foreground border-muted"><Lock className="w-3 h-3 mr-1" />Private</Badge>}
              </div>
            </div>
          </div>
          <div className="flex items-center gap-1 mt-3 pt-3 border-t border-border">
            <Button variant="ghost" size="sm" onClick={() => onPreview(doc)} className="flex-1" data-testid={`vault-preview-${doc.vault_document_id}`}><Eye className="w-4 h-4 mr-1" />View</Button>
            <Button variant="ghost" size="sm" onClick={() => onDownload(doc)} className="flex-1"><Download className="w-4 h-4 mr-1" />Download</Button>
            <Button variant="ghost" size="icon" onClick={() => onEdit(doc)} className="h-8 w-8"><Pencil className="w-4 h-4" /></Button>
            <Button variant="ghost" size="icon" onClick={() => onDelete(doc)} className="h-8 w-8 text-destructive hover:text-destructive"><Trash2 className="w-4 h-4" /></Button>
          </div>
        </div>
      );
    })}
  </div>
);

const EmptyState = ({ onUpload, category }) => (
  <div className="text-center py-12">
    <FolderArchive className="w-12 h-12 mx-auto text-muted-foreground/50 mb-4" />
    <h3 className="text-lg font-medium mb-1">No documents {category ? `in ${category}` : 'yet'}</h3>
    <p className="text-muted-foreground mb-4">Upload your first document to get started</p>
    <Button onClick={onUpload} variant="outline"><Upload className="w-4 h-4 mr-2" />Upload Document</Button>
  </div>
);

export default AgentVault;
