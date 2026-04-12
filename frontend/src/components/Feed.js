import { useState, useEffect, useCallback, useRef } from 'react';
import { useSearchParams, useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { useDataContext } from '../context/DataContext';
import { Card, CardContent, CardHeader } from './ui/card';
import { Button } from './ui/button';
import { Label } from './ui/label';
import { Textarea } from './ui/textarea';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from './ui/dialog';
import { toast } from 'sonner';
import { CreateActivityDialog } from './CreateActivityDialog';
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

/** One text block for display (legacy rows may have title + content). */
const getActivityPostBody = (activity) => {
  const t = activity.title?.trim();
  const c = activity.content?.trim();
  if (t && c) return `${t}\n\n${c}`;
  return c || t || '';
};

const imageUrlLooksLikeImage = (url) =>
  url && /\.(jpe?g|png|gif|webp|bmp|svg)(\?|#|$)/i.test(url);

// Helper: get auth headers for fetch calls
const getAuthHeaders = () => {
  const token = localStorage.getItem('auth_token');
  return token ? { 'Authorization': `Bearer ${token}` } : {};
};

/**
 * Activity file URLs require JWT; <img src> does not send Authorization headers.
 * Load bytes with fetch + blob URL so images stay visible after remount/navigation.
 */
const useAuthenticatedActivityImage = (imageUrl) => {
  const [displaySrc, setDisplaySrc] = useState(null);
  const [status, setStatus] = useState('idle');
  const blobRef = useRef(null);

  useEffect(() => {
    if (!imageUrl) {
      setDisplaySrc(null);
      setStatus('idle');
      return;
    }
    let cancelled = false;
    setStatus('loading');
    setDisplaySrc(null);
    if (blobRef.current) {
      URL.revokeObjectURL(blobRef.current);
      blobRef.current = null;
    }

    (async () => {
      try {
        const res = await fetch(imageUrl, {
          credentials: 'include',
          headers: getAuthHeaders(),
        });
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const blob = await res.blob();
        if (cancelled) return;
        const ou = URL.createObjectURL(blob);
        blobRef.current = ou;
        setDisplaySrc(ou);
        setStatus('ready');
      } catch {
        if (!cancelled) setStatus('error');
      }
    })();

    return () => {
      cancelled = true;
      if (blobRef.current) {
        URL.revokeObjectURL(blobRef.current);
        blobRef.current = null;
      }
    };
  }, [imageUrl]);

  return { displaySrc, status };
};

const ActivityCard = ({ activity, onReply, onSendDraft, onEdit, onDelete, canReply = true, isAgent = false }) => {
  const [expanded, setExpanded] = useState(false);
  const [showReplyInput, setShowReplyInput] = useState(false);
  const [replyText, setReplyText] = useState('');
  const [replying, setReplying] = useState(false);
  const [sending, setSending] = useState(false);
  const [inlineImageDecodeFailed, setInlineImageDecodeFailed] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [replies, setReplies] = useState(activity.replies || []);
  const [loadingReplies, setLoadingReplies] = useState(false);

  const config = TYPE_CONFIG[activity.type] || TYPE_CONFIG.message;
  const Icon = config.icon;
  const isDraft = activity.is_draft;
  const postBody = getActivityPostBody(activity);
  const fileUrlFull = activity.file_url ? `${process.env.REACT_APP_BACKEND_URL}${activity.file_url}` : null;
  const hasImageAttachment =
    activity.type === 'image' ||
    (activity.file_name && isImageFile(activity.file_name)) ||
    imageUrlLooksLikeImage(fileUrlFull);
  const imageUrl = hasImageAttachment && fileUrlFull ? fileUrlFull : null;
  const { displaySrc: authImageSrc, status: imageAuthStatus } = useAuthenticatedActivityImage(imageUrl);

  useEffect(() => {
    setInlineImageDecodeFailed(false);
  }, [activity.activity_id, imageUrl]);

  const showImageSkeleton =
    Boolean(hasImageAttachment && imageUrl && imageAuthStatus === 'loading');
  const showImageInline =
    Boolean(
      hasImageAttachment &&
        imageUrl &&
        imageAuthStatus === 'ready' &&
        authImageSrc &&
        !inlineImageDecodeFailed
    );
  const showFileAttachmentRow =
    Boolean(activity.file_name && fileUrlFull) &&
    (!hasImageAttachment || imageAuthStatus === 'error' || inlineImageDecodeFailed);

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

  useEffect(() => {
    if (isAgent || !activity.reply_count) return;
    if ((activity.replies || []).length > 0) return;
    let cancelled = false;
    (async () => {
      setLoadingReplies(true);
      try {
        const res = await fetch(`${API}/activities/${activity.activity_id}`, {
          credentials: 'include',
          headers: getAuthHeaders()
        });
        if (res.ok && !cancelled) {
          const data = await res.json();
          setReplies(data.replies || []);
        }
      } catch (e) {
        console.error('Failed to fetch replies:', e);
      } finally {
        if (!cancelled) setLoadingReplies(false);
      }
    })();
    return () => { cancelled = true; };
  }, [isAgent, activity.activity_id, activity.reply_count]);

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
      if (isAgent) setShowReplyInput(false);
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

  /* —— Buyer: simple social-style card (image → text → comments) —— */
  if (!isAgent) {
    return (
      <Card
        className="border-border rounded-xl overflow-hidden shadow-sm"
        data-testid={`activity-card-${activity.activity_id}`}
      >
        <CardContent className="p-0">
          <div className="px-4 pt-4 pb-2 flex items-start justify-between gap-3">
            <div className="min-w-0 flex-1">
              <p className="text-sm font-semibold text-foreground">{activity.author_name}</p>
              <p className="text-xs text-muted-foreground mt-0.5">
                {formatDate(activity.created_at)}
                {activity.unit_reference ? (
                  <span className="text-muted-foreground"> · {activity.unit_reference}</span>
                ) : null}
              </p>
            </div>
          </div>

          {hasImageAttachment && imageUrl && (
            <>
              {showImageSkeleton && (
                <div className="mt-2 border-y border-border bg-muted/30" aria-busy>
                  <div className="w-full min-h-[200px] max-h-[min(70vh,520px)] animate-pulse bg-muted/80" />
                </div>
              )}
              {showImageInline && (
                <div className="mt-2 border-y border-border bg-muted/30">
                  <a
                    href={authImageSrc}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="block"
                    data-testid={`image-preview-${activity.activity_id}`}
                  >
                    <img
                      src={authImageSrc}
                      alt=""
                      className="w-full max-h-[min(70vh,520px)] object-contain bg-muted/20"
                      onError={() => setInlineImageDecodeFailed(true)}
                    />
                  </a>
                </div>
              )}
            </>
          )}

          {showFileAttachmentRow && (
            <div className="mx-4 mt-3 p-3 rounded-lg border border-border bg-muted/40 flex items-center justify-between gap-2">
              <div className="flex items-center gap-2 min-w-0">
                <FileText className="w-4 h-4 text-muted-foreground flex-shrink-0" />
                <span className="text-sm font-medium truncate">{activity.file_name}</span>
                {activity.file_size ? (
                  <span className="text-xs text-muted-foreground flex-shrink-0 hidden sm:inline">
                    {(activity.file_size / 1024 / 1024).toFixed(1)} MB
                  </span>
                ) : null}
              </div>
              <Button variant="outline" size="sm" className="flex-shrink-0" asChild>
                <a href={fileUrlFull} target="_blank" rel="noopener noreferrer" data-testid={`download-file-${activity.activity_id}`}>
                  <Download className="w-4 h-4 sm:mr-1" />
                  <span className="hidden sm:inline">Open</span>
                </a>
              </Button>
            </div>
          )}

          {postBody ? (
            <div className="px-4 py-3">
              <p className="text-sm text-foreground whitespace-pre-wrap break-words leading-relaxed">{postBody}</p>
            </div>
          ) : null}

          <div className="border-t border-border bg-muted/15 px-4 py-3 space-y-3">
            <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wide">Comments</p>
            {loadingReplies && replies.length === 0 ? (
              <div className="flex items-center gap-2 text-sm text-muted-foreground">
                <Loader2 className="w-4 h-4 animate-spin" />
                Loading…
              </div>
            ) : null}
            {replies.map((reply) => (
              <div key={reply.reply_id} className="rounded-lg bg-background/80 border border-border/60 px-3 py-2">
                <p className="text-sm text-foreground">{reply.content}</p>
                <p className="text-[11px] text-muted-foreground mt-1">
                  {reply.author_name}
                  {reply.author_role ? ` · ${reply.author_role}` : ''} · {formatDate(reply.created_at)}
                </p>
              </div>
            ))}
            {canReply ? (
              <div className="space-y-2 pt-1">
                <Textarea
                  value={replyText}
                  onChange={(e) => setReplyText(e.target.value)}
                  placeholder="Write a comment…"
                  rows={3}
                  className="resize-none text-sm"
                  data-testid={`reply-input-${activity.activity_id}`}
                />
                <div className="flex justify-end">
                  <Button size="sm" onClick={handleReply} disabled={!replyText.trim() || replying} data-testid={`send-reply-${activity.activity_id}`}>
                    {replying ? <Loader2 className="w-4 h-4 animate-spin" /> : 'Comment'}
                  </Button>
                </div>
              </div>
            ) : null}
          </div>
        </CardContent>
      </Card>
    );
  }

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
              <p className="text-[11px] sm:text-xs text-muted-foreground mt-1 truncate">
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
        {/* Image first (social-style), then text — blob URL so JWT is applied */}
        {hasImageAttachment && imageUrl && (
          <>
            {showImageSkeleton && (
              <div className="mt-3 rounded-lg overflow-hidden bg-muted/30" aria-busy>
                <div className="w-full min-h-[180px] max-h-96 animate-pulse bg-muted/80" />
              </div>
            )}
            {showImageInline && (
              <div className="mt-3 rounded-lg overflow-hidden bg-muted/30">
                <a
                  href={authImageSrc}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="block"
                  data-testid={`image-preview-${activity.activity_id}`}
                >
                  <img
                    src={authImageSrc}
                    alt={activity.file_name || 'Image attachment'}
                    className="w-full max-h-96 object-contain cursor-pointer hover:opacity-90 transition-opacity"
                    onError={() => setInlineImageDecodeFailed(true)}
                  />
                </a>
              </div>
            )}
          </>
        )}

        {postBody ? (
          <p className={cn(
            'text-xs sm:text-sm text-foreground whitespace-pre-wrap break-words mt-3',
            !expanded && 'line-clamp-4'
          )}>
            {postBody}
          </p>
        ) : null}
        
        {/* File attachment - PDF/docs, or image when fetch/decode failed */}
        {showFileAttachmentRow && (
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
                <a href={`${process.env.REACT_APP_BACKEND_URL}${activity.file_url}`} download target="_blank" rel="noopener noreferrer">
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
export const Feed = ({ isAgent = false, embedded = false, highlightActivityId = null }) => {
  const { user } = useAuth();
  const [searchParams, setSearchParams] = useSearchParams();
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
  
  // Edit state
  const [editingActivity, setEditingActivity] = useState(null);
  const [editFormData, setEditFormData] = useState({ content: '' });
  const [saving, setSaving] = useState(false);
  
  // Delete confirmation state  
  const [deleteConfirm, setDeleteConfirm] = useState({ open: false, activity: null });
  const highlightInjectAttempted = useRef(null);

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

  useEffect(() => {
    highlightInjectAttempted.current = null;
  }, [highlightActivityId]);

  useEffect(() => {
    if (isAgent || !embedded || !highlightActivityId || loading) return;
    if (activities.some((a) => a.activity_id === highlightActivityId)) return;
    if (highlightInjectAttempted.current === highlightActivityId) return;
    highlightInjectAttempted.current = highlightActivityId;

    (async () => {
      try {
        const res = await fetch(`${API}/activities/${highlightActivityId}`, {
          credentials: 'include',
          headers: getAuthHeaders(),
        });
        if (res.ok) {
          const one = await res.json();
          setActivities((prev) =>
            prev.some((a) => a.activity_id === one.activity_id) ? prev : [one, ...prev]
          );
        } else {
          toast.error('This update is no longer available');
          setSearchParams((prev) => {
            const n = new URLSearchParams(prev);
            n.delete('activity_id');
            return n;
          }, { replace: true });
        }
      } catch {
        toast.error('This update is no longer available');
        setSearchParams((prev) => {
          const n = new URLSearchParams(prev);
          n.delete('activity_id');
          return n;
        }, { replace: true });
      }
    })();
  }, [isAgent, embedded, highlightActivityId, loading, activities, setSearchParams]);

  useEffect(() => {
    if (isAgent || !embedded || !highlightActivityId || loading) return;
    if (!activities.some((a) => a.activity_id === highlightActivityId)) return;
    requestAnimationFrame(() => {
      const el = document.querySelector(`[data-testid="activity-card-${highlightActivityId}"]`);
      if (el) {
        el.scrollIntoView({ behavior: 'smooth', block: 'center' });
        el.classList.add('ring-2', 'ring-primary', 'ring-offset-2');
        setTimeout(() => el.classList.remove('ring-2', 'ring-primary', 'ring-offset-2'), 2000);
      }
    });
  }, [isAgent, embedded, highlightActivityId, loading, activities]);

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
      content: getActivityPostBody(activity),
    });
  };

  const handleSaveEdit = async () => {
    if (!editingActivity) return;
    
    setSaving(true);
    try {
      const res = await fetch(`${API}/activities/${editingActivity.activity_id}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json', ...getAuthHeaders() },
        credentials: 'include',
        body: JSON.stringify({ title: '', content: editFormData.content })
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
        {isAgent && (
          <CreateActivityDialog
            open={showCreateDialog}
            onOpenChange={setShowCreateDialog}
            projects={projects}
            clients={clients}
            onCreated={fetchActivities}
          />
        )}
      </div>
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
      {/* Create dialog for agent */}
      {isAgent && (
        <CreateActivityDialog
          open={showCreateDialog}
          onOpenChange={setShowCreateDialog}
          projects={projects}
          clients={clients}
          onCreated={fetchActivities}
        />
      )}

      {/* Edit Activity Dialog */}
      <Dialog open={!!editingActivity} onOpenChange={(open) => !open && setEditingActivity(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Edit Activity</DialogTitle>
            <DialogDescription>
              Edit the text of this post. Attachments stay the same.
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4 py-4">
            <div className="space-y-2">
              <Label htmlFor="edit-content">Post</Label>
              <Textarea
                id="edit-content"
                value={editFormData.content}
                onChange={(e) => setEditFormData({ ...editFormData, content: e.target.value })}
                placeholder="Post text"
                rows={6}
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
              <p className="text-sm text-muted-foreground line-clamp-3">
                {getActivityPostBody(deleteConfirm.activity) || 'This post'}
              </p>
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
