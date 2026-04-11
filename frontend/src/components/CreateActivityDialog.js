import { useState } from 'react';
import { Button } from './ui/button';
import { Input } from './ui/input';
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

const TYPE_CONFIG = {
  message: { icon: MessageSquare, label: 'Message', color: 'bg-blue-500' },
  image: { icon: ImageIcon, label: 'Image', color: 'bg-emerald-500' },
  file: { icon: FileText, label: 'Document', color: 'bg-purple-500' },
  status: { icon: Bell, label: 'Status Update', color: 'bg-amber-500' },
};

export const CreateActivityDialog = ({
  open,
  onOpenChange,
  projects,
  clients,
  onCreated,
}) => {
  const [formData, setFormData] = useState({
    type: 'message',
    title: '',
    content: '',
    project_id: '',
    unit_id: '',
    client_ids: [],
  });
  const [files, setFiles] = useState([]);
  const [creating, setCreating] = useState(false);
  const [dragActive, setDragActive] = useState(false);

  const projectClients = clients.filter(
    (c) => !formData.project_id || c.project_id === formData.project_id
  );

  const handleCreate = async () => {
    if (!formData.project_id) {
      toast.error('Please select a project');
      return;
    }
    if (formData.client_ids.length === 0) {
      toast.error('Please select at least one recipient');
      return;
    }
    if (formData.type === 'message' && !formData.content) {
      toast.error('Please enter a message');
      return;
    }
    if ((formData.type === 'image' || formData.type === 'file') && files.length === 0) {
      toast.error(`Please upload ${formData.type === 'image' ? 'an image' : 'a file'}`);
      return;
    }

    setCreating(true);
    try {
      const filesToUpload = files.length > 0 ? files : [null];

      for (let i = 0; i < filesToUpload.length; i++) {
        const currentFile = filesToUpload[i];
        const form = new FormData();
        form.append('type', formData.type);
        form.append('project_id', formData.project_id);
        form.append('client_ids', formData.client_ids.join(','));

        if (formData.title && (i === 0 || filesToUpload.length === 1)) {
          form.append('title', formData.title);
        }
        if (formData.content && (i === 0 || filesToUpload.length === 1)) {
          form.append('content', formData.content);
        }
        if (formData.unit_id) form.append('unit_id', formData.unit_id);
        if (currentFile) form.append('file', currentFile);

        const token = localStorage.getItem('auth_token');
        const res = await fetch(`${API}/activities`, {
          method: 'POST',
          credentials: 'include',
          headers: token ? { Authorization: `Bearer ${token}` } : {},
          body: form,
        });

        if (!res.ok) {
          const error = await res.json();
          throw new Error(error.detail || 'Failed to create activity');
        }
      }

      toast.success(files.length > 1 ? `${files.length} images posted` : 'Activity posted');
      onOpenChange(false);
      setFormData({ type: 'message', title: '', content: '', project_id: '', unit_id: '', client_ids: [] });
      setFiles([]);
      if (onCreated) onCreated();
    } catch (error) {
      toast.error(error.message);
    } finally {
      setCreating(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-lg max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle>New Activity Post</DialogTitle>
          <DialogDescription>
            Send an update, document, or status to your clients.
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-4 py-4">
          {/* Type selection */}
          <div className="space-y-2">
            <Label>Post Type</Label>
            <div className="grid grid-cols-4 gap-2">
              {Object.entries(TYPE_CONFIG).map(([type, cfg]) => {
                const TypeIcon = cfg.icon;
                return (
                  <button
                    key={type}
                    onClick={() => setFormData((prev) => ({ ...prev, type }))}
                    className={cn(
                      'flex flex-col items-center gap-1 p-3 rounded-lg border transition-all',
                      formData.type === type
                        ? 'border-primary bg-primary/5'
                        : 'border-border hover:border-primary/30'
                    )}
                    data-testid={`type-btn-${type}`}
                  >
                    <TypeIcon
                      className={cn(
                        'w-5 h-5',
                        formData.type === type ? 'text-primary' : 'text-muted-foreground'
                      )}
                    />
                    <span className="text-xs">{cfg.label}</span>
                  </button>
                );
              })}
            </div>
          </div>

          {/* Project selection */}
          <div className="space-y-2">
            <Label>Project *</Label>
            <Select
              value={formData.project_id}
              onValueChange={(v) =>
                setFormData((prev) => ({ ...prev, project_id: v, client_ids: [] }))
              }
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

          {/* Recipients */}
          {formData.project_id && (
            <div className="space-y-2">
              <Label>Recipients *</Label>
              <div className="border border-border rounded-lg p-3 max-h-40 overflow-y-auto space-y-2">
                {projectClients.length === 0 ? (
                  <p className="text-sm text-muted-foreground">No clients in this project</p>
                ) : (
                  <>
                    <div className="flex items-center space-x-2 pb-2 border-b border-border">
                      <Checkbox
                        checked={formData.client_ids.length === projectClients.length}
                        onCheckedChange={(checked) => {
                          setFormData((prev) => ({
                            ...prev,
                            client_ids: checked ? projectClients.map((c) => c.client_id) : [],
                          }));
                        }}
                        data-testid="select-all-clients"
                      />
                      <label className="text-sm font-medium">
                        Select all ({projectClients.length})
                      </label>
                    </div>
                    {projectClients.map((client) => (
                      <div key={client.client_id} className="flex items-center space-x-2">
                        <Checkbox
                          checked={formData.client_ids.includes(client.client_id)}
                          onCheckedChange={(checked) => {
                            setFormData((prev) => ({
                              ...prev,
                              client_ids: checked
                                ? [...prev.client_ids, client.client_id]
                                : prev.client_ids.filter((id) => id !== client.client_id),
                            }));
                          }}
                          data-testid={`client-checkbox-${client.client_id}`}
                        />
                        <label className="text-sm">
                          {client.name}
                          {client.unit_reference && (
                            <span className="text-muted-foreground ml-1">
                              ({client.unit_reference})
                            </span>
                          )}
                        </label>
                      </div>
                    ))}
                  </>
                )}
              </div>
            </div>
          )}

          {/* Title */}
          <div className="space-y-2">
            <Label htmlFor="title">Title</Label>
            <Input
              id="title"
              value={formData.title}
              onChange={(e) => setFormData((prev) => ({ ...prev, title: e.target.value }))}
              placeholder="Optional title for this post"
              data-testid="activity-title-input"
            />
          </div>

          {/* Content */}
          <div className="space-y-2">
            <Label htmlFor="content">
              {formData.type === 'message' || formData.type === 'status' ? 'Message *' : 'Description'}
            </Label>
            <Textarea
              id="content"
              value={formData.content}
              onChange={(e) => setFormData((prev) => ({ ...prev, content: e.target.value }))}
              placeholder={
                formData.type === 'image'
                  ? 'Optional description for the image...'
                  : formData.type === 'file'
                  ? 'Optional description for the document...'
                  : 'Write your message...'
              }
              rows={4}
              data-testid="activity-content-input"
            />
          </div>

          {/* File upload with drag-and-drop */}
          {(formData.type === 'image' || formData.type === 'file') && (
            <div className="space-y-2">
              <Label>{formData.type === 'image' ? 'Images *' : 'Document *'}</Label>
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
                onDrop={(e) => {
                  e.preventDefault();
                  e.stopPropagation();
                  setDragActive(false);
                  const droppedFiles = Array.from(e.dataTransfer.files);
                  if (formData.type === 'image') {
                    const imageFiles = droppedFiles.filter((f) => f.type.startsWith('image/'));
                    if (imageFiles.length > 0) {
                      setFiles((prev) => [...prev, ...imageFiles]);
                    } else {
                      toast.error('Please drop image files only');
                    }
                  } else {
                    if (droppedFiles.length > 0) setFiles([droppedFiles[0]]);
                  }
                }}
                data-testid="file-drop-zone"
              >
                {files.length > 0 ? (
                  <div className="space-y-3">
                    {formData.type === 'image' && (
                      <div className="grid grid-cols-3 gap-2">
                        {files.map((f, idx) => (
                          <div key={f.name + idx} className="relative group aspect-square">
                            <img
                              src={URL.createObjectURL(f)}
                              alt={f.name}
                              className="w-full h-full object-cover rounded-lg"
                            />
                            <button
                              type="button"
                              onClick={() => setFiles((prev) => prev.filter((_, i) => i !== idx))}
                              className="absolute -top-2 -right-2 w-6 h-6 bg-destructive text-destructive-foreground rounded-full flex items-center justify-center opacity-0 group-hover:opacity-100 transition-opacity"
                            >
                              <X className="w-3 h-3" />
                            </button>
                          </div>
                        ))}
                      </div>
                    )}
                    {formData.type === 'file' &&
                      files.map((f, idx) => (
                        <div key={f.name} className="flex items-center justify-between p-2 bg-muted rounded-lg">
                          <div className="flex items-center gap-2">
                            <FileText className="w-4 h-4 text-muted-foreground" />
                            <span className="text-sm truncate max-w-[200px]">{f.name}</span>
                          </div>
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => setFiles((prev) => prev.filter((_, i) => i !== idx))}
                          >
                            <X className="w-4 h-4" />
                          </Button>
                        </div>
                      ))}
                    {formData.type === 'image' && (
                      <label className="cursor-pointer">
                        <input
                          type="file"
                          accept="image/*"
                          multiple
                          onChange={(e) => {
                            const newFiles = Array.from(e.target.files || []);
                            setFiles((prev) => [...prev, ...newFiles]);
                            e.target.value = '';
                          }}
                          className="hidden"
                        />
                        <div className="flex items-center justify-center gap-2 p-2 text-sm text-primary hover:text-primary/80">
                          <Plus className="w-4 h-4" />
                          Add more images
                        </div>
                      </label>
                    )}
                  </div>
                ) : (
                  <label className="cursor-pointer block">
                    <input
                      type="file"
                      accept={formData.type === 'image' ? 'image/*' : '.pdf,.doc,.docx,.xls,.xlsx,.ppt,.pptx'}
                      multiple={formData.type === 'image'}
                      onChange={(e) => setFiles(Array.from(e.target.files || []))}
                      className="hidden"
                      data-testid="file-upload-input"
                    />
                    <div className="py-6">
                      {formData.type === 'image' ? (
                        <ImageIcon className="w-10 h-10 text-muted-foreground mx-auto mb-3" />
                      ) : (
                        <FileText className="w-10 h-10 text-muted-foreground mx-auto mb-3" />
                      )}
                      <p className="text-sm font-medium text-foreground">
                        {dragActive
                          ? 'Drop files here'
                          : formData.type === 'image'
                          ? 'Drop images here or click to browse'
                          : 'Drop document here or click to browse'}
                      </p>
                      <p className="text-xs text-muted-foreground mt-1">
                        {formData.type === 'image'
                          ? 'JPG, PNG, GIF, WebP (max 20MB each)'
                          : 'PDF, Word, Excel, or PowerPoint (max 20MB)'}
                      </p>
                    </div>
                  </label>
                )}
              </div>
            </div>
          )}
        </div>

        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)}>
            Cancel
          </Button>
          <Button onClick={handleCreate} disabled={creating} data-testid="submit-activity-btn">
            {creating ? (
              <Loader2 className="w-4 h-4 animate-spin mr-2" />
            ) : (
              <Send className="w-4 h-4 mr-2" />
            )}
            Post
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
};
