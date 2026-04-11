import { useState, useEffect, useCallback } from 'react';
import { useSearchParams, useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { useDataContext } from '../context/DataContext';
import { Card, CardContent, CardHeader } from './ui/card';
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
  User,
  Users,
  Calendar,
  Paperclip,
  Download,
  ChevronDown,
  ChevronUp,
  Reply,
  X,
  Building2,
  MoreVertical,
  Edit2,
  Trash2
} from 'lucide-react';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from './ui/dropdown-menu';
import { cn } from '../lib/utils';

const API = process.env.REACT_APP_BACKEND_URL + '/api';

const TYPE_CONFIG = {
  message: { icon: MessageSquare, label: 'Message', color: 'bg-blue-500' },
  image: { icon: ImageIcon, label: 'Image', color: 'bg-emerald-500' },
  file: { icon: FileText, label: 'Document', color: 'bg-purple-500' },
  pdf: { icon: FileText, label: 'Document', color: 'bg-purple-500' },  // backwards compat
  status: { icon: Bell, label: 'Status Update', color: 'bg-amber-500' }
};

const formatDate = (dateStr) => {
  const date = new Date(dateStr);
  const now = new Date();
  const diffDays = Math.floor((now - date) / (1000 * 60 * 60 * 24));
  
  if (diffDays === 0) return 'Today';
  if (diffDays === 1) return 'Yesterday';
  if (diffDays < 7) return `${diffDays} days ago`;
  return date.toLocaleDateString('en-GB', { day: 'numeric', month: 'short', year: 'numeric' });
};

const isImageFile = (filename) => {
  if (!filename) return false;
  const ext = filename.toLowerCase().split('.').pop();
  return ['jpg', 'jpeg', 'png', 'gif', 'webp', 'bmp', 'svg'].includes(ext);
};

// Helper: get auth headers for fetch calls
const getAuthHeaders = () => {
  const token = localStorage.getItem('auth_token');
  return token ? { 'Authorization': `Bearer ${token}` } : {};
};

const ActivityCard = ({ activity, onReply, onSendDraft, onEdit, onDelete, canReply = true, isAgent = false }) => {
  const [expanded, setExpanded] = useState(false);
  const [showReplyInput, setShowReplyInput] = useState(false);
  const [replyText, setReplyText] = useState('');
  const [replying, setReplying] = useState(false);
  const [sending, setSending] = useState(false);
  const [imageError, setImageError] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [replies, setReplies] = useState(activity.replies || []);
  const [loadingReplies, setLoadingReplies] = useState(false);
  
  const config = TYPE_CONFIG[activity.type] || TYPE_CONFIG.message;
  const Icon = config.icon;
  const isDraft = activity.is_draft;
  
  // Check if the attachment is an image
  const hasImageAttachment = activity.file_name && isImageFile(activity.file_name);
  const imageUrl = hasImageAttachment && activity.file_url 
    ? `${API.replace('/api', '')}${activity.file_url}` 
    : null;
  
  // Lazy-load replies when expanding
  const fetchReplies = async () => {
    if (replies.length > 0 || !activity.reply_count) return;
    setLoadingReplies(true);
    try {
      const res = await fetch(`${API}/activities/${activity.activity_id}`, {
        credentials: 'include',
        headers: getAuthHeaders()
      });
      if (res.ok) {
        const data = await res.json();
        setReplies(data.replies || []);
      }
    } catch (e) {
      console.error('Failed to fetch replies:', e);
    } finally {
      setLoadingReplies(false);
    }
  };

  const handleExpand = () => {
    const next = !expanded;
    setExpanded(next);
    if (next && activity.reply_count > 0 && replies.length === 0) {
      fetchReplies();
    }
  };

  const handleReply = async () => {
    if (!replyText.trim()) return;
    setReplying(true);
    try {
      await onReply(activity.activity_id, replyText);
      setReplyText('');
      setShowReplyInput(false);
      // Refresh replies after sending
      setLoadingReplies(true);
      const res = await fetch(`${API}/activities/${activity.activity_id}`, {
        credentials: 'include',
        headers: getAuthHeaders()
      });
      if (res.ok) {
        const data = await res.json();
        setReplies(data.replies || []);
      }
      setLoadingReplies(false);
    } finally {
      setReplying(false);
    }
  };

  const handleSendDraft = async () => {
    if (!onSendDraft) return;
    setSending(true);
    try {
      await onSendDraft(activity.activity_id);
    } finally {
      setSending(false);
    }
  };

  const handleDelete = async () => {
    if (!onDelete) return;
    setDeleting(true);
    try {
      await onDelete(activity.activity_id);
    } finally {
      setDeleting(false);
    }
  };

  return (
    <Card className={cn(
      "border-border rounded-lg overflow-hidden hover:shadow-md transition-shadow",
      isDraft && "border-amber-500/50 bg-amber-500/5"
    )} data-testid={`activity-card-${activity.activity_id}`}>
      {/* Type indicator */}
      <div className={cn("h-1", isDraft ? "bg-amber-500" : config.color)} />
      
      <CardHeader className="pb-2 px-3 sm:px-6">
        <div className="flex items-start justify-between gap-2 sm:gap-4">
          <div className="flex items-start gap-2 sm:gap-3 min-w-0 flex-1">
            <div className={cn("w-8 h-8 sm:w-10 sm:h-10 rounded-lg flex items-center justify-center flex-shrink-0", config.color + "/10")}>
              <Icon className={cn("w-4 h-4 sm:w-5 sm:h-5", config.color.replace('bg-', 'text-'))} />
            </div>
            <div className="min-w-0 flex-1">
              <div className="flex items-center gap-1 sm:gap-2 flex-wrap">
                {isDraft && (
                  <span className="text-[9px] sm:text-[10px] font-semibold uppercase tracking-wider px-1.5 sm:px-2 py-0.5 rounded-full whitespace-nowrap bg-amber-500/20 text-amber-600">
                    Draft
                  </span>
                )}
                <span className={cn("text-[9px] sm:text-[10px] font-semibold uppercase tracking-wider px-1.5 sm:px-2 py-0.5 rounded-full whitespace-nowrap", config.color + "/10", config.color.replace('bg-', 'text-'))}>
                  {config.label}
                </span>
                {activity.unit_reference && (
                  <span className="text-[9px] sm:text-[10px] text-muted-foreground px-1.5 sm:px-2 py-0.5 rounded-full bg-muted whitespace-nowrap">
                    {activity.unit_reference}
                  </span>
                )}
              </div>
              <h3 className="font-semibold text-foreground mt-1 leading-tight text-sm sm:text-base break-words">
                {activity.title || 'Update'}
              </h3>
              <p className="text-[11px] sm:text-xs text-muted-foreground mt-0.5 truncate">
                {activity.author_name} · {formatDate(activity.created_at)}
              </p>
            </div>
          </div>
          
          {/* Recipients badge and Actions - only for agents */}
          {isAgent && (
            <div className="flex items-center gap-1 flex-shrink-0">
              {!isDraft && activity.recipients && (
                <div className="flex items-center gap-1 text-xs text-muted-foreground mr-1">
                  <Users className="w-3 h-3 sm:w-3.5 sm:h-3.5" />
                  <span>{activity.recipients.length}</span>
                </div>
              )}
              
              {/* Edit/Delete dropdown menu */}
              <DropdownMenu>
                <DropdownMenuTrigger asChild>
                  <Button
                    variant="ghost"
                    size="icon"
                    className="h-8 w-8"
                    data-testid={`activity-menu-${activity.activity_id}`}
                  >
                    <MoreVertical className="w-4 h-4" />
                  </Button>
                </DropdownMenuTrigger>
                <DropdownMenuContent align="end">
                  <DropdownMenuItem
                    onClick={() => onEdit && onEdit(activity)}
                    className="cursor-pointer"
                    data-testid={`edit-activity-${activity.activity_id}`}
                  >
                    <Edit2 className="w-4 h-4 mr-2" />
                    Edit
                  </DropdownMenuItem>
                  <DropdownMenuItem
                    onClick={handleDelete}
                    className="cursor-pointer text-destructive focus:text-destructive"
                    disabled={deleting}
                    data-testid={`delete-activity-${activity.activity_id}`}
                  >
                    {deleting ? (
                      <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                    ) : (
                      <Trash2 className="w-4 h-4 mr-2" />
                    )}
                    Delete
                  </DropdownMenuItem>
                </DropdownMenuContent>
              </DropdownMenu>
            </div>
          )}
          
          {/* Send button for drafts */}
          {isDraft && isAgent && (
            <Button
              size="sm"
              onClick={handleSendDraft}
              disabled={sending}
              className="bg-emerald-600 hover:bg-emerald-700"
            >
              {sending ? (
                <Loader2 className="w-4 h-4 animate-spin" />
              ) : (
                <>
                  <Send className="w-4 h-4 mr-1" />
                  Send
                </>
              )}
            </Button>
          )}
        </div>
      </CardHeader>
      
      <CardContent className="pt-0 px-3 sm:px-6">
        {/* Content preview */}
        {activity.content && (
          <p className={cn(
            "text-xs sm:text-sm text-muted-foreground whitespace-pre-wrap break-words",
            !expanded && "line-clamp-3"
          )}>
            {activity.content}
          </p>
        )}
        
        {/* Image Preview - visual display for image attachments */}
        {hasImageAttachment && imageUrl && !imageError && (
          <div className="mt-3 rounded-lg overflow-hidden bg-muted/30">
            <a 
              href={imageUrl} 
              target="_blank" 
              rel="noopener noreferrer"
              className="block"
              data-testid={`image-preview-${activity.activity_id}`}
            >
              <img 
                src={imageUrl}
                alt={activity.file_name || 'Image attachment'}
                className="w-full max-h-96 object-contain cursor-pointer hover:opacity-90 transition-opacity"
                onError={() => setImageError(true)}
                loading="lazy"
              />
            </a>
            <div className="flex items-center justify-between px-3 py-2 bg-muted/50">
              <span className="text-xs text-muted-foreground truncate">{activity.file_name}</span>
              <Button
                variant="ghost"
                size="sm"
                className="h-7 text-xs"
                asChild
              >
                <a href={imageUrl} download target="_blank" rel="noopener noreferrer">
                  <Download className="w-3 h-3 mr-1" />
                  Download
                </a>
              </Button>
            </div>
          </div>
        )}
        
        {/* File attachment - for non-image files or failed image loads */}
        {activity.file_name && (!hasImageAttachment || imageError) && (
          <div className="mt-3 p-2 sm:p-3 bg-muted rounded-lg flex items-center justify-between gap-2">
            <div className="flex items-center gap-2 min-w-0 flex-1">
              <Paperclip className="w-4 h-4 text-muted-foreground flex-shrink-0" />
              <span className="text-xs sm:text-sm truncate">{activity.file_name}</span>
              {activity.file_size && (
                <span className="text-[10px] sm:text-xs text-muted-foreground flex-shrink-0 hidden sm:inline">
                  ({(activity.file_size / 1024 / 1024).toFixed(1)} MB)
                </span>
              )}
            </div>
            {activity.file_url && (
              <Button
                variant="ghost"
                size="sm"
                className="h-8 flex-shrink-0"
                asChild
                data-testid={`download-file-${activity.activity_id}`}
              >
                <a href={`${API.replace('/api', '')}${activity.file_url}`} download target="_blank" rel="noopener noreferrer">
                  <Download className="w-4 h-4" />
                </a>
              </Button>
            )}
          </div>
        )}
        
        {/* Recipients list - only for agents when expanded */}
        {expanded && isAgent && activity.recipients && activity.recipients.length > 0 && (
          <div className="mt-4 pt-4 border-t border-border">
            <p className="text-xs font-medium text-muted-foreground mb-2">RECIPIENTS</p>
            <div className="flex flex-wrap gap-1">
              {activity.recipients.map(r => (
                <span key={r.client_id} className="text-xs px-2 py-1 bg-muted rounded-full">
                  {r.client_name}
                </span>
              ))}
            </div>
          </div>
        )}
        
        {/* Replies section */}
        {expanded && (replies.length > 0 || loadingReplies) && (
          <div className="mt-4 pt-4 border-t border-border space-y-3">
            <p className="text-xs font-medium text-muted-foreground">
              {loadingReplies ? 'LOADING REPLIES...' : `${replies.length} REPL${replies.length === 1 ? 'Y' : 'IES'}`}
            </p>
            {loadingReplies && (
              <div className="flex items-center gap-2 text-sm text-muted-foreground">
                <Loader2 className="w-4 h-4 animate-spin" />
                Loading replies...
              </div>
            )}
            {replies.map(reply => (
              <div key={reply.reply_id} className="pl-4 border-l-2 border-primary/30">
                <p className="text-sm">{reply.content}</p>
                <p className="text-xs text-muted-foreground mt-1">
                  {reply.author_name} ({reply.author_role}) · {formatDate(reply.created_at)}
                </p>
              </div>
            ))}
          </div>
        )}
        
        {/* Reply input */}
        {showReplyInput && (
          <div className="mt-4 pt-4 border-t border-border space-y-2">
            <Textarea
              value={replyText}
              onChange={(e) => setReplyText(e.target.value)}
              placeholder="Write your reply..."
              rows={2}
              className="resize-none"
              data-testid={`reply-input-${activity.activity_id}`}
            />
            <div className="flex justify-end gap-2">
              <Button variant="outline" size="sm" onClick={() => setShowReplyInput(false)}>
                Cancel
              </Button>
              <Button size="sm" onClick={handleReply} disabled={!replyText.trim() || replying} data-testid={`send-reply-${activity.activity_id}`}>
                {replying ? <Loader2 className="w-4 h-4 animate-spin" /> : 'Send'}
              </Button>
            </div>
          </div>
        )}
        
        {/* Actions */}
        <div className="mt-4 pt-3 border-t border-border flex items-center justify-between">
          <Button
            variant="ghost"
            size="sm"
            className="h-8 text-xs text-muted-foreground"
            onClick={handleExpand}
          >
            {expanded ? (
              <>
                <ChevronUp className="w-4 h-4 mr-1" />
                Less
              </>
            ) : (
              <>
                <ChevronDown className="w-4 h-4 mr-1" />
                More
              </>
            )}
          </Button>
          <div className="flex items-center gap-2">
            {activity.reply_count > 0 && !expanded && (
              <span className="text-xs text-muted-foreground">
                {activity.reply_count} repl{activity.reply_count === 1 ? 'y' : 'ies'}
              </span>
            )}
            {canReply && (
              <Button
                variant="ghost"
                size="sm"
                className="h-8"
                onClick={() => setShowReplyInput(!showReplyInput)}
                data-testid={`reply-btn-${activity.activity_id}`}
              >
                <Reply className="w-4 h-4 mr-1" />
                Reply
              </Button>
            )}
          </div>
        </div>
      </CardContent>
    </Card>
  );
};

/**
 * Shared Feed Component
 * 
 * Single component for both agent and buyer views.
 * - isAgent: determines UI permissions (create post, view all recipients)
 * - Uses same /api/activities endpoint - backend handles role-based filtering
 */
export const Feed = ({ isAgent = false, embedded = false }) => {
  const { user } = useAuth();
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const clientFilter = searchParams.get('client');
  const projectFilter = searchParams.get('project');
  
  // SINGLE SOURCE OF TRUTH: DataContext for projects (agent only)
  const dataContext = useDataContext();
  const projects = isAgent ? dataContext.projects : [];
  
  const [activities, setActivities] = useState([]);
  const [loading, setLoading] = useState(true);
  const [total, setTotal] = useState(0);
  const [offset, setOffset] = useState(0);
  const limit = 20;
  
  const [showCreateDialog, setShowCreateDialog] = useState(false);
  const [clients, setClients] = useState([]);
  const [filterClient, setFilterClient] = useState(null);
  const [filterProject, setFilterProject] = useState(null);
  
  // Create form state (agent only)
  const [formData, setFormData] = useState({
    type: 'message',
    title: '',
    content: '',
    project_id: '',
    unit_id: '',
    client_ids: []
  });
  const [files, setFiles] = useState([]);
  const [creating, setCreating] = useState(false);
  const [dragActive, setDragActive] = useState(false);
  
  // Edit state
  const [editingActivity, setEditingActivity] = useState(null);
  const [editFormData, setEditFormData] = useState({ title: '', content: '' });
  const [saving, setSaving] = useState(false);
  
  // Delete confirmation state  
  const [deleteConfirm, setDeleteConfirm] = useState({ open: false, activity: null });

  const fetchActivities = useCallback(async () => {
    setLoading(true);
    try {
      // Buyer: no filters passed - backend enforces unit_id scope
      // Agent: can pass project/client filters
      let url = `${API}/activities?limit=${limit}&offset=${offset}`;
      if (isAgent && clientFilter) url += `&client_id=${clientFilter}`;
      if (isAgent && projectFilter) url += `&project_id=${projectFilter}`;
      
      const res = await fetch(url, { 
        credentials: 'include',
        headers: getAuthHeaders()
      });
      if (res.ok) {
        const data = await res.json();
        // Activities come pre-enriched from the backend (author, project, recipients)
        // Replies are lazy-loaded on expand to avoid N+1 performance issues
        setActivities(data.activities || []);
        setTotal(data.total);
      } else {
        console.error('Activities fetch failed:', res.status);
      }
    } catch (error) {
      console.error('Failed to fetch activities:', error);
      toast.error('Failed to load feed');
    } finally {
      setLoading(false);
    }
  }, [isAgent, clientFilter, projectFilter, offset]);

  const fetchClients = async () => {
    if (!isAgent) return; // Buyers don't need this metadata
    
    try {
      const clientsRes = await fetch(`${API}/clients`, { 
        credentials: 'include',
        headers: getAuthHeaders()
      });
      
      if (clientsRes.ok) {
        const clientsData = await clientsRes.json();
        setClients(clientsData);
        if (clientFilter) {
          setFilterClient(clientsData.find(c => c.client_id === clientFilter));
        }
      }
    } catch (error) {
      console.error('Failed to fetch clients:', error);
    }
  };

  // Set filter project from URL when projects are loaded
  useEffect(() => {
    if (isAgent && projectFilter && projects.length > 0) {
      setFilterProject(projects.find(p => p.project_id === projectFilter) || null);
    }
  }, [isAgent, projectFilter, projects]);

  useEffect(() => {
    fetchClients();
  }, [isAgent]);

  useEffect(() => {
    fetchActivities();
  }, [fetchActivities]);

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
      // If multiple images, create one activity per image
      const filesToUpload = files.length > 0 ? files : [null];
      
      for (let i = 0; i < filesToUpload.length; i++) {
        const currentFile = filesToUpload[i];
        const form = new FormData();
        form.append('type', formData.type);
        form.append('project_id', formData.project_id);
        form.append('client_ids', formData.client_ids.join(','));
        
        // For multiple images, only include content on the first one
        if (formData.title && (i === 0 || filesToUpload.length === 1)) {
          form.append('title', formData.title);
        }
        if (formData.content && (i === 0 || filesToUpload.length === 1)) {
          form.append('content', formData.content);
        }
        if (formData.unit_id) form.append('unit_id', formData.unit_id);
        if (currentFile) form.append('file', currentFile);

        const res = await fetch(`${API}/activities`, {
          method: 'POST',
          credentials: 'include',
          body: form
        });

        if (!res.ok) {
          const error = await res.json();
          throw new Error(error.detail || 'Failed to create activity');
        }
      }

      toast.success(files.length > 1 ? `${files.length} images posted` : 'Activity posted');
      setShowCreateDialog(false);
      setFormData({ type: 'message', title: '', content: '', project_id: '', unit_id: '', client_ids: [] });
      setFiles([]);
      fetchActivities();
    } catch (error) {
      toast.error(error.message);
    } finally {
      setCreating(false);
    }
  };

  const handleReply = async (activityId, content) => {
    try {
      const res = await fetch(`${API}/activities/${activityId}/reply`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', ...getAuthHeaders() },
        credentials: 'include',
        body: JSON.stringify({ content })
      });

      if (res.ok) {
        toast.success('Reply sent');
        fetchActivities();
      } else {
        const error = await res.json();
        throw new Error(error.detail || 'Failed to send reply');
      }
    } catch (error) {
      toast.error(error.message);
    }
  };

  const handleSendDraft = async (activityId) => {
    try {
      const res = await fetch(`${API}/activities/${activityId}/send`, {
        method: 'POST',
        credentials: 'include'
      });

      if (res.ok) {
        toast.success('Message sent to client');
        fetchActivities();
      } else {
        const error = await res.json();
        throw new Error(error.detail || 'Failed to send message');
      }
    } catch (error) {
      toast.error(error.message);
    }
  };

  const handleEditActivity = (activity) => {
    setEditingActivity(activity);
    setEditFormData({
      title: activity.title || '',
      content: activity.content || ''
    });
  };

  const handleSaveEdit = async () => {
    if (!editingActivity) return;
    
    setSaving(true);
    try {
      const res = await fetch(`${API}/activities/${editingActivity.activity_id}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
        body: JSON.stringify(editFormData)
      });

      if (res.ok) {
        toast.success('Activity updated');
        setEditingActivity(null);
        fetchActivities();
      } else {
        const error = await res.json();
        throw new Error(error.detail || 'Failed to update activity');
      }
    } catch (error) {
      toast.error(error.message);
    } finally {
      setSaving(false);
    }
  };

  const handleDeleteActivity = async (activityId) => {
    try {
      const res = await fetch(`${API}/activities/${activityId}`, {
        method: 'DELETE',
        credentials: 'include'
      });

      if (res.ok) {
        toast.success('Activity deleted');
        setDeleteConfirm({ open: false, activity: null });
        fetchActivities();
      } else {
        const error = await res.json();
        throw new Error(error.detail || 'Failed to delete activity');
      }
    } catch (error) {
      toast.error(error.message);
    }
  };

  const clearFilters = () => {
    navigate('/agent/feed');
    setFilterClient(null);
    setFilterProject(null);
  };

  const projectClients = clients.filter(c => 
    !formData.project_id || c.project_id === formData.project_id
  );

  // Loading state
  if (loading && activities.length === 0) {
    return (
      <div className="animate-pulse space-y-4" data-testid="feed-loading">
        {[1, 2, 3].map(i => (
          <div key={i} className="h-48 bg-muted rounded-lg" />
        ))}
      </div>
    );
  }

  // Empty state
  if (activities.length === 0 && !loading) {
    return (
      <div data-testid="feed-empty">
        {/* Header for agent view */}
        {isAgent && !embedded && (
          <div className="flex items-start justify-between mb-6">
            <div>
              <h1 className="text-3xl font-outfit font-semibold text-foreground tracking-tight">
                Activity Feed
              </h1>
              <p className="text-muted-foreground mt-1">0 activities</p>
            </div>
            <Button 
              className="rounded-lg"
              onClick={() => setShowCreateDialog(true)}
              data-testid="create-activity-btn"
            >
              <Plus className="w-4 h-4 mr-2" />
              New Post
            </Button>
          </div>
        )}
        
        <Card className="border-border rounded-lg">
          <CardContent className="py-12 text-center">
            <MessageSquare className="w-12 h-12 text-muted-foreground/30 mx-auto mb-4" />
            <p className="text-muted-foreground">
              {isAgent ? 'No activities yet' : 'No updates yet'}
            </p>
            <p className="text-sm text-muted-foreground mt-1">
              {isAgent 
                ? 'Create your first post to communicate with clients'
                : 'Your agent will post updates here'
              }
            </p>
            {isAgent && (
              <Button 
                className="mt-4 rounded-lg"
                onClick={() => setShowCreateDialog(true)}
              >
                <Plus className="w-4 h-4 mr-2" />
                Create Post
              </Button>
            )}
          </CardContent>
        </Card>
        
        {/* Create dialog for agent */}
        {isAgent && renderCreateDialog()}
      </div>
    );
  }

  function renderCreateDialog() {
    return (
      <Dialog open={showCreateDialog} onOpenChange={setShowCreateDialog}>
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
                {Object.entries(TYPE_CONFIG).filter(([type]) => type !== 'pdf').map(([type, cfg]) => {
                  const TypeIcon = cfg.icon;
                  return (
                    <button
                      key={type}
                      onClick={() => setFormData(prev => ({ ...prev, type }))}
                      className={cn(
                        "flex flex-col items-center gap-1 p-3 rounded-lg border transition-all",
                        formData.type === type
                          ? "border-primary bg-primary/5"
                          : "border-border hover:border-primary/30"
                      )}
                      data-testid={`type-btn-${type}`}
                    >
                      <TypeIcon className={cn("w-5 h-5", formData.type === type ? "text-primary" : "text-muted-foreground")} />
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
                onValueChange={(v) => setFormData(prev => ({ ...prev, project_id: v, client_ids: [] }))}
              >
                <SelectTrigger data-testid="project-select">
                  <SelectValue placeholder="Select project" />
                </SelectTrigger>
                <SelectContent>
                  {projects.map(p => (
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
                            setFormData(prev => ({
                              ...prev,
                              client_ids: checked ? projectClients.map(c => c.client_id) : []
                            }));
                          }}
                          data-testid="select-all-clients"
                        />
                        <label className="text-sm font-medium">Select all ({projectClients.length})</label>
                      </div>
                      {projectClients.map(client => (
                        <div key={client.client_id} className="flex items-center space-x-2">
                          <Checkbox
                            checked={formData.client_ids.includes(client.client_id)}
                            onCheckedChange={(checked) => {
                              setFormData(prev => ({
                                ...prev,
                                client_ids: checked
                                  ? [...prev.client_ids, client.client_id]
                                  : prev.client_ids.filter(id => id !== client.client_id)
                              }));
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

            {/* Title */}
            <div className="space-y-2">
              <Label htmlFor="title">Title</Label>
              <Input
                id="title"
                value={formData.title}
                onChange={(e) => setFormData(prev => ({ ...prev, title: e.target.value }))}
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
                onChange={(e) => setFormData(prev => ({ ...prev, content: e.target.value }))}
                placeholder={
                  formData.type === 'image' ? "Optional description for the image..."
                  : formData.type === 'file' ? "Optional description for the document..."
                  : "Write your message..."
                }
                rows={4}
                data-testid="activity-content-input"
              />
            </div>

            {/* File upload for image/file with drag-and-drop */}
            {(formData.type === 'image' || formData.type === 'file') && (
              <div className="space-y-2">
                <Label>{formData.type === 'image' ? 'Images *' : 'Document *'}</Label>
                <div 
                  className={cn(
                    "border-2 border-dashed rounded-lg p-4 text-center transition-colors",
                    dragActive 
                      ? "border-primary bg-primary/5" 
                      : "border-border hover:border-primary/50"
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
                      const imageFiles = droppedFiles.filter(f => f.type.startsWith('image/'));
                      if (imageFiles.length > 0) {
                        setFiles(prev => [...prev, ...imageFiles]);
                      } else {
                        toast.error('Please drop image files only');
                      }
                    } else {
                      // For documents, only take the first file
                      if (droppedFiles.length > 0) {
                        setFiles([droppedFiles[0]]);
                      }
                    }
                  }}
                  data-testid="file-drop-zone"
                >
                  {files.length > 0 ? (
                    <div className="space-y-3">
                      {/* Image previews grid */}
                      {formData.type === 'image' && (
                        <div className="grid grid-cols-3 gap-2">
                          {files.map((f, idx) => (
                            <div key={idx} className="relative group aspect-square">
                              <img 
                                src={URL.createObjectURL(f)} 
                                alt={f.name}
                                className="w-full h-full object-cover rounded-lg"
                              />
                              <button
                                type="button"
                                onClick={() => setFiles(prev => prev.filter((_, i) => i !== idx))}
                                className="absolute -top-2 -right-2 w-6 h-6 bg-destructive text-destructive-foreground rounded-full flex items-center justify-center opacity-0 group-hover:opacity-100 transition-opacity"
                              >
                                <X className="w-3 h-3" />
                              </button>
                            </div>
                          ))}
                        </div>
                      )}
                      
                      {/* File list for documents */}
                      {formData.type === 'file' && files.map((f, idx) => (
                        <div key={idx} className="flex items-center justify-between p-2 bg-muted rounded-lg">
                          <div className="flex items-center gap-2">
                            <FileText className="w-4 h-4 text-muted-foreground" />
                            <span className="text-sm truncate max-w-[200px]">{f.name}</span>
                          </div>
                          <Button
                            variant="ghost"
                            size="sm"
                            onClick={() => setFiles(prev => prev.filter((_, i) => i !== idx))}
                          >
                            <X className="w-4 h-4" />
                          </Button>
                        </div>
                      ))}
                      
                      {/* Add more images button */}
                      {formData.type === 'image' && (
                        <label className="cursor-pointer">
                          <input
                            type="file"
                            accept="image/*"
                            multiple
                            onChange={(e) => {
                              const newFiles = Array.from(e.target.files || []);
                              setFiles(prev => [...prev, ...newFiles]);
                              e.target.value = ''; // Reset to allow same file
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
                        onChange={(e) => {
                          const selectedFiles = Array.from(e.target.files || []);
                          setFiles(selectedFiles);
                        }}
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
                              : 'Drop document here or click to browse'
                          }
                        </p>
                        <p className="text-xs text-muted-foreground mt-1">
                          {formData.type === 'image' 
                            ? 'JPG, PNG, GIF, WebP (max 20MB each)' 
                            : 'PDF, Word, Excel, or PowerPoint (max 20MB)'
                          }
                        </p>
                      </div>
                    </label>
                  )}
                </div>
              </div>
            )}
          </div>
          
          <DialogFooter>
            <Button variant="outline" onClick={() => setShowCreateDialog(false)}>
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
  }

  return (
    <div className="space-y-6" data-testid="feed-container">
      {/* Header - only for non-embedded agent view */}
      {isAgent && !embedded && (
        <div className="flex items-start justify-between">
          <div>
            <h1 className="text-3xl font-outfit font-semibold text-foreground tracking-tight">
              Activity Feed
            </h1>
            <div className="flex items-center gap-2 mt-1 flex-wrap">
              <p className="text-muted-foreground">{total} activit{total === 1 ? 'y' : 'ies'}</p>
              {filterClient && (
                <button 
                  onClick={clearFilters}
                  className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-primary/10 text-primary text-xs font-medium hover:bg-primary/20 transition-colors"
                >
                  <User className="w-3 h-3" />
                  {filterClient.name}
                  <X className="w-3 h-3" />
                </button>
              )}
              {filterProject && (
                <button 
                  onClick={clearFilters}
                  className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-primary/10 text-primary text-xs font-medium hover:bg-primary/20 transition-colors"
                >
                  <Building2 className="w-3 h-3" />
                  {filterProject.name}
                  <X className="w-3 h-3" />
                </button>
              )}
            </div>
          </div>
          <Button 
            className="rounded-lg"
            onClick={() => setShowCreateDialog(true)}
            data-testid="create-activity-btn"
          >
            <Plus className="w-4 h-4 mr-2" />
            New Post
          </Button>
        </div>
      )}

      {/* Buyer header when embedded */}
      {!isAgent && embedded && total > 0 && (
        <div className="flex items-center justify-between">
          <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">
            Updates from your agent
          </p>
          <span className="text-xs text-muted-foreground">{total} update{total !== 1 ? 's' : ''}</span>
        </div>
      )}

      {/* Activities List */}
      <div className="space-y-4">
        {activities.map(activity => (
          <ActivityCard 
            key={activity.activity_id} 
            activity={activity}
            onReply={handleReply}
            onSendDraft={handleSendDraft}
            onEdit={handleEditActivity}
            onDelete={(activityId) => setDeleteConfirm({ open: true, activity: activities.find(a => a.activity_id === activityId) })}
            canReply={!activity.is_draft}
            isAgent={isAgent}
          />
        ))}
        
        {/* Pagination */}
        {total > limit && (
          <div className="flex justify-center gap-2 pt-4">
            <Button
              variant="outline"
              size="sm"
              disabled={offset === 0}
              onClick={() => setOffset(Math.max(0, offset - limit))}
            >
              Previous
            </Button>
            <span className="text-sm text-muted-foreground py-2">
              {offset + 1} - {Math.min(offset + limit, total)} of {total}
            </span>
            <Button
              variant="outline"
              size="sm"
              disabled={offset + limit >= total}
              onClick={() => setOffset(offset + limit)}
            >
              Next
            </Button>
          </div>
        )}
      </div>

      {/* Create dialog for agent */}
      {isAgent && renderCreateDialog()}

      {/* Edit Activity Dialog */}
      <Dialog open={!!editingActivity} onOpenChange={(open) => !open && setEditingActivity(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Edit Activity</DialogTitle>
            <DialogDescription>
              Update the title and content of this activity.
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4 py-4">
            <div className="space-y-2">
              <Label htmlFor="edit-title">Title</Label>
              <Input
                id="edit-title"
                value={editFormData.title}
                onChange={(e) => setEditFormData({ ...editFormData, title: e.target.value })}
                placeholder="Activity title"
                data-testid="edit-activity-title"
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="edit-content">Content</Label>
              <Textarea
                id="edit-content"
                value={editFormData.content}
                onChange={(e) => setEditFormData({ ...editFormData, content: e.target.value })}
                placeholder="Activity content"
                rows={4}
                data-testid="edit-activity-content"
              />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setEditingActivity(null)}>
              Cancel
            </Button>
            <Button onClick={handleSaveEdit} disabled={saving} data-testid="save-edit-activity-btn">
              {saving ? <Loader2 className="w-4 h-4 animate-spin mr-2" /> : null}
              Save Changes
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Delete Confirmation Dialog */}
      <Dialog open={deleteConfirm.open} onOpenChange={(open) => !open && setDeleteConfirm({ open: false, activity: null })}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Delete Activity</DialogTitle>
            <DialogDescription>
              Are you sure you want to delete this activity? This action cannot be undone.
            </DialogDescription>
          </DialogHeader>
          {deleteConfirm.activity && (
            <div className="p-3 bg-muted rounded-lg">
              <p className="font-medium">{deleteConfirm.activity.title || 'Untitled'}</p>
              <p className="text-sm text-muted-foreground truncate">{deleteConfirm.activity.content}</p>
            </div>
          )}
          <DialogFooter>
            <Button variant="outline" onClick={() => setDeleteConfirm({ open: false, activity: null })}>
              Cancel
            </Button>
            <Button 
              variant="destructive" 
              onClick={() => deleteConfirm.activity && handleDeleteActivity(deleteConfirm.activity.activity_id)}
              data-testid="confirm-delete-activity-btn"
            >
              <Trash2 className="w-4 h-4 mr-2" />
              Delete
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
};

export default Feed;
