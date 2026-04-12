import { useState, useEffect, useCallback, useMemo } from 'react';
import { Button } from './ui/button';
import { Label } from './ui/label';
import { Textarea } from './ui/textarea';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from './ui/select';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from './ui/dialog';
import { Checkbox } from './ui/checkbox';
import { toast } from 'sonner';
import {
  Plus,
  MessageSquare,
  Image as ImageIcon,
  FileText,
  Bell,
  Send,
  Loader2,
  X,
} from 'lucide-react';
import { cn } from '../lib/utils';

const API = process.env.REACT_APP_BACKEND_URL + '/api';
const MAX_BYTES = 20 * 1024 * 1024;

const POST_KIND = {
  message: { icon: MessageSquare, label: 'Message', apiType: 'message' },
  status: { icon: Bell, label: 'Status', apiType: 'status' },
  image: { icon: ImageIcon, label: 'Photos', apiType: 'image' },
  pdf: { icon: FileText, label: 'PDF', apiType: 'pdf' },
};

/**
 * Stable preview URLs for File[] — revoke on change/unmount (never call createObjectURL in render).
 */
function usePreviewUrls(files) {
  const [urls, setUrls] = useState([]);

  useEffect(() => {
    if (!files.length) {
      setUrls([]);
      return;
    }
    const next = files.map((f) => URL.createObjectURL(f));
    setUrls(next);
    return () => {
      next.forEach((u) => URL.revokeObjectURL(u));
    };
  }, [files]);

  return urls;
}

async function postActivityMultipart(payload) {
  const { type, projectId, clientIds, content, unitId, file } = payload;
  const form = new FormData();
  form.append('type', type);
  form.append('project_id', projectId);
  form.append('client_ids', clientIds.join(','));
  if (content) form.append('content', content);
  if (unitId) form.append('unit_id', unitId);
  if (file) form.append('file', file);

  const token = localStorage.getItem('auth_token');
  const res = await fetch(`${API}/activities`, {
    method: 'POST',
    credentials: 'include',
    headers: token ? { Authorization: `Bearer ${token}` } : {},
    body: form,
  });

  if (!res.ok) {
    let detail = 'Failed to create activity';
    try {
      const err = await res.json();
      detail = typeof err.detail === 'string' ? err.detail : JSON.stringify(err.detail || err);
    } catch {
      detail = res.statusText;
    }
    throw new Error(detail);
  }
  return res.json();
}

export const CreateActivityDialog = ({ open, onOpenChange, projects, clients, onCreated }) => {
  const [postKind, setPostKind] = useState('message');
  const [content, setContent] = useState('');
  const [projectId, setProjectId] = useState('');
  const [unitId, setUnitId] = useState('');
  const [clientIds, setClientIds] = useState([]);
  const [photoFiles, setPhotoFiles] = useState([]);
  const [pdfFile, setPdfFile] = useState(null);
  const [creating, setCreating] = useState(false);
  const [dragActive, setDragActive] = useState(false);

  const photoPreviewUrls = usePreviewUrls(photoFiles);

  const projectClients = useMemo(
    () => clients.filter((c) => !projectId || c.project_id === projectId),
    [clients, projectId]
  );

  const resetAttachments = useCallback(() => {
    setPhotoFiles([]);
    setPdfFile(null);
  }, []);

  const handleKindChange = (kind) => {
    setPostKind(kind);
    resetAttachments();
  };

  const validateFiles = (fileList, kind) => {
    for (const f of fileList) {
      if (f.size > MAX_BYTES) {
        toast.error(`${f.name} is over 20 MB`);
        return false;
      }
    }
    if (kind === 'image') {
      for (const f of fileList) {
        if (!f.type.startsWith('image/')) {
          toast.error(`${f.name} is not an image`);
          return false;
        }
      }
    }
    if (kind === 'pdf' && fileList[0] && fileList[0].type !== 'application/pdf') {
      toast.error('Please choose a PDF file');
      return false;
    }
    return true;
  };

  const handleCreate = async () => {
    if (!projectId) {
      toast.error('Please select a project');
      return;
    }
    if (clientIds.length === 0) {
      toast.error('Please select at least one recipient');
      return;
    }

    const base = {
      projectId,
      clientIds,
      unitId: unitId || undefined,
    };

    if (postKind === 'message' || postKind === 'status') {
      if (!content.trim()) {
        toast.error('Please enter a message');
        return;
      }
      setCreating(true);
      try {
        await postActivityMultipart({
          ...base,
          type: POST_KIND[postKind].apiType,
          content: content.trim(),
        });
        toast.success('Posted');
        finish();
      } catch (e) {
        toast.error(e.message);
      } finally {
        setCreating(false);
      }
      return;
    }

    if (postKind === 'image') {
      if (photoFiles.length === 0) {
        toast.error('Add at least one photo');
        return;
      }
      if (!validateFiles(photoFiles, 'image')) return;

      setCreating(true);
      try {
        for (let i = 0; i < photoFiles.length; i++) {
          await postActivityMultipart({
            ...base,
            type: 'image',
            file: photoFiles[i],
            content: i === 0 ? content.trim() || undefined : undefined,
          });
        }
        toast.success(photoFiles.length > 1 ? `${photoFiles.length} photos posted` : 'Posted');
        finish();
      } catch (e) {
        toast.error(e.message);
      } finally {
        setCreating(false);
      }
      return;
    }

    if (postKind === 'pdf') {
      if (!pdfFile) {
        toast.error('Choose a PDF');
        return;
      }
      if (!validateFiles([pdfFile], 'pdf')) return;

      setCreating(true);
      try {
        await postActivityMultipart({
          ...base,
          type: 'pdf',
          file: pdfFile,
          content: content.trim() || undefined,
        });
        toast.success('Posted');
        finish();
      } catch (e) {
        toast.error(e.message);
      } finally {
        setCreating(false);
      }
    }
  };

  const finish = () => {
    onOpenChange(false);
    setPostKind('message');
    setContent('');
    setProjectId('');
    setUnitId('');
    setClientIds([]);
    resetAttachments();
    if (onCreated) onCreated();
  };

  const onDropPhotos = (e) => {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(false);
    const dropped = Array.from(e.dataTransfer.files).filter((f) => f.type.startsWith('image/'));
    if (!dropped.length) {
      toast.error('Drop image files only');
      return;
    }
    if (!validateFiles(dropped, 'image')) return;
    setPhotoFiles((prev) => [...prev, ...dropped]);
  };

  const labelForBody =
    postKind === 'message' || postKind === 'status'
      ? 'Post'
      : postKind === 'image'
      ? 'Caption (optional)'
      : 'Note (optional)';

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-lg max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>New post</DialogTitle>
          <DialogDescription>
            Choose what you’re sending, pick recipients, then add text and optional files.
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-4 py-4">
          <div className="space-y-2">
            <Label>What are you posting?</Label>
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
              {Object.entries(POST_KIND).map(([key, cfg]) => {
                const Icon = cfg.icon;
                return (
                  <button
                    key={key}
                    type="button"
                    onClick={() => handleKindChange(key)}
                    className={cn(
                      'flex flex-col items-center gap-1 p-3 rounded-lg border transition-all',
                      postKind === key ? 'border-primary bg-primary/5' : 'border-border hover:border-primary/30'
                    )}
                    data-testid={`type-btn-${key}`}
                  >
                    <Icon
                      className={cn('w-5 h-5', postKind === key ? 'text-primary' : 'text-muted-foreground')}
                    />
                    <span className="text-xs">{cfg.label}</span>
                  </button>
                );
              })}
            </div>
          </div>

          <div className="space-y-2">
            <Label>Project *</Label>
            <Select
              value={projectId}
              onValueChange={(v) => {
                setProjectId(v);
                setClientIds([]);
              }}
            >
              <SelectTrigger data-testid="project-select">
                <SelectValue placeholder="Select project" />
              </SelectTrigger>
              <SelectContent>
                {projects.map((p) => (
                  <SelectItem key={p.project_id} value={p.project_id}>
                    {p.name}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          {projectId && (
            <div className="space-y-2">
              <Label>Recipients *</Label>
              <div className="border border-border rounded-lg p-3 max-h-40 overflow-y-auto space-y-2">
                {projectClients.length === 0 ? (
                  <p className="text-sm text-muted-foreground">No clients in this project</p>
                ) : (
                  <>
                    <div className="flex items-center space-x-2 pb-2 border-b border-border">
                      <Checkbox
                        checked={clientIds.length === projectClients.length && projectClients.length > 0}
                        onCheckedChange={(checked) => {
                          setClientIds(checked ? projectClients.map((c) => c.client_id) : []);
                        }}
                        data-testid="select-all-clients"
                      />
                      <label className="text-sm font-medium">Select all ({projectClients.length})</label>
                    </div>
                    {projectClients.map((client) => (
                      <div key={client.client_id} className="flex items-center space-x-2">
                        <Checkbox
                          checked={clientIds.includes(client.client_id)}
                          onCheckedChange={(checked) => {
                            setClientIds((prev) =>
                              checked
                                ? [...prev, client.client_id]
                                : prev.filter((id) => id !== client.client_id)
                            );
                          }}
                          data-testid={`client-checkbox-${client.client_id}`}
                        />
                        <label className="text-sm">
                          {client.name}
                          {client.unit_reference && (
                            <span className="text-muted-foreground ml-1">({client.unit_reference})</span>
                          )}
                        </label>
                      </div>
                    ))}
                  </>
                )}
              </div>
            </div>
          )}

          <div className="space-y-2">
            <Label htmlFor="activity-body">{labelForBody}</Label>
            <Textarea
              id="activity-body"
              value={content}
              onChange={(e) => setContent(e.target.value)}
              placeholder="What’s new with the project?"
              rows={postKind === 'image' || postKind === 'pdf' ? 3 : 5}
              data-testid="activity-content-input"
            />
          </div>

          {postKind === 'image' && (
            <div className="space-y-2">
              <Label>Photos *</Label>
              <div
                className={cn(
                  'border-2 border-dashed rounded-lg p-4 text-center transition-colors',
                  dragActive ? 'border-primary bg-primary/5' : 'border-border hover:border-primary/50'
                )}
                onDragOver={(e) => {
                  e.preventDefault();
                  e.stopPropagation();
                  setDragActive(true);
                }}
                onDragLeave={(e) => {
                  e.preventDefault();
                  e.stopPropagation();
                  setDragActive(false);
                }}
                onDrop={onDropPhotos}
                data-testid="file-drop-zone"
              >
                {photoFiles.length > 0 ? (
                  <div className="space-y-3">
                    <div className="grid grid-cols-3 gap-2">
                      {photoFiles.map((f, idx) => (
                        <div key={`${f.name}-${f.size}-${idx}`} className="relative group aspect-square">
                          {photoPreviewUrls[idx] ? (
                          <img
                            src={photoPreviewUrls[idx]}
                            alt=""
                            className="w-full h-full object-cover rounded-lg bg-muted"
                          />
                          ) : (
                            <div className="w-full h-full rounded-lg bg-muted animate-pulse" />
                          )}
                          <button
                            type="button"
                            onClick={() => setPhotoFiles((prev) => prev.filter((_, i) => i !== idx))}
                            className="absolute -top-2 -right-2 w-6 h-6 bg-destructive text-destructive-foreground rounded-full flex items-center justify-center opacity-0 group-hover:opacity-100 transition-opacity"
                            aria-label="Remove"
                          >
                            <X className="w-3 h-3" />
                          </button>
                        </div>
                      ))}
                    </div>
                    <label className="cursor-pointer block">
                      <input
                        type="file"
                        accept="image/*"
                        multiple
                        className="hidden"
                        onChange={(e) => {
                          const added = Array.from(e.target.files || []);
                          e.target.value = '';
                          if (!added.length) return;
                          if (!validateFiles(added, 'image')) return;
                          setPhotoFiles((prev) => [...prev, ...added]);
                        }}
                      />
                      <div className="flex items-center justify-center gap-2 p-2 text-sm text-primary hover:text-primary/80">
                        <Plus className="w-4 h-4" />
                        Add more photos
                      </div>
                    </label>
                  </div>
                ) : (
                  <label className="cursor-pointer block">
                    <input
                      type="file"
                      accept="image/*"
                      multiple
                      className="hidden"
                      data-testid="file-upload-input"
                      onChange={(e) => {
                        const added = Array.from(e.target.files || []);
                        if (!added.length) return;
                        if (!validateFiles(added, 'image')) return;
                        setPhotoFiles(added);
                      }}
                    />
                    <div className="py-6">
                      <ImageIcon className="w-10 h-10 text-muted-foreground mx-auto mb-3" />
                      <p className="text-sm font-medium text-foreground">
                        {dragActive ? 'Drop images here' : 'Drop images here or click to browse'}
                      </p>
                      <p className="text-xs text-muted-foreground mt-1">JPG, PNG, GIF, WebP — max 20 MB each</p>
                    </div>
                  </label>
                )}
              </div>
            </div>
          )}

          {postKind === 'pdf' && (
            <div className="space-y-2">
              <Label>PDF *</Label>
              <div
                className={cn(
                  'border-2 border-dashed rounded-lg p-4 transition-colors',
                  dragActive ? 'border-primary bg-primary/5' : 'border-border'
                )}
                onDragOver={(e) => {
                  e.preventDefault();
                  setDragActive(true);
                }}
                onDragLeave={(e) => {
                  e.preventDefault();
                  setDragActive(false);
                }}
                onDrop={(e) => {
                  e.preventDefault();
                  setDragActive(false);
                  const f = e.dataTransfer.files?.[0];
                  if (f && f.type === 'application/pdf') {
                    if (!validateFiles([f], 'pdf')) return;
                    setPdfFile(f);
                  } else {
                    toast.error('Please drop a PDF file');
                  }
                }}
              >
                {pdfFile ? (
                  <div className="flex items-center justify-between p-2 bg-muted rounded-lg gap-2">
                    <div className="flex items-center gap-2 min-w-0">
                      <FileText className="w-4 h-4 text-muted-foreground flex-shrink-0" />
                      <span className="text-sm truncate">{pdfFile.name}</span>
                    </div>
                    <Button type="button" variant="ghost" size="sm" onClick={() => setPdfFile(null)}>
                      <X className="w-4 h-4" />
                    </Button>
                  </div>
                ) : (
                  <label className="cursor-pointer block text-center py-6">
                    <input
                      type="file"
                      accept="application/pdf"
                      className="hidden"
                      data-testid="file-upload-input"
                      onChange={(e) => {
                        const f = e.target.files?.[0];
                        e.target.value = '';
                        if (!f) return;
                        if (!validateFiles([f], 'pdf')) return;
                        setPdfFile(f);
                      }}
                    />
                    <FileText className="w-10 h-10 text-muted-foreground mx-auto mb-3" />
                    <p className="text-sm font-medium">PDF only (max 20 MB)</p>
                    <p className="text-xs text-muted-foreground mt-1">Matches server — Word/Excel not accepted yet</p>
                  </label>
                )}
              </div>
            </div>
          )}
        </div>

        <DialogFooter>
          <Button type="button" variant="outline" onClick={() => onOpenChange(false)}>
            Cancel
          </Button>
          <Button type="button" onClick={handleCreate} disabled={creating} data-testid="submit-activity-btn">
            {creating ? <Loader2 className="w-4 h-4 animate-spin mr-2" /> : <Send className="w-4 h-4 mr-2" />}
            Post
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
};
