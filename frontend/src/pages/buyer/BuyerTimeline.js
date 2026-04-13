import { useState, useEffect, useCallback, useRef, useMemo } from 'react';
import { useSearchParams } from 'react-router-dom';
import { useAuth } from '../../context/AuthContext';
import { useSettings } from '../../context/SettingsContext';
import { useWebSocket } from '../../hooks/useWebSocket';
import { Button } from '../../components/ui/button';
import { Card, CardContent } from '../../components/ui/card';
import { Textarea } from '../../components/ui/textarea';
import { Input } from '../../components/ui/input';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter, DialogDescription } from '../../components/ui/dialog';
import { toast } from 'sonner';
import { ThemeToggle } from '../../components/ThemeToggle';
import { NotificationCenter } from '../../components/NotificationCenter';
import { PdfViewer } from '../../components/PdfViewer';
import { 
  Home, 
  LogOut, 
  FileText, 
  Receipt, 
  CheckCircle, 
  XCircle, 
  MessageCircle,
  Clock,
  Download,
  ChevronDown,
  ChevronUp,
  HardHat,
  Send,
  Loader2,
  Calendar,
  Eye,
  Search,
  X,
  QrCode,
  Copy,
  ExternalLink,
  ImageIcon,
  Bell,
  Building2,
  FolderOpen,
  FileCheck,
  AlertTriangle,
  File,
  FileSpreadsheet,
  CheckSquare,
  Paperclip,
  UserCircle,
  Mail,
  Phone
} from 'lucide-react';
import { cn } from '../../lib/utils';

const BUYER_CATEGORY_COLORS = {
  quote: 'bg-blue-500/10 text-blue-600 dark:text-blue-400 border-blue-500/20',
  invoice: 'bg-purple-500/10 text-purple-600 dark:text-purple-400 border-purple-500/20',
  update: 'bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border-emerald-500/20',
  vault: 'bg-amber-500/10 text-amber-600 dark:text-amber-400 border-amber-500/20',
  decision: 'bg-orange-500/10 text-orange-600 dark:text-orange-400 border-orange-500/20',
};

const API = process.env.REACT_APP_BACKEND_URL + '/api';

const getAuthHeaders = () => {
  const token = localStorage.getItem('auth_token');
  return token ? { 'Authorization': `Bearer ${token}` } : {};
};

// Change Request Thread — shows the full buyer-agent exchange
const ChangeRequestThread = ({
  entityType,
  entityId,
  buyerComment,
  preferredChangeRequestId = null,
  onPreferredMiss = null,
}) => {
  const [thread, setThread] = useState(null);
  const [loading, setLoading] = useState(true);
  const [replyText, setReplyText] = useState('');
  const [sending, setSending] = useState(false);

  const fetchThread = useCallback(async () => {
    try {
      const res = await fetch(
        `${API}/change-requests/entity/${entityType}/${entityId}`,
        { credentials: 'include', headers: getAuthHeaders() }
      );
      if (res.ok) {
        const data = await res.json();
        const list = data.change_requests || [];
        let chosen = null;
        if (preferredChangeRequestId) {
          const match = list.find((cr) => cr.change_request_id === preferredChangeRequestId);
          if (match) {
            chosen = match;
          } else {
            toast.error('This change request is no longer available');
            onPreferredMiss?.();
          }
        } else {
          chosen = list[0] || null;
        }
        setThread(chosen);
      }
    } catch {
      // Fallback to just showing the buyer comment
    } finally {
      setLoading(false);
    }
  }, [entityType, entityId, preferredChangeRequestId, onPreferredMiss]);

  useEffect(() => {
    setLoading(true);
    fetchThread();
  }, [fetchThread]);

  useEffect(() => {
    if (!thread?.change_request_id || !preferredChangeRequestId) return;
    if (thread.change_request_id !== preferredChangeRequestId) return;
    requestAnimationFrame(() => {
      const el = document.querySelector(
        `[data-testid="change-request-thread-${thread.change_request_id}"]`
      );
      if (el) {
        el.scrollIntoView({ behavior: 'smooth', block: 'center' });
        el.classList.add('ring-2', 'ring-primary', 'ring-offset-2');
        setTimeout(() => el.classList.remove('ring-2', 'ring-primary', 'ring-offset-2'), 2000);
      }
    });
  }, [thread, preferredChangeRequestId]);

  const handleSendReply = async () => {
    if (!thread?.change_request_id || !replyText.trim()) return;
    setSending(true);
    try {
      const res = await fetch(`${API}/change-requests/${thread.change_request_id}/respond`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', ...getAuthHeaders() },
        credentials: 'include',
        body: JSON.stringify({ message: replyText.trim() }),
      });
      if (res.ok) {
        toast.success('Message sent');
        setReplyText('');
        await fetchThread();
      } else {
        const err = await res.json().catch(() => ({}));
        toast.error(err.detail?.message || err.detail || 'Failed to send');
      }
    } catch {
      toast.error('Failed to send');
    } finally {
      setSending(false);
    }
  };

  // If no canonical thread exists and no legacy comment, hide
  if (loading) return null;

  if (!thread) {
    if (!buyerComment) return null;
    return (
      <div className="p-3 bg-blue-500/10 rounded-lg border border-blue-500/20">
        <p className="text-xs font-semibold text-blue-600 dark:text-blue-400 mb-1">Your question</p>
        <p className="text-sm text-foreground">{buyerComment}</p>
      </div>
    );
  }

  const canReply = thread.status === 'open' || thread.status === 'under_review';

  return (
    <div
      className="rounded-lg border border-blue-500/20 overflow-hidden"
      data-testid={thread.change_request_id ? `change-request-thread-${thread.change_request_id}` : 'change-request-thread'}
    >
      <div className="px-3 py-2 bg-blue-500/10 border-b border-blue-500/20">
        <p className="text-xs font-semibold text-blue-600 dark:text-blue-400">
          Change Request
          {thread.status === 'closed' && (
            <span className="ml-2 text-muted-foreground font-normal">Closed</span>
          )}
          {thread.status === 'resolved' && (
            <span className="ml-2 text-emerald-600 font-normal">Resolved</span>
          )}
          {thread.status === 'open' && (
            <span className="ml-2 text-amber-600 font-normal">Awaiting response</span>
          )}
          {thread.status === 'under_review' && (
            <span className="ml-2 text-blue-600 font-normal">Under review</span>
          )}
        </p>
      </div>
      <div className="p-3 space-y-2">
        {thread.messages.map(msg => (
          <div
            key={msg.message_id}
            className={cn(
              'p-2 rounded-lg text-sm',
              msg.author_role === 'buyer' ? 'bg-muted/50' : 'bg-primary/5 ml-3'
            )}
          >
            <div className="flex items-center gap-1.5 mb-1">
              <span className="text-xs font-medium capitalize text-muted-foreground">
                {msg.author_role === 'buyer' ? 'You' : 'Agent'}
              </span>
              <span className="text-[10px] text-muted-foreground">
                {new Date(msg.created_at).toLocaleDateString('de-CH', { day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit' })}
              </span>
            </div>
            <p className="whitespace-pre-wrap">{msg.content}</p>
          </div>
        ))}
        {canReply && (
          <div className="pt-2 border-t border-blue-500/10 space-y-2">
            <Textarea
              value={replyText}
              onChange={(e) => setReplyText(e.target.value)}
              placeholder="Add a message to your agent..."
              rows={3}
              className="text-sm resize-none"
              data-testid="change-request-reply-input"
            />
            <Button
              size="sm"
              disabled={sending || !replyText.trim()}
              onClick={handleSendReply}
              data-testid="change-request-reply-send"
            >
              {sending ? <Loader2 className="w-4 h-4 animate-spin mr-1" /> : <Send className="w-4 h-4 mr-1" />}
              Send
            </Button>
          </div>
        )}
      </div>
    </div>
  );
};

const formatCurrency = (amount, currency = 'CHF') => {
  return `${currency} ${new Intl.NumberFormat('de-CH', { 
    style: 'decimal', 
    minimumFractionDigits: 2,
    maximumFractionDigits: 2 
  }).format(amount)}`;
};

const formatDate = (dateStr) => {
  if (!dateStr) return '';
  const date = new Date(dateStr);
  return date.toLocaleDateString('en-GB', { day: 'numeric', month: 'short', year: 'numeric' });
};


const formatRelativeTime = (dateStr) => {
  const date = new Date(dateStr);
  const now = new Date();
  const diff = now - date;
  const days = Math.floor(diff / (1000 * 60 * 60 * 24));
  
  if (days === 0) return 'Today';
  if (days === 1) return 'Yesterday';
  if (days < 7) return `${days} days ago`;
  return formatDate(dateStr);
};

const mapLegacyTabToFilter = (tab) => {
  const normalized = (tab || '').toLowerCase();
  if (normalized === 'documents') return 'all';
  if (normalized === 'updates') return 'updates';
  if (normalized === 'vault') return 'vault';
  if (normalized === 'decisions') return 'decisions';
  return null;
};

const FEED_FILTERS = [
  { key: 'all', label: 'All', icon: Home },
  { key: 'quotes', label: 'Quotes', icon: FileText },
  { key: 'invoices', label: 'Invoices', icon: Receipt },
  { key: 'updates', label: 'Updates', icon: Bell },
  { key: 'vault', label: 'Vault', icon: FolderOpen },
  { key: 'decisions', label: 'Decisions', icon: CheckSquare },
];

const resolveFeedFileUrl = (fileUrl) => {
  if (!fileUrl) return null;
  if (String(fileUrl).startsWith('http')) return fileUrl;
  return `${process.env.REACT_APP_BACKEND_URL}${fileUrl}`;
};

const sortVaultDocuments = (docs = []) => {
  return [...docs].sort((a, b) => {
    const aArch = a.is_architect_plan || a.doc_type === 'architect_plan' || a.category === 'architect_plans';
    const bArch = b.is_architect_plan || b.doc_type === 'architect_plan' || b.category === 'architect_plans';
    if (aArch !== bArch) return aArch ? -1 : 1;
    return new Date(b.created_at || 0).getTime() - new Date(a.created_at || 0).getTime();
  });
};

const getActivityBody = (activity) => {
  const title = activity?.title?.trim();
  const content = activity?.content?.trim();
  if (title && content) return `${title}\n\n${content}`;
  return content || title || '';
};

const normalizeTimelineStatus = (rawStatus) => {
  const normalized = String(rawStatus || '')
    .toLowerCase()
    .trim()
    .replace(/[\s-]+/g, '_');

  if (['approved', 'completed', 'done', 'closed'].includes(normalized)) return 'completed';
  if (['in_progress', 'inprogress', 'active', 'started', 'ongoing'].includes(normalized)) return 'in_progress';
  if (['pending', 'not_started', 'todo', 'queued'].includes(normalized)) return 'pending';
  return normalized || 'pending';
};

const BuyerUpdateFeedCard = ({ activity, highlight = false }) => {
  const fileUrl = resolveFeedFileUrl(activity.file_url);
  const postBody = getActivityBody(activity);
  const ext = String(activity.file_name || '').split('.').pop()?.toLowerCase();
  const isImage = activity.type === 'image' || Boolean(activity.file_type?.startsWith('image/')) || ['jpg', 'jpeg', 'png', 'gif', 'webp', 'bmp', 'svg'].includes(ext);

  return (
    <Card
      className={cn(
        'mb-6 overflow-hidden transition-all duration-200 hover:shadow-md',
        highlight && 'ring-2 ring-primary/40'
      )}
      data-testid={`buyer-update-${activity.activity_id}`}
    >
      <CardContent className="p-0">
        <div className="px-4 pt-4 pb-2">
          <div className="flex items-start justify-between gap-3">
            <div className="min-w-0">
              <p className="text-sm font-semibold text-foreground">{activity.author_name || 'Your agent'}</p>
              <p className="text-xs text-muted-foreground mt-0.5">{formatRelativeTime(activity.created_at)}</p>
            </div>
            <span className="inline-flex items-center px-2 py-0.5 text-[10px] font-semibold rounded-full border uppercase tracking-wider bg-blue-500/10 text-blue-600 border-blue-500/20">
              Update
            </span>
          </div>
        </div>

        {isImage && fileUrl && (
          <div className="border-y border-border bg-muted/30">
            <img src={fileUrl} alt={activity.file_name || 'Update attachment'} className="w-full max-h-[420px] object-contain" />
          </div>
        )}

        {!isImage && fileUrl && (
          <div className="mx-4 mt-2 p-3 rounded-lg border border-border bg-muted/30 flex items-center justify-between gap-3">
            <div className="min-w-0 flex items-center gap-2">
              <FileText className="w-4 h-4 text-muted-foreground flex-shrink-0" />
              <span className="text-sm truncate">{activity.file_name || 'Attachment'}</span>
            </div>
            <Button variant="outline" size="sm" asChild className="flex-shrink-0">
              <a href={fileUrl} target="_blank" rel="noopener noreferrer">
                <Eye className="w-4 h-4 mr-1.5" />
                Open
              </a>
            </Button>
          </div>
        )}

        {postBody && (
          <div className="px-4 py-3">
            <p className="text-sm text-foreground whitespace-pre-wrap break-words">{postBody}</p>
          </div>
        )}
      </CardContent>
    </Card>
  );
};

const DecisionFeedCard = ({
  decision,
  onRespond,
  highlighted = false,
  preferredChangeRequestId = null,
  onPreferredMiss = null,
}) => {
  const [expanded, setExpanded] = useState(Boolean(highlighted));
  const [comment, setComment] = useState('');
  const [responding, setResponding] = useState(false);
  const [threadReloadTick, setThreadReloadTick] = useState(0);
  const isPending = decision?.buyer_status === 'pending';
  const isOverdue = decision?.deadline && decision?.status === 'pending' && new Date(decision.deadline) < new Date();

  useEffect(() => {
    if (highlighted || preferredChangeRequestId) setExpanded(true);
  }, [highlighted, preferredChangeRequestId]);

  const handleRespond = async (action) => {
    setResponding(true);
    try {
      await onRespond(decision.decision_id, action, action === 'request_change' ? comment : null);
      if (action === 'request_change') setComment('');
      // Ensure freshly-created/updated thread appears immediately.
      setThreadReloadTick((v) => v + 1);
    } finally {
      setResponding(false);
    }
  };

  return (
    <Card
      className={cn(
        'mb-6 overflow-hidden transition-all duration-200 hover:shadow-md',
        isPending && 'border-amber-500/30',
        isOverdue && 'border-red-500/30',
        highlighted && 'ring-2 ring-primary/40'
      )}
      data-testid={`feed-card-decision-${decision.decision_id}`}
    >
      <CardContent className="p-4">
        <div className="flex items-start gap-3 cursor-pointer" onClick={() => setExpanded((v) => !v)}>
          {decision.buyer_status === 'approved' ? (
            <CheckCircle className="w-5 h-5 text-emerald-600 mt-0.5 flex-shrink-0" />
          ) : decision.buyer_status === 'rejected' ? (
            <XCircle className="w-5 h-5 text-red-600 mt-0.5 flex-shrink-0" />
          ) : (
            <Clock className="w-5 h-5 text-amber-600 mt-0.5 flex-shrink-0" />
          )}
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2 flex-wrap">
              <span className={cn('inline-flex items-center px-2 py-0.5 text-[10px] font-semibold rounded-full border uppercase tracking-wider', BUYER_CATEGORY_COLORS.decision)}>
                Decision
              </span>
              <span className="text-xs text-muted-foreground capitalize">{decision.buyer_status}</span>
            </div>
            <p className="font-semibold text-foreground mt-2">{decision.title}</p>
            {decision.deadline && (
              <p className={cn('text-xs mt-1', isOverdue ? 'text-red-600 font-medium' : 'text-muted-foreground')}>
                Due: {new Date(decision.deadline).toLocaleDateString('de-CH')}
              </p>
            )}
          </div>
          {expanded ? <ChevronUp className="w-4 h-4 text-muted-foreground" /> : <ChevronDown className="w-4 h-4 text-muted-foreground" />}
        </div>

        {expanded && (
          <div className="mt-4 pt-4 border-t space-y-3">
            {decision.description && <p className="text-sm whitespace-pre-wrap">{decision.description}</p>}
            {decision.contact_person && (
              <div className="p-3 rounded-lg border bg-muted/20">
                <div className="flex items-start gap-2">
                  <UserCircle className="w-4 h-4 text-muted-foreground mt-0.5" />
                  <div>
                    <p className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">Contact person</p>
                    <p className="text-sm font-medium">{decision.contact_person.name || 'Contact'}</p>
                    {(decision.contact_person.company_name || decision.contact_person.role) && (
                      <p className="text-xs text-muted-foreground">
                        {[decision.contact_person.role, decision.contact_person.company_name].filter(Boolean).join(' - ')}
                      </p>
                    )}
                    {decision.contact_person.email && (
                      <p className="text-xs mt-1 flex items-center gap-1"><Mail className="w-3 h-3" />{decision.contact_person.email}</p>
                    )}
                    {decision.contact_person.phone && (
                      <p className="text-xs mt-1 flex items-center gap-1"><Phone className="w-3 h-3" />{decision.contact_person.phone}</p>
                    )}
                  </div>
                </div>
              </div>
            )}
            {decision.external_link && (
              <a href={decision.external_link} target="_blank" rel="noopener noreferrer" className="inline-flex items-center gap-2 text-sm text-primary hover:underline">
                <ExternalLink className="w-4 h-4" />
                Open linked file
              </a>
            )}
            {decision.attachments?.length > 0 && (
              <div className="space-y-1.5">
                {decision.attachments.map((att, idx) => (
                  <a
                    key={att.filename || idx}
                    href={att.url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="flex items-center gap-2 p-2 rounded-lg bg-muted/40 hover:bg-muted text-sm"
                  >
                    <Paperclip className="w-4 h-4" />
                    {att.filename || 'Attachment'}
                  </a>
                ))}
              </div>
            )}

            <ChangeRequestThread
              key={`decision-thread-${decision.decision_id}-${threadReloadTick}`}
              entityType="decision"
              entityId={decision.decision_id}
              preferredChangeRequestId={preferredChangeRequestId}
              onPreferredMiss={preferredChangeRequestId ? onPreferredMiss : undefined}
            />

            {isPending && (
              <div className="space-y-2">
                <div className="flex flex-wrap gap-2">
                  <Button size="sm" className="bg-emerald-600 hover:bg-emerald-700" onClick={() => handleRespond('approved')} disabled={responding}>
                    <CheckCircle className="w-4 h-4 mr-1" />
                    Approve
                  </Button>
                  <Button size="sm" variant="outline" className="text-red-600 border-red-500/30 hover:bg-red-500/10" onClick={() => handleRespond('rejected')} disabled={responding}>
                    <XCircle className="w-4 h-4 mr-1" />
                    Decline
                  </Button>
                </div>
                <Textarea
                  value={comment}
                  onChange={(e) => setComment(e.target.value)}
                  placeholder="Ask a question or request changes..."
                  rows={2}
                  className="text-sm"
                />
                {comment.trim() && (
                  <Button size="sm" variant="outline" onClick={() => handleRespond('request_change')} disabled={responding}>
                    <Send className="w-4 h-4 mr-1" />
                    Send request
                  </Button>
                )}
              </div>
            )}
          </div>
        )}
      </CardContent>
    </Card>
  );
};

// Status configurations
const statusConfig = {
  'Sent': { 
    label: 'Awaiting Response', 
    color: 'bg-amber-500/10 text-amber-600 dark:text-amber-400 border-amber-500/20',
    icon: Clock
  },
  'Draft': { 
    label: 'Draft', 
    color: 'bg-gray-500/10 text-gray-600 dark:text-gray-400 border-gray-500/20',
    icon: FileText
  },
  'Change Requested': { 
    label: 'Under Review', 
    color: 'bg-blue-500/10 text-blue-600 dark:text-blue-400 border-blue-500/20',
    icon: MessageCircle
  },
  'Approved': { 
    label: 'Approved', 
    color: 'bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border-emerald-500/20',
    icon: CheckCircle
  },
  'Rejected': { 
    label: 'Declined', 
    color: 'bg-red-500/10 text-red-600 dark:text-red-400 border-red-500/20',
    icon: XCircle
  },
  'Paid': { 
    label: 'Paid', 
    color: 'bg-green-500/10 text-green-600 dark:text-green-400 border-green-500/20',
    icon: CheckCircle
  },
};

// E-Commerce Style Timeline Card
const TimelineCard = ({
  event,
  onAction,
  onDownloadPdf,
  onPreviewPdf,
  onShowQrPayment,
  initialExpanded = false,
  highlightChangeRequestId = null,
  onClearChangeRequestParam = null,
}) => {
  const [expanded, setExpanded] = useState(() => event.actionRequired || initialExpanded);

  useEffect(() => {
    if (initialExpanded) setExpanded(true);
  }, [initialExpanded]);
  const [showQuestionInput, setShowQuestionInput] = useState(false);
  const [question, setQuestion] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);

  const config = statusConfig[event.status] || statusConfig['Draft'];
  const StatusIcon = config.icon;
  
  const isQuote = event.type === 'quote';
  const isInvoice = event.type === 'invoice';
  const isQuoteActionable = isQuote && event.status === 'Sent';
  const needsPayment = isInvoice && event.status === 'Sent';

  const handleQuestionSubmit = async () => {
    if (!question.trim()) return;
    setIsSubmitting(true);
    await onAction(event.id, 'request_change', question);
    setQuestion('');
    setShowQuestionInput(false);
    setIsSubmitting(false);
  };

  return (
    <div className="mb-6" data-testid={`timeline-event-${event.id}`}>
      <Card className={cn(
        "overflow-hidden transition-all duration-300 hover:shadow-xl",
        event.actionRequired && "ring-2 ring-primary/30 shadow-lg",
        !event.actionRequired && "hover:shadow-lg"
      )}>
        {/* Hero Image or Placeholder */}
        <div className={cn(
          "relative overflow-hidden",
          event.heroImageUrl ? "h-44" : "h-32"
        )}>
          {event.heroImageUrl ? (
            <>
              <img 
                src={event.heroImageUrl?.startsWith('http') ? event.heroImageUrl : `${process.env.REACT_APP_BACKEND_URL}${event.heroImageUrl}`}
                alt={event.title}
                className="w-full h-full object-cover"
              />
              <div className="absolute inset-0 bg-gradient-to-t from-black/60 via-transparent to-transparent" />
            </>
          ) : (
            <div className={cn(
              "w-full h-full flex items-center justify-center",
              isInvoice 
                ? "bg-gradient-to-br from-purple-500/20 via-purple-400/10 to-purple-600/20" 
                : "bg-gradient-to-br from-primary/20 via-blue-400/10 to-primary/20"
            )}>
              <div className="text-center">
                <div className={cn(
                  "w-14 h-14 rounded-2xl flex items-center justify-center mx-auto mb-2",
                  isInvoice ? "bg-purple-500/20" : "bg-primary/20"
                )}>
                  {isInvoice ? (
                    <Receipt className={cn("w-7 h-7", isInvoice ? "text-purple-500" : "text-primary")} />
                  ) : (
                    <FileText className="w-7 h-7 text-primary" />
                  )}
                </div>
                <p className={cn(
                  "text-xs font-medium uppercase tracking-wider",
                  isInvoice ? "text-purple-500/70" : "text-primary/70"
                )}>
                  {isInvoice ? 'Invoice' : 'Quote'}
                </p>
              </div>
            </div>
          )}
        </div>

        <CardContent className="p-0">
          {/* Main Card Content */}
          <div 
            className="p-5 cursor-pointer"
            onClick={() => setExpanded(!expanded)}
          >
            {/* Type & Status Row */}
            <div className="flex items-center gap-2 mb-3">
              <span className={cn(
                "inline-flex items-center px-2.5 py-1 text-[10px] font-bold rounded-full border uppercase tracking-wider",
                isInvoice 
                  ? "bg-purple-500/10 text-purple-600 dark:text-purple-400 border-purple-500/20" 
                  : "bg-blue-500/10 text-blue-600 dark:text-blue-400 border-blue-500/20"
              )}>
                {isInvoice ? 'Invoice' : 'Quote'}
              </span>
              <span className={cn(
                "inline-flex items-center px-2.5 py-1 text-[10px] font-bold rounded-full border uppercase tracking-wider",
                config.color
              )}>
                <StatusIcon className="w-3 h-3 mr-1" />
                {config.label}
              </span>
              {event.actionRequired && (
                <span className="ml-auto inline-flex items-center px-2.5 py-1 text-[10px] font-bold rounded-full bg-primary text-primary-foreground uppercase tracking-wider animate-pulse">
                  Action Required
                </span>
              )}
            </div>

            {/* Title & Amount */}
            <div className="flex flex-col sm:flex-row sm:items-start sm:justify-between gap-2 sm:gap-4 mb-3">
              <div className="flex-1 min-w-0">
                <h3 className="font-bold text-foreground text-lg sm:text-2xl leading-tight mb-1 break-words">{event.title}</h3>
                <p className="text-[10px] sm:text-[11px] text-muted-foreground/70">
                  {event.documentNumber} · <span className="text-muted-foreground/50">{event.supplierName || 'From your agent'}</span>
                </p>
              </div>
              <div className="sm:text-right flex-shrink-0">
                <p className="text-2xl sm:text-3xl font-bold text-foreground tracking-tight">{formatCurrency(event.amount, event.currency)}</p>
                {needsPayment && event.dueDate && (
                  <p className="text-xs text-amber-600 dark:text-amber-400 font-medium mt-0.5">
                    Due {formatDate(event.dueDate)}
                  </p>
                )}
              </div>
            </div>

            {/* Summary */}
            {event.summary && (
              <p className="text-sm text-muted-foreground mb-3 line-clamp-2">{event.summary}</p>
            )}

            {/* Footer: Date & Expand */}
            <div className="flex items-center justify-between pt-2 border-t border-border/50">
              <span className="text-xs text-muted-foreground flex items-center gap-1">
                <Calendar className="w-3 h-3" />
                {formatRelativeTime(event.date)}
              </span>
              <span className="text-xs text-muted-foreground flex items-center gap-1">
                {expanded ? 'Hide details' : 'Show details'}
                {expanded ? (
                  <ChevronUp className="w-4 h-4" />
                ) : (
                  <ChevronDown className="w-4 h-4" />
                )}
              </span>
            </div>
          </div>

          {/* Expanded Content */}
          {expanded && (
            <div className="border-t border-border p-5 space-y-4 animate-fade-in bg-muted/30">
              {/* Line Items Preview */}
              {event.items && event.items.length > 0 && (
                <div className="space-y-2">
                  <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">What's included</p>
                  <div className="grid gap-1.5">
                    {event.items.slice(0, 4).map((item, idx) => (
                      <div key={idx} className="flex items-center justify-between text-sm py-1.5 px-3 bg-background rounded-lg">
                        <span className="text-foreground">{item.description}</span>
                        <span className="text-muted-foreground font-medium">{formatCurrency(item.total || 0, event.currency)}</span>
                      </div>
                    ))}
                    {event.items.length > 4 && (
                      <p className="text-xs text-muted-foreground px-3">+{event.items.length - 4} more items</p>
                    )}
                  </div>
                </div>
              )}

              {/* Change Request Thread — always attempt render, component handles empty state */}
              {event.status !== 'Draft' && (
                <ChangeRequestThread
                  entityType={event.type?.toLowerCase() || 'document'}
                  entityId={event.id}
                  buyerComment={event.changeComment}
                  preferredChangeRequestId={highlightChangeRequestId}
                  onPreferredMiss={highlightChangeRequestId ? onClearChangeRequestParam : undefined}
                />
              )}

              {/* Document Actions */}
              <div className="flex gap-2">
                {event.hasSourcePdf && (
                  <Button
                    variant="outline"
                    size="sm"
                    className="flex-1"
                    onClick={(e) => {
                      e.stopPropagation();
                      onPreviewPdf(event.id, event.title);
                    }}
                    data-testid={`preview-pdf-${event.id}`}
                  >
                    <Eye className="w-4 h-4 mr-2" />
                    View Document
                  </Button>
                )}
                <Button
                  variant="outline"
                  size="sm"
                  className="flex-1"
                  onClick={(e) => {
                    e.stopPropagation();
                    onDownloadPdf(event.id);
                  }}
                  data-testid={`download-pdf-${event.id}`}
                >
                  <Download className="w-4 h-4 mr-2" />
                  Download PDF
                </Button>
              </div>

              {/* Action Buttons for Quotes */}
              {isQuoteActionable && !showQuestionInput && (
                <div className="flex flex-col sm:flex-row gap-2 sm:gap-3 pt-2">
                  <Button
                    className="bg-emerald-600 hover:bg-emerald-700 text-white h-12 sm:h-12 text-sm sm:text-base flex-1 font-medium"
                    onClick={(e) => {
                      e.stopPropagation();
                      onAction(event.id, 'approve');
                    }}
                    data-testid={`approve-${event.id}`}
                  >
                    <CheckCircle className="w-5 h-5 mr-2" />
                    Approve Quote
                  </Button>
                  <Button
                    variant="destructive"
                    className="h-12 sm:h-12 text-sm sm:text-base flex-1 font-medium"
                    onClick={(e) => {
                      e.stopPropagation();
                      onAction(event.id, 'reject');
                    }}
                    data-testid={`reject-${event.id}`}
                  >
                    <XCircle className="w-5 h-5 mr-2" />
                    Decline
                  </Button>
                  <Button
                    variant="outline"
                    className="h-12 sm:h-12 text-sm sm:text-base flex-1 font-medium"
                    onClick={(e) => {
                      e.stopPropagation();
                      setShowQuestionInput(true);
                    }}
                    data-testid={`question-${event.id}`}
                  >
                    <MessageCircle className="w-5 h-5 mr-2" />
                    Ask Question
                  </Button>
                </div>
              )}

              {/* Question Input - works for both quotes and invoices */}
              {showQuestionInput && (
                <div className="space-y-3 pt-2">
                  <Textarea
                    placeholder="Type your question or request..."
                    value={question}
                    onChange={(e) => setQuestion(e.target.value)}
                    rows={3}
                    className="resize-none"
                    data-testid={`question-input-${event.id}`}
                  />
                  <div className="flex gap-2">
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => setShowQuestionInput(false)}
                      className="flex-1"
                    >
                      Cancel
                    </Button>
                    <Button
                      size="sm"
                      onClick={handleQuestionSubmit}
                      disabled={!question.trim() || isSubmitting}
                      className="flex-1"
                      data-testid={`send-question-${event.id}`}
                    >
                      {isSubmitting ? (
                        <Loader2 className="w-4 h-4 animate-spin" />
                      ) : (
                        <>
                          <Send className="w-4 h-4 mr-1.5" />
                          Send
                        </>
                      )}
                    </Button>
                  </div>
                </div>
              )}

              {/* Paid Invoice Display */}
              {needsPayment && !showQuestionInput && (
                <div className="pt-2 space-y-3">
                  <div className="flex flex-col sm:flex-row gap-2 sm:gap-3">
                    <Button
                      className="h-12 sm:h-12 bg-primary hover:bg-primary/90 flex-1 text-sm sm:text-base font-medium"
                      onClick={(e) => {
                        e.stopPropagation();
                        onShowQrPayment(event);
                      }}
                      data-testid={`qr-payment-${event.id}`}
                    >
                      <QrCode className="w-5 h-5 mr-2" />
                      Pay with QR
                    </Button>
                    <Button
                      variant="outline"
                      className="h-12 sm:h-12 flex-1 text-sm sm:text-base font-medium"
                      onClick={(e) => {
                        e.stopPropagation();
                        onAction(event.id, 'confirm_payment');
                      }}
                      data-testid={`confirm-payment-${event.id}`}
                    >
                      <CheckCircle className="w-5 h-5 mr-2" />
                      I've Paid
                    </Button>
                    <Button
                      variant="outline"
                      className="h-12 sm:h-12 flex-1 text-sm sm:text-base font-medium"
                      onClick={(e) => {
                        e.stopPropagation();
                        setShowQuestionInput(true);
                      }}
                      data-testid={`invoice-question-${event.id}`}
                    >
                      <MessageCircle className="w-5 h-5 mr-2" />
                      Question
                    </Button>
                  </div>
                  <p className="text-xs text-muted-foreground text-center">
                    Scan QR with your banking app, confirm after transfer, or ask a question
                  </p>
                </div>
              )}

              {/* Paid Invoice Display */}
              {isInvoice && event.status === 'Paid' && (
                <div className="flex items-center gap-2 p-3 bg-green-500/10 rounded-lg">
                  <CheckCircle className="w-5 h-5 text-green-600" />
                  <span className="text-sm font-medium text-green-700 dark:text-green-400">
                    Payment completed
                  </span>
                </div>
              )}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
};

// Construction Phase Card
const ConstructionPhaseCard = ({ stages }) => {
  const [expanded, setExpanded] = useState(false);
  
  if (!stages || stages.length === 0) return null;
  
  const completedCount = stages.filter(s => s.status === 'completed' || s.status === 'approved').length;
  const currentStage = stages.find(s => s.status === 'in_progress') || stages.find(s => s.status === 'pending');
  const progressPercent = stages.length > 0 ? Math.round((completedCount / stages.length) * 100) : 0;

  const API_BASE = process.env.REACT_APP_BACKEND_URL;

  return (
    <Card className="mb-6 overflow-hidden">
      <CardContent className="p-0">
        <div 
          className="p-4 cursor-pointer bg-muted/30"
          onClick={() => setExpanded(!expanded)}
          data-testid="construction-progress-header"
        >
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-xl bg-primary/10 flex items-center justify-center">
                <HardHat className="w-5 h-5 text-primary" />
              </div>
              <div>
                <p className="text-xs text-muted-foreground uppercase tracking-wider font-medium">Construction Progress</p>
                <p className="font-semibold text-foreground">
                  {currentStage ? currentStage.name : 'All Complete'}
                </p>
              </div>
            </div>
            <div className="flex items-center gap-3">
              <div className="text-right">
                <p className="text-lg font-bold text-foreground">{progressPercent}%</p>
                <p className="text-xs text-muted-foreground">{completedCount}/{stages.length} stages</p>
              </div>
              {expanded ? (
                <ChevronUp className="w-5 h-5 text-muted-foreground" />
              ) : (
                <ChevronDown className="w-5 h-5 text-muted-foreground" />
              )}
            </div>
          </div>
          
          <div className="mt-3 h-2 bg-muted rounded-full overflow-hidden">
            <div 
              className="h-full bg-primary rounded-full transition-all duration-500"
              style={{ width: `${progressPercent}%` }}
            />
          </div>
        </div>

        {expanded && (
          <div className="border-t border-border p-4 space-y-3 animate-fade-in">
            {stages.map((stage, idx) => {
              const isCompleted = stage.status === 'completed' || stage.status === 'approved';
              const isCurrent = stage.status === 'in_progress';
              const isPending = stage.status === 'pending';
              
              return (
                <div 
                  key={stage.step_id} 
                  className={cn(
                    "p-3 rounded-lg border",
                    isCurrent && "bg-primary/5 border-primary/30",
                    isCompleted && "bg-emerald-500/5 border-emerald-500/20",
                    isPending && "bg-muted/30 border-border"
                  )}
                  data-testid={`construction-stage-${stage.step_id}`}
                >
                  <div className="flex items-start gap-3">
                    <div className={cn(
                      "w-8 h-8 rounded-full flex items-center justify-center flex-shrink-0 mt-0.5",
                      isCompleted && "bg-emerald-500 text-white",
                      isCurrent && "bg-primary text-primary-foreground",
                      isPending && "bg-muted text-muted-foreground"
                    )}>
                      {isCompleted ? (
                        <CheckCircle className="w-4 h-4" />
                      ) : isCurrent ? (
                        <Clock className="w-4 h-4" />
                      ) : (
                        <span className="text-xs font-bold">{idx + 1}</span>
                      )}
                    </div>
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2">
                        <span className="font-medium text-foreground">{stage.title}</span>
                        {isCurrent && (
                          <span className="text-[10px] font-semibold uppercase tracking-wider px-2 py-0.5 rounded-full bg-primary text-primary-foreground">
                            In Progress
                          </span>
                        )}
                        {isCompleted && (
                          <span className="text-[10px] font-semibold uppercase tracking-wider px-2 py-0.5 rounded-full bg-emerald-500/10 text-emerald-600">
                            Complete
                          </span>
                        )}
                      </div>
                      {stage.description && (
                        <p className="text-sm text-muted-foreground mt-1">{stage.description}</p>
                      )}
                      
                      {/* Dates */}
                      <div className="flex items-center gap-4 mt-2 text-xs text-muted-foreground">
                        {stage.planned_date && (
                          <span className="flex items-center gap-1">
                            <Calendar className="w-3 h-3" />
                            {isPending ? 'Planned' : 'Target'}: {new Date(stage.planned_date).toLocaleDateString('en-GB', { day: 'numeric', month: 'short' })}
                          </span>
                        )}
                        {stage.completed_at && (
                          <span className="flex items-center gap-1 text-emerald-600">
                            <CheckCircle className="w-3 h-3" />
                            Done: {new Date(stage.completed_at).toLocaleDateString('en-GB', { day: 'numeric', month: 'short' })}
                          </span>
                        )}
                      </div>
                      
                      {/* Linked documents - only for current and completed stages */}
                      {(isCurrent || isCompleted) && stage.documents && stage.documents.length > 0 && (
                        <div className="mt-3 flex flex-wrap gap-2">
                          {stage.documents.map(doc => (
                            <a
                              key={doc.activity_id}
                              href={doc.file_url ? `${API_BASE}${doc.file_url}` : '#'}
                              target="_blank"
                              rel="noopener noreferrer"
                              className="flex items-center gap-1.5 px-2 py-1 bg-background border border-border rounded text-xs hover:border-primary/50 transition-colors"
                            >
                              <FileText className="w-3 h-3 text-muted-foreground" />
                              <span className="truncate max-w-[120px]">{doc.title || doc.file_name || 'Document'}</span>
                              {doc.file_url && <Download className="w-3 h-3 text-primary" />}
                            </a>
                          ))}
                        </div>
                      )}
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </CardContent>
    </Card>
  );
};

// Vault Document Card for Buyers
const VaultDocumentCard = ({ document, onPreview, onDownload }) => {
  const categoryLabel = String(document.category || 'other')
    .replace(/_/g, ' ')
    .replace(/\b\w/g, (c) => c.toUpperCase());

  const getCategoryColor = (category) => {
    const colors = {
      'Architect Plans': 'bg-blue-500/10 text-blue-600 dark:text-blue-400 border-blue-500/20',
      'Contracts': 'bg-purple-500/10 text-purple-600 dark:text-purple-400 border-purple-500/20',
      'Plans': 'bg-blue-500/10 text-blue-600 dark:text-blue-400 border-blue-500/20',
      'Permits': 'bg-amber-500/10 text-amber-600 dark:text-amber-400 border-amber-500/20',
      'Reports': 'bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border-emerald-500/20',
      'Other': 'bg-gray-500/10 text-gray-600 dark:text-gray-400 border-gray-500/20',
    };
    return colors[category] || colors['Other'];
  };

  const getDocTypeIcon = (docType) => {
    if (docType === 'action_required') {
      return <AlertTriangle className="w-4 h-4 text-amber-500" />;
    }
    return <FileCheck className="w-4 h-4 text-emerald-500" />;
  };

  const getFileIcon = (fileType, filename) => {
    // Check by mime type first
    if (fileType?.includes('pdf')) return <FileText className="w-5 h-5" />;
    if (fileType?.includes('image')) return <ImageIcon className="w-5 h-5" />;
    if (fileType?.includes('word') || fileType?.includes('document')) return <FileText className="w-5 h-5" />;
    if (fileType?.includes('sheet') || fileType?.includes('excel')) return <FileSpreadsheet className="w-5 h-5" />;
    
    // Fallback to extension
    const ext = (filename || '').split('.').pop()?.toLowerCase();
    if (['pdf'].includes(ext)) return <FileText className="w-5 h-5" />;
    if (['jpg', 'jpeg', 'png', 'gif', 'webp', 'svg'].includes(ext)) return <ImageIcon className="w-5 h-5" />;
    if (['doc', 'docx'].includes(ext)) return <FileText className="w-5 h-5" />;
    if (['xls', 'xlsx', 'csv'].includes(ext)) return <FileSpreadsheet className="w-5 h-5" />;
    return <File className="w-5 h-5" />;
  };

  const formatFileSize = (bytes) => {
    if (!bytes) return '';
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  };

  const isArchitectPlan = document.is_architect_plan || document.doc_type === 'architect_plan' || document.category === 'architect_plans';
  const isPdf = document.content_type?.includes('pdf') || (document.original_filename || '').toLowerCase().endsWith('.pdf');
  const isImage = document.content_type?.includes('image') || ['jpg', 'jpeg', 'png', 'gif', 'webp', 'svg'].includes((document.original_filename || '').split('.').pop()?.toLowerCase());
  // Same URL rule as Download: only a public `document.url` can be embedded inline (no second fetch path).
  const architectInlineSrc =
    document.url && String(document.url).startsWith('http') ? document.url : null;

  return (
    <Card 
      className={cn(
        "overflow-hidden transition-all duration-200 hover:shadow-md mb-3",
        document.doc_type === 'action_required' && "ring-1 ring-amber-500/30",
        isArchitectPlan && "ring-1 ring-blue-500/30"
      )}
      data-testid={`vault-doc-${document.vault_id}`}
    >
      <CardContent className="p-3 sm:p-4">
        <div className="flex items-start gap-3 sm:gap-4">
          {/* File Icon */}
          <div className={cn(
            "w-10 h-10 sm:w-12 sm:h-12 rounded-xl flex items-center justify-center flex-shrink-0",
            document.doc_type === 'action_required' 
              ? "bg-amber-500/10 text-amber-600"
              : "bg-primary/10 text-primary"
          )}>
            {getFileIcon(document.file_type, document.original_filename)}
          </div>
          
          {/* Content */}
          <div className="flex-1 min-w-0">
            <div className="flex flex-col sm:flex-row sm:items-start sm:justify-between gap-1 sm:gap-2">
              <div className="min-w-0 flex-1">
                {/* Document title - full display, wraps on mobile */}
                <h3 className="font-medium text-foreground text-sm sm:text-base leading-tight break-words" title={document.name || document.original_filename}>
                  {document.name || document.original_filename || 'Untitled Document'}
                </h3>
                <div className="flex items-center gap-2 mt-1.5 flex-wrap">
                  <span className={cn(
                    "inline-flex items-center px-2 py-0.5 text-[10px] font-semibold rounded-full border uppercase tracking-wider",
                    getCategoryColor(categoryLabel)
                  )}>
                    {categoryLabel}
                  </span>
                  <span className="flex items-center gap-1 text-[10px] sm:text-xs text-muted-foreground">
                    {getDocTypeIcon(document.doc_type)}
                    <span className="hidden xs:inline">{document.doc_type === 'action_required' ? 'Action Required' : 'General'}</span>
                  </span>
                  {isArchitectPlan && (
                    <span className="inline-flex items-center px-2 py-0.5 text-[10px] font-semibold rounded-full border uppercase tracking-wider bg-blue-500/10 text-blue-600 dark:text-blue-400 border-blue-500/20">
                      Architect Plan
                    </span>
                  )}
                </div>
              </div>
            </div>
            
            {/* Notes */}
            {document.notes && (
              <p className="text-xs sm:text-sm text-muted-foreground mt-2 line-clamp-2">{document.notes}</p>
            )}

            {isArchitectPlan && (isPdf || isImage) && architectInlineSrc && (
              <div className="mt-3 rounded-lg border border-border overflow-hidden bg-muted/20">
                {isImage ? (
                  <img
                    src={architectInlineSrc}
                    alt={document.title || 'Architect plan'}
                    className="w-full h-[62vh] object-contain bg-black/5"
                  />
                ) : (
                  <iframe
                    src={`${architectInlineSrc}#toolbar=0&navpanes=0`}
                    title={document.title || 'Architect plan preview'}
                    className="w-full h-[62vh] border-0"
                  />
                )}
              </div>
            )}
            
            {/* Meta & Actions */}
            <div className="flex flex-col xs:flex-row items-start xs:items-center justify-between gap-2 mt-3 pt-3 border-t border-border/50">
              <div className="flex items-center gap-2 sm:gap-3 text-[10px] sm:text-xs text-muted-foreground">
                <span className="flex items-center gap-1">
                  <Calendar className="w-3 h-3" />
                  {formatDate(document.created_at)}
                </span>
                {document.file_size && (
                  <span>{formatFileSize(document.file_size)}</span>
                )}
              </div>
              <div className="flex items-center gap-1 sm:gap-2 w-full xs:w-auto">
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => onPreview(document)}
                  className="h-8 px-2 sm:px-3 flex-1 xs:flex-initial text-xs"
                  data-testid={`preview-vault-doc-${document.vault_id}`}
                >
                  <Eye className="w-3 h-3 sm:w-4 sm:h-4 mr-1" />
                  {isArchitectPlan ? 'Fullscreen' : 'View'}
                </Button>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => onDownload(document)}
                  className="h-8 px-2 sm:px-3 flex-1 xs:flex-initial text-xs"
                  data-testid={`download-vault-doc-${document.vault_id}`}
                >
                  <Download className="w-3 h-3 sm:w-4 sm:h-4 mr-1" />
                  Download
                </Button>
              </div>
            </div>
          </div>
        </div>
      </CardContent>
    </Card>
  );
};

// QR Payment Modal
const QrPaymentModal = ({ isOpen, onClose, invoice, qrData, loading }) => {
  const copyToClipboard = (text, label) => {
    navigator.clipboard.writeText(text);
    toast.success(`${label} copied to clipboard`);
  };

  return (
    <Dialog open={isOpen} onOpenChange={onClose}>
      <DialogContent className="max-w-md">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <QrCode className="w-5 h-5 text-primary" />
            Swiss QR Payment
          </DialogTitle>
          <DialogDescription>
            Scan with your banking app to pay
          </DialogDescription>
        </DialogHeader>

        {loading ? (
          <div className="flex items-center justify-center py-12">
            <Loader2 className="w-8 h-8 animate-spin text-primary" />
          </div>
        ) : qrData ? (
          <div className="space-y-4">
            {/* QR Code Display */}
            <div className="flex justify-center p-4 bg-white rounded-lg">
              <img 
                src={`data:image/svg+xml;base64,${qrData.qr_code_svg_base64}`}
                alt="Swiss QR Payment Code"
                className="w-64 h-64"
              />
            </div>

            {/* Payment Details */}
            <div className="space-y-3 p-4 bg-muted/50 rounded-lg">
              <div className="flex items-center justify-between">
                <span className="text-sm text-muted-foreground">Amount</span>
                <span className="font-bold text-lg">{formatCurrency(qrData.amount, qrData.currency)}</span>
              </div>
              
              <div className="flex items-center justify-between">
                <span className="text-sm text-muted-foreground">Reference</span>
                <div className="flex items-center gap-2">
                  <span className="font-mono text-sm">{qrData.document_number}</span>
                  <Button
                    variant="ghost"
                    size="icon"
                    className="h-6 w-6"
                    onClick={() => copyToClipboard(qrData.document_number, 'Reference')}
                  >
                    <Copy className="w-3 h-3" />
                  </Button>
                </div>
              </div>
              
              <div className="pt-2 border-t border-border">
                <p className="text-xs text-muted-foreground mb-1">Beneficiary</p>
                <p className="text-sm font-medium">{qrData.payment_info?.beneficiary}</p>
              </div>
              
              <div>
                <p className="text-xs text-muted-foreground mb-1">IBAN</p>
                <div className="flex items-center gap-2">
                  <span className="font-mono text-sm">{qrData.payment_info?.iban}</span>
                  <Button
                    variant="ghost"
                    size="icon"
                    className="h-6 w-6"
                    onClick={() => copyToClipboard(qrData.payment_info?.iban, 'IBAN')}
                  >
                    <Copy className="w-3 h-3" />
                  </Button>
                </div>
              </div>
            </div>

            <p className="text-xs text-muted-foreground text-center">
              Open your banking app, scan this QR code, and confirm the payment
            </p>
          </div>
        ) : (
          <div className="text-center py-8">
            <p className="text-muted-foreground">Failed to load QR code</p>
          </div>
        )}

        <DialogFooter>
          <Button variant="outline" onClick={onClose} className="w-full">
            Close
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
};

// Main Buyer Timeline Page
export const BuyerTimeline = () => {
  const { user, logout } = useAuth();
  const { getLogo, getCompanyName, t } = useSettings();
  const [searchParams, setSearchParams] = useSearchParams();
  const rawTab = searchParams.get('tab') || 'all';
  const legacyMappedFilter = mapLegacyTabToFilter(rawTab);
  const feedFilter = FEED_FILTERS.some((f) => f.key === rawTab) ? rawTab : (legacyMappedFilter || 'all');
  const deepLinkHandled = useRef(new Set());
  const setFeedFilter = useCallback((nextFilter) => {
    setSearchParams((prev) => {
      const next = new URLSearchParams(prev);
      next.set('tab', nextFilter);
      ['document_id', 'vault_document_id', 'activity_id', 'decision_id', 'milestone_step_id', 'change_request_id'].forEach((k) => next.delete(k));
      return next;
    }, { replace: true });
  }, [setSearchParams]);
  const clearChangeRequestParam = useCallback(() => {
    setSearchParams((prev) => {
      const next = new URLSearchParams(prev);
      next.delete('change_request_id');
      return next;
    }, { replace: true });
  }, [setSearchParams]);
  const documentId = searchParams.get('document_id');
  const vaultDocumentId = searchParams.get('vault_document_id');
  const milestoneStepId = searchParams.get('milestone_step_id');
  const decisionIdFromUrl = searchParams.get('decision_id');
  const activityIdFromUrl = searchParams.get('activity_id');
  const changeRequestIdFromUrl = searchParams.get('change_request_id');
  const [loading, setLoading] = useState(true);
  const [events, setEvents] = useState([]);
  const [projectInfo, setProjectInfo] = useState(null);
  const [stages, setStages] = useState([]);
  const [confirmDialog, setConfirmDialog] = useState({ open: false, type: null, eventId: null });
  const [isProcessing, setIsProcessing] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');
  const [showSearch, setShowSearch] = useState(false);
  const [unreadCount, setUnreadCount] = useState(0);
  const [teamMembers, setTeamMembers] = useState([]);
  const [constructionTimeline, setConstructionTimeline] = useState(null);
  const [buyerActivities, setBuyerActivities] = useState([]);
  const [vaultDocuments, setVaultDocuments] = useState([]);
  const [buyerDecisions, setBuyerDecisions] = useState([]);
  
  // PDF Viewer state
  const [pdfViewer, setPdfViewer] = useState({ open: false, url: '', filename: '' });

  // Get agent branding
  const logoUrl = getLogo();
  const companyName = getCompanyName();
  
  // QR Payment Modal
  const [qrModal, setQrModal] = useState({ open: false, invoice: null, qrData: null, loading: false });

  const fetchData = useCallback(async () => {
    try {
      const portalRes = await fetch(`${API}/buyer/portal`, { credentials: 'include', headers: getAuthHeaders() });
      
      if (portalRes.ok) {
        const portal = await portalRes.json();

        // Documents
        setEvents(portal.documents || []);
        
        // Project info
        setProjectInfo(portal.project);
        
        // Construction timeline + stages
        if (portal.construction_timeline) {
          setConstructionTimeline(portal.construction_timeline);
          if (portal.construction_timeline.steps?.length > 0) {
            setStages(portal.construction_timeline.steps.map(step => ({
              step_id: step.step_id,
              title: step.title,
              status: normalizeTimelineStatus(step.status),
              description: step.description,
              planned_date: step.planned_date,
              completed_at: step.completed_at,
              documents: step.documents
            })));
          }
        }
        
        // Team
        setTeamMembers(portal.team || []);
        
        // Buyer activities (agent feed posts)
        setBuyerActivities(portal.activities || []);
        
        // Unread count
        setUnreadCount(portal.unread_count || 0);
        
        // Decisions
        setBuyerDecisions(portal.decisions || []);
        
        // Vault
        setVaultDocuments(sortVaultDocuments(portal.vault_files || []));
      }
    } catch (error) {
      console.error('Failed to fetch portal data:', error);
      toast.error('Failed to load timeline');
    } finally {
      setLoading(false);
    }
  }, []);

  // WebSocket: refresh portal when quotes/invoices or vault change on the agent side
  const handleWebSocketMessage = useCallback((message) => {
    if (
      message.type === 'document_sent' ||
      message.type === 'vault_updated' ||
      message.type === 'vault_shared' ||
      message.type === 'decision_updated'
    ) {
      fetchData();
    }
  }, [fetchData]);

  useWebSocket(user?.user_id, handleWebSocketMessage);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  // Helper: send action through sync layer, get fresh portal state
  const portalAction = async (actionData) => {
    const res = await fetch(`${API}/buyer/portal/action`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', ...getAuthHeaders() },
      credentials: 'include',
      body: JSON.stringify(actionData)
    });
    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.message || err.detail || 'Action failed');
    }
    // Response is the updated portal — refresh all state
    const portal = await res.json();
    setEvents(portal.documents || []);
    setProjectInfo(portal.project);
    setVaultDocuments(sortVaultDocuments(portal.vault_files || []));
    setBuyerDecisions(portal.decisions || []);
    setUnreadCount(portal.unread_count || 0);
    setTeamMembers(portal.team || []);
    setBuyerActivities(portal.activities || []);
    return portal;
  };

  // Mark activities as seen when viewing Updates filter
  useEffect(() => {
    if (feedFilter === 'updates') {
      portalAction({ action: 'mark_seen' }).catch(() => {});
    }
    if (feedFilter === 'vault' || feedFilter === 'decisions') {
      fetchData();
    }
  }, [feedFilter, fetchData]);

  useEffect(() => {
    const handler = (e) => {
      const d = e.detail || {};
      setSearchParams((prev) => {
        const next = new URLSearchParams(prev);
        Object.entries(d).forEach(([k, v]) => {
          if (v != null && v !== '') next.set(k, String(v));
        });
        return next;
      }, { replace: true });
    };
    window.addEventListener('navigate-tab', handler);
    return () => window.removeEventListener('navigate-tab', handler);
  }, [setSearchParams]);

  useEffect(() => {
    if (loading || !decisionIdFromUrl) return;
    if (feedFilter !== 'decisions' || buyerDecisions.length === 0) return;
    const ok = buyerDecisions.some((d) => d.decision_id === decisionIdFromUrl);
    if (!ok) {
      const k = `nodec-${decisionIdFromUrl}`;
      if (!deepLinkHandled.current.has(k)) {
        deepLinkHandled.current.add(k);
        toast.error('This decision is no longer available');
        setSearchParams((prev) => {
          const n = new URLSearchParams(prev);
          n.delete('decision_id');
          return n;
        }, { replace: true });
      }
    }
  }, [loading, decisionIdFromUrl, feedFilter, buyerDecisions, setSearchParams]);

  useEffect(() => {
    if (loading) return;

    const run = () => {
      if (documentId && ['all', 'quotes', 'invoices'].includes(feedFilter)) {
        const exists = events.some((e) => e.id === documentId);
        const el = document.querySelector(`[data-testid="timeline-event-${documentId}"]`);
        if (el) {
          el.scrollIntoView({ behavior: 'smooth', block: 'center' });
          el.classList.add('ring-2', 'ring-primary', 'ring-offset-2');
          setTimeout(() => el.classList.remove('ring-2', 'ring-primary', 'ring-offset-2'), 2000);
        } else if (events.length > 0 && !exists) {
          const k = `nodoc-${documentId}`;
          if (!deepLinkHandled.current.has(k)) {
            deepLinkHandled.current.add(k);
            toast.error('This document is no longer available');
            setSearchParams((prev) => {
              const n = new URLSearchParams(prev);
              n.delete('document_id');
              return n;
            }, { replace: true });
          }
        }
      }
      if (vaultDocumentId && feedFilter === 'vault' && vaultDocuments.length > 0) {
        const match = vaultDocuments.find(
          (d) => d.vault_id === vaultDocumentId || d.vault_document_id === vaultDocumentId
        );
        if (match) {
          const el = document.querySelector(`[data-testid="vault-doc-${match.vault_id}"]`);
          if (el) {
            el.scrollIntoView({ behavior: 'smooth', block: 'center' });
            el.classList.add('ring-2', 'ring-primary', 'ring-offset-2');
            setTimeout(() => el.classList.remove('ring-2', 'ring-primary', 'ring-offset-2'), 2000);
          }
        } else {
          const k = `novault-${vaultDocumentId}`;
          if (!deepLinkHandled.current.has(k)) {
            deepLinkHandled.current.add(k);
            toast.error('This file is no longer shared with you');
            setSearchParams((prev) => {
              const n = new URLSearchParams(prev);
              n.delete('vault_document_id');
              return n;
            }, { replace: true });
          }
        }
      }
      if (milestoneStepId && stages.length > 0) {
        const exists = stages.some((s) => s.step_id === milestoneStepId);
        const el = document.querySelector(`[data-testid="construction-stage-${milestoneStepId}"]`);
        if (el) {
          el.scrollIntoView({ behavior: 'smooth', block: 'center' });
          el.classList.add('ring-2', 'ring-primary', 'ring-offset-2');
          setTimeout(() => el.classList.remove('ring-2', 'ring-primary', 'ring-offset-2'), 2000);
        } else if (!exists) {
          const k = `nomile-${milestoneStepId}`;
          if (!deepLinkHandled.current.has(k)) {
            deepLinkHandled.current.add(k);
            toast.error('This milestone is no longer on your timeline');
            setSearchParams((prev) => {
              const n = new URLSearchParams(prev);
              n.delete('milestone_step_id');
              return n;
            }, { replace: true });
          }
        }
      }
    };

    const id = requestAnimationFrame(run);
    return () => cancelAnimationFrame(id);
  }, [
    loading,
    feedFilter,
    documentId,
    vaultDocumentId,
    milestoneStepId,
    events,
    vaultDocuments,
    stages,
    setSearchParams,
  ]);

  const handleAction = async (eventId, action, comment = null) => {
    if (action === 'approve' || action === 'reject') {
      setConfirmDialog({ open: true, type: action, eventId });
      return;
    }
    if (action === 'confirm_payment') {
      setConfirmDialog({ open: true, type: 'payment', eventId });
      return;
    }
    if (action === 'request_change' && comment) {
      setIsProcessing(true);
      try {
        await portalAction({ action: 'request_change', document_id: eventId, comment });
        toast.success('Question sent to your agent');
      } catch (error) {
        toast.error(error.message || 'Failed to send question');
      } finally {
        setIsProcessing(false);
      }
    }
  };

  const confirmAction = async () => {
    const { type, eventId } = confirmDialog;
    setIsProcessing(true);
    try {
      const actionName = type === 'payment' ? 'confirm_payment' : type;
      await portalAction({ action: actionName, document_id: eventId });
      const messages = { 'approve': 'Quote approved! Invoice will be generated.', 'reject': 'Quote declined', 'payment': 'Payment confirmed' };
      toast.success(messages[type] || 'Action completed');
    } catch (error) {
      toast.error(error.message || 'Action failed. Please try again.');
    } finally {
      setIsProcessing(false);
      setConfirmDialog({ open: false, type: null, eventId: null });
    }
  };

  const handleDownloadPdf = async (documentId) => {
    try {
      // Use source-pdf endpoint to download the original uploaded PDF
      const res = await fetch(`${API}/documents/${documentId}/source-pdf`, { credentials: 'include', headers: getAuthHeaders() });
      
      if (res.ok) {
        const blob = await res.blob();
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `document_${documentId}.pdf`;
        // Required for Safari and mobile browsers
        a.style.display = 'none';
        document.body.appendChild(a);
        a.click();
        // Cleanup
        setTimeout(() => {
          document.body.removeChild(a);
          window.URL.revokeObjectURL(url);
        }, 100);
      } else {
        throw new Error('Download failed');
      }
    } catch (error) {
      toast.error('Failed to download PDF');
    }
  };

  const handlePreviewPdf = (documentId, documentTitle) => {
    // Open the PDF in the in-app viewer
    setPdfViewer({
      open: true,
      url: `${API}/documents/${documentId}/source-pdf`,
      filename: documentTitle ? `${documentTitle}.pdf` : `document_${documentId}.pdf`
    });
  };

  const handleShowQrPayment = async (invoice) => {
    setQrModal({ open: true, invoice, qrData: null, loading: true });
    
    try {
      const res = await fetch(`${API}/documents/${invoice.id}/qr-code`, { credentials: 'include', headers: getAuthHeaders() });
      
      if (res.ok) {
        const qrData = await res.json();
        setQrModal(prev => ({ ...prev, qrData, loading: false }));
      } else {
        const err = await res.json();
        throw new Error(err.detail || 'Failed to load QR code');
      }
    } catch (error) {
      toast.error(error.message || 'Failed to load QR code');
      setQrModal(prev => ({ ...prev, loading: false }));
    }
  };

  const vaultAuthDownloadUrl = (document) =>
    `${API}/vault/documents/${document.vault_document_id || document.vault_id}/download`;

  /**
   * Single code path for vault file access (same resolution as Download).
   * View = same flow; only the final browser action differs (new tab vs save).
   */
  const openVaultFileSameAsDownload = async (document, { openInNewTab }) => {
    const fileUrl = document.url;
    if (fileUrl && fileUrl.startsWith('http')) {
      if (openInNewTab) {
        window.open(fileUrl, '_blank', 'noopener,noreferrer');
      } else {
        const a = window.document.createElement('a');
        a.href = fileUrl;
        a.download = document.original_filename || document.name || 'document';
        a.target = '_blank';
        window.document.body.appendChild(a);
        a.click();
        window.document.body.removeChild(a);
      }
      return;
    }
    try {
      const res = await fetch(vaultAuthDownloadUrl(document), {
        credentials: 'include',
        headers: getAuthHeaders(),
      });
      if (!res.ok) {
        toast.error(openInNewTab ? 'Failed to open document' : 'Failed to download document');
        return;
      }
      const blob = await res.blob();
      const url = window.URL.createObjectURL(blob);
      if (openInNewTab) {
        window.open(url, '_blank', 'noopener,noreferrer');
        window.setTimeout(() => window.URL.revokeObjectURL(url), 120000);
      } else {
        const a = window.document.createElement('a');
        a.href = url;
        a.download = document.original_filename || document.name || 'document';
        a.style.display = 'none';
        window.document.body.appendChild(a);
        a.click();
        window.setTimeout(() => {
          window.document.body.removeChild(a);
          window.URL.revokeObjectURL(url);
        }, 100);
      }
    } catch {
      toast.error(openInNewTab ? 'Failed to open document' : 'Failed to download document');
    }
  };

  const handleVaultPreview = (document) => openVaultFileSameAsDownload(document, { openInNewTab: true });
  const handleVaultDownload = (document) => openVaultFileSameAsDownload(document, { openInNewTab: false });

  const currentPhase = useMemo(() => {
    if (!stages.length) return 'Not started';

    const inProgress = stages.find((s) => normalizeTimelineStatus(s.status) === 'in_progress');
    if (inProgress?.title) return inProgress.title;

    const pending = stages.find((s) => normalizeTimelineStatus(s.status) === 'pending');
    if (pending?.title) return pending.title;

    const allCompleted = stages.every((s) => normalizeTimelineStatus(s.status) === 'completed');
    return allCompleted ? 'Complete' : 'Not started';
  }, [stages]);

  const actionableDocuments = events.filter((e) => Boolean(e.actionRequired));
  const actionableDecisions = buyerDecisions.filter((d) => d?.buyer_status === 'pending');
  const pendingCount = actionableDocuments.length + actionableDecisions.length;

  const filteredEvents = events.filter(event => {
    if (!searchQuery.trim()) return true;
    const query = searchQuery.toLowerCase();
    return (
      event.title?.toLowerCase().includes(query) ||
      event.documentNumber?.toLowerCase().includes(query) ||
      event.status?.toLowerCase().includes(query) ||
      event.type?.toLowerCase().includes(query) ||
      event.supplierName?.toLowerCase().includes(query) ||
      event.summary?.toLowerCase().includes(query) ||
      formatDate(event.date)?.toLowerCase().includes(query) ||
      String(event.amount)?.includes(query)
    );
  });

  const filteredDocumentsForSearch = filteredEvents;
  const filteredVaultForSearch = vaultDocuments.filter((doc) => {
    if (!searchQuery.trim()) return true;
    const query = searchQuery.toLowerCase();
    return (
      doc.name?.toLowerCase().includes(query) ||
      doc.original_filename?.toLowerCase().includes(query) ||
      doc.category?.toLowerCase().includes(query) ||
      doc.notes?.toLowerCase().includes(query)
    );
  });
  const filteredDecisionsForSearch = buyerDecisions.filter((decision) => {
    if (!searchQuery.trim()) return true;
    const query = searchQuery.toLowerCase();
    return (
      decision.title?.toLowerCase().includes(query) ||
      decision.description?.toLowerCase().includes(query) ||
      decision.buyer_status?.toLowerCase().includes(query)
    );
  });
  const filteredActivitiesForSearch = buyerActivities.filter((activity) => {
    if (!searchQuery.trim()) return true;
    const query = searchQuery.toLowerCase();
    const body = getActivityBody(activity).toLowerCase();
    return (
      activity.author_name?.toLowerCase().includes(query) ||
      activity.file_name?.toLowerCase().includes(query) ||
      body.includes(query)
    );
  });

  const socialFeedItems = useMemo(() => {
    const entries = [];

    if (feedFilter === 'all' || feedFilter === 'quotes' || feedFilter === 'invoices') {
      filteredDocumentsForSearch.forEach((doc) => {
        const normalizedType = String(doc.type || '').toLowerCase();
        const kind = normalizedType === 'invoice' ? 'invoice' : 'quote';
        if (feedFilter === 'quotes' && kind !== 'quote') return;
        if (feedFilter === 'invoices' && kind !== 'invoice') return;
        entries.push({
          id: `document-${doc.id}`,
          kind,
          sortDate: doc.date || doc.created_at || doc.updated_at,
          payload: doc,
        });
      });
    }

    if (feedFilter === 'all' || feedFilter === 'vault') {
      filteredVaultForSearch.forEach((doc) => {
        entries.push({
          id: `vault-${doc.vault_id || doc.vault_document_id}`,
          kind: 'vault',
          sortDate: doc.created_at || doc.updated_at,
          payload: doc,
        });
      });
    }

    if (feedFilter === 'all' || feedFilter === 'decisions') {
      filteredDecisionsForSearch.forEach((decision) => {
        entries.push({
          id: `decision-${decision.decision_id}`,
          kind: 'decision',
          sortDate: decision.updated_at || decision.created_at || decision.deadline,
          payload: decision,
        });
      });
    }

    if (feedFilter === 'all' || feedFilter === 'updates') {
      filteredActivitiesForSearch.forEach((activity) => {
        entries.push({
          id: `activity-${activity.activity_id}`,
          kind: 'updates',
          sortDate: activity.created_at || activity.updated_at,
          payload: activity,
        });
      });
    }

    return entries.sort((a, b) => {
      const aTime = a.sortDate ? new Date(a.sortDate).getTime() : 0;
      const bTime = b.sortDate ? new Date(b.sortDate).getTime() : 0;
      return bTime - aTime;
    });
  }, [
    feedFilter,
    filteredDocumentsForSearch,
    filteredVaultForSearch,
    filteredDecisionsForSearch,
    filteredActivitiesForSearch,
  ]);

  const pendingDecisionCount = buyerDecisions.filter((d) => d.buyer_status === 'pending').length;
  const filterBadgeCounts = {
    all: socialFeedItems.length,
    quotes: filteredDocumentsForSearch.filter((d) => String(d.type || '').toLowerCase() !== 'invoice').length,
    invoices: filteredDocumentsForSearch.filter((d) => String(d.type || '').toLowerCase() === 'invoice').length,
    updates: unreadCount,
    vault: filteredVaultForSearch.length,
    decisions: pendingDecisionCount,
  };

  const renderFeedCard = (item) => {
    if (item.kind === 'updates') {
      return (
        <BuyerUpdateFeedCard
          key={item.id}
          activity={item.payload}
          highlight={searchParams.get('activity_id') === item.payload?.activity_id}
        />
      );
    }

    if (item.kind === 'vault') {
      return (
        <VaultDocumentCard
          key={item.id}
          document={item.payload}
          onPreview={handleVaultPreview}
          onDownload={handleVaultDownload}
        />
      );
    }

    if (item.kind === 'decision') {
      return (
        <DecisionFeedCard
          key={item.id}
          decision={item.payload}
          onRespond={async (decisionId, action, comment) => {
            try {
              await portalAction({ action: 'respond_decision', decision_id: decisionId, option_id: action, comment });
              toast.success(action === 'approved' ? 'Decision approved' : action === 'rejected' ? 'Decision declined' : 'Change request sent');
            } catch {
              toast.error('Failed to respond');
            }
          }}
          highlighted={decisionIdFromUrl === item.payload?.decision_id}
          preferredChangeRequestId={
            decisionIdFromUrl === item.payload?.decision_id
              ? changeRequestIdFromUrl
              : null
          }
          onPreferredMiss={clearChangeRequestParam}
        />
      );
    }

    if (item.kind === 'quote' || item.kind === 'invoice') {
      return (
        <TimelineCard
          key={item.id}
          event={item.payload}
          onAction={handleAction}
          onDownloadPdf={handleDownloadPdf}
          onPreviewPdf={handlePreviewPdf}
          onShowQrPayment={handleShowQrPayment}
          initialExpanded={!!(documentId === item.payload.id && changeRequestIdFromUrl)}
          highlightChangeRequestId={documentId === item.payload.id ? changeRequestIdFromUrl : null}
          onClearChangeRequestParam={clearChangeRequestParam}
        />
      );
    }

    return null;
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-background flex items-center justify-center">
        <div className="text-center">
          <Loader2 className="w-8 h-8 animate-spin text-primary mx-auto mb-4" />
          <p className="text-muted-foreground">Loading your timeline...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-background" data-testid="buyer-timeline">
      {/* Header */}
      <header className="sticky top-0 z-50 bg-background/80 backdrop-blur-xl border-b border-border">
        <div className="max-w-2xl mx-auto px-4 py-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              {logoUrl ? (
                <img 
                  src={logoUrl} 
                  alt={companyName} 
                  className="w-10 h-10 rounded-xl object-contain"
                />
              ) : (
                <div className="w-10 h-10 bg-primary rounded-xl flex items-center justify-center">
                  <Building2 className="w-5 h-5 text-primary-foreground" />
                </div>
              )}
              <div>
                <h1 className="font-semibold text-foreground">
                  {projectInfo?.name 
                    ? (projectInfo.unit_reference 
                      ? `${projectInfo.name} — ${projectInfo.unit_reference}` 
                      : projectInfo.name)
                    : (projectInfo?.unit_reference || t('buyer.yourProperty'))}
                </h1>
                <p className="text-sm text-muted-foreground">
                  {companyName}
                </p>
              </div>
            </div>
            <div className="flex items-center gap-2">
              <Button
                variant="ghost"
                size="icon"
                onClick={() => setShowSearch(!showSearch)}
                className="h-9 w-9 rounded-lg"
                data-testid="search-toggle-btn"
              >
                <Search className="w-4 h-4" />
              </Button>
              <NotificationCenter />
              <ThemeToggle />
              <Button
                variant="ghost"
                size="icon"
                onClick={logout}
                className="h-9 w-9 rounded-lg text-muted-foreground hover:text-destructive"
                data-testid="logout-btn"
              >
                <LogOut className="w-4 h-4" />
              </Button>
            </div>
          </div>
          
          {/* Search Bar */}
          {showSearch && (
            <div className="mt-4 animate-fade-in">
              <div className="relative">
                <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
                <Input
                  type="text"
                  placeholder="Search quotes, invoices, amounts..."
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  className="pl-10 pr-10 h-11 rounded-xl"
                  autoFocus
                  data-testid="search-input"
                />
                {searchQuery && (
                  <Button
                    variant="ghost"
                    size="icon"
                    className="absolute right-1 top-1/2 -translate-y-1/2 h-8 w-8"
                    onClick={() => setSearchQuery('')}
                  >
                    <X className="w-4 h-4" />
                  </Button>
                )}
              </div>
              {searchQuery && (
                <p className="text-xs text-muted-foreground mt-2">
                  {filteredEvents.length} result{filteredEvents.length !== 1 ? 's' : ''} found
                </p>
              )}
            </div>
          )}
        </div>
      </header>

      {/* Main Content */}
      <main className="max-w-2xl mx-auto px-4 py-6">
        {/* User greeting */}
        <div className="mb-6">
          <p className="text-sm text-muted-foreground">Welcome back, {user?.name?.split(' ')[0]}</p>
          <div className="flex items-center gap-2 mt-1">
            <span className="text-xs px-2 py-0.5 rounded-full bg-muted text-muted-foreground">
              Current phase: {currentPhase}
            </span>
            {pendingCount > 0 && (
              <button
                onClick={() => {
                  // Find first pending action across documents and decisions, then jump to it.
                  const actionableFeedItems = socialFeedItems.filter((item) => {
                    if (item.kind === 'decision') return item.payload?.buyer_status === 'pending';
                    if (item.kind === 'quote' || item.kind === 'invoice') return Boolean(item.payload?.actionRequired);
                    return false;
                  });
                  if (!actionableFeedItems.length) return;

                  const first = actionableFeedItems[0];
                  const selector = first.kind === 'decision'
                    ? `[data-testid="feed-card-decision-${first.payload?.decision_id}"]`
                    : `[data-testid="timeline-event-${first.payload?.id}"]`;
                  const el = document.querySelector(selector);
                  if (el) {
                    el.scrollIntoView({ behavior: 'smooth', block: 'center' });
                    el.classList.add('ring-2', 'ring-primary', 'ring-offset-2');
                    setTimeout(() => el.classList.remove('ring-2', 'ring-primary', 'ring-offset-2'), 2000);
                  }
                }}
                className="text-xs px-2 py-0.5 rounded-full bg-primary text-primary-foreground font-medium hover:bg-primary/90 transition-colors cursor-pointer"
                data-testid="action-needed-badge"
              >
                {pendingCount} pending action{pendingCount > 1 ? 's' : ''}
              </button>
            )}
          </div>
        </div>

        {/* Construction Progress */}
        <ConstructionPhaseCard stages={stages} />

        {/* Unified social feed filters */}
        <div className="mb-4">
          <div className="flex gap-2 overflow-x-auto pb-1">
            {FEED_FILTERS.map((filter) => {
              const Icon = filter.icon;
              const isActive = feedFilter === filter.key;
              return (
                <button
                  key={filter.key}
                  onClick={() => setFeedFilter(filter.key)}
                  className={cn(
                    'inline-flex items-center gap-2 px-3 py-2 rounded-full text-sm font-medium border whitespace-nowrap transition-colors',
                    isActive
                      ? 'bg-primary text-primary-foreground border-primary'
                      : 'bg-background text-muted-foreground border-border hover:text-foreground'
                  )}
                  data-testid={`tab-${filter.key}`}
                >
                  <Icon className="w-4 h-4" />
                  {filter.label}
                </button>
              );
            })}
          </div>
        </div>

        {/* Unified social feed stack */}
        <div className="space-y-4" data-testid="buyer-social-feed">
          {socialFeedItems.length === 0 ? (
            <Card className="text-center py-12">
              <CardContent>
                <FileText className="w-12 h-12 text-muted-foreground/30 mx-auto mb-4" />
                <p className="text-muted-foreground">
                  {searchQuery ? 'No matching items' : 'No feed items yet'}
                </p>
                <p className="text-sm text-muted-foreground mt-1">
                  {searchQuery
                    ? 'Try another search term or filter'
                    : 'Updates, quotes, invoices, decisions, and shared files will appear here'}
                </p>
              </CardContent>
            </Card>
          ) : (
            socialFeedItems.map((item) => renderFeedCard(item))
          )}
        </div>
      </main>

      {/* Confirmation Dialog */}
      <Dialog open={confirmDialog.open} onOpenChange={(open) => !open && setConfirmDialog({ open: false, type: null, eventId: null })}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>
              {confirmDialog.type === 'approve' && 'Approve this quote?'}
              {confirmDialog.type === 'reject' && 'Decline this quote?'}
              {confirmDialog.type === 'payment' && 'Confirm payment?'}
            </DialogTitle>
            <DialogDescription>
              {confirmDialog.type === 'approve' && 'Once approved, your agent will generate an invoice for payment.'}
              {confirmDialog.type === 'reject' && 'This will decline the upgrade proposal. You can request changes instead if needed.'}
              {confirmDialog.type === 'payment' && 'Please confirm you have completed the bank transfer. Your agent will verify the payment.'}
            </DialogDescription>
          </DialogHeader>
          <DialogFooter className="flex-col sm:flex-row gap-2">
            <Button
              variant="outline"
              onClick={() => setConfirmDialog({ open: false, type: null, eventId: null })}
              disabled={isProcessing}
            >
              Cancel
            </Button>
            <Button
              onClick={confirmAction}
              disabled={isProcessing}
              className={cn(
                confirmDialog.type === 'reject' && "bg-destructive hover:bg-destructive/90",
                confirmDialog.type === 'approve' && "bg-emerald-600 hover:bg-emerald-700"
              )}
            >
              {isProcessing ? (
                <Loader2 className="w-4 h-4 animate-spin" />
              ) : (
                <>
                  {confirmDialog.type === 'approve' && 'Yes, Approve'}
                  {confirmDialog.type === 'reject' && 'Yes, Decline'}
                  {confirmDialog.type === 'payment' && 'Confirm Payment'}
                </>
              )}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* QR Payment Modal */}
      <QrPaymentModal
        isOpen={qrModal.open}
        onClose={() => setQrModal({ open: false, invoice: null, qrData: null, loading: false })}
        invoice={qrModal.invoice}
        qrData={qrModal.qrData}
        loading={qrModal.loading}
      />

      {/* PDF Viewer Modal */}
      <PdfViewer
        isOpen={pdfViewer.open}
        onClose={() => setPdfViewer({ open: false, url: '', filename: '' })}
        url={pdfViewer.url}
        filename={pdfViewer.filename}
      />
    </div>
  );
};
