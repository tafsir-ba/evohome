import { useState, useEffect, useRef } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from './ui/card';
import { Button } from './ui/button';
import { Textarea } from './ui/textarea';
import { Badge } from './ui/badge';
import { toast } from 'sonner';
import { cn } from '../lib/utils';
import {
  MessageSquare,
  Send,
  CheckCircle,
  AlertCircle,
  Clock,
  User,
  Loader2,
  ChevronDown,
  ChevronUp,
  XCircle,
} from 'lucide-react';

const API = process.env.REACT_APP_BACKEND_URL + '/api';

const getAuthHeaders = () => {
  const token = localStorage.getItem('auth_token');
  return token ? { 'Authorization': `Bearer ${token}` } : {};
};

const STATUS_CONFIG = {
  open: { label: 'Open', color: 'bg-amber-500/10 text-amber-700 border-amber-500/30', icon: AlertCircle },
  under_review: { label: 'Under Review', color: 'bg-blue-500/10 text-blue-700 border-blue-500/30', icon: Clock },
  resolved: { label: 'Resolved', color: 'bg-emerald-500/10 text-emerald-700 border-emerald-500/30', icon: CheckCircle },
  closed: { label: 'Closed', color: 'bg-muted text-muted-foreground border-border', icon: XCircle },
};

/**
 * ChangeRequestPanel — displays change requests for any entity.
 * Used on invoice detail, quote detail, and future decision detail pages.
 */
export const ChangeRequestPanel = ({
  entityType,
  entityId,
  isAgent = true,
  highlightChangeRequestId = null,
  onHighlightConsumed = null,
}) => {
  const [changeRequests, setChangeRequests] = useState([]);
  const [loading, setLoading] = useState(true);
  const [replyText, setReplyText] = useState('');
  const [replyingTo, setReplyingTo] = useState(null);
  const [sending, setSending] = useState(false);
  const [expanded, setExpanded] = useState({});
  const highlightDone = useRef(null);

  const fetchChangeRequests = async () => {
    try {
      const res = await fetch(
        `${API}/change-requests/entity/${entityType}/${entityId}`,
        { credentials: 'include', headers: getAuthHeaders() }
      );
      if (res.ok) {
        const data = await res.json();
        setChangeRequests(data.change_requests || []);
        // Auto-expand open ones
        const exp = {};
        (data.change_requests || []).forEach(cr => {
          if (cr.status === 'open' || cr.status === 'under_review') {
            exp[cr.change_request_id] = true;
          }
        });
        setExpanded(prev => ({ ...prev, ...exp }));
      }
    } catch (error) {
      console.error('Failed to fetch change requests:', error);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (entityType && entityId) fetchChangeRequests();
  }, [entityType, entityId]);

  useEffect(() => {
    highlightDone.current = null;
  }, [highlightChangeRequestId, entityId]);

  useEffect(() => {
    if (!highlightChangeRequestId || loading) return;
    if (changeRequests.length === 0) {
      if (highlightDone.current !== `empty-${highlightChangeRequestId}`) {
        highlightDone.current = `empty-${highlightChangeRequestId}`;
        toast.error('This change request thread is no longer available');
        onHighlightConsumed?.();
      }
      return;
    }
    const match = changeRequests.find((cr) => cr.change_request_id === highlightChangeRequestId);
    if (!match) {
      if (highlightDone.current !== `missing-${highlightChangeRequestId}`) {
        highlightDone.current = `missing-${highlightChangeRequestId}`;
        toast.error('This change request thread is no longer available');
        onHighlightConsumed?.();
      }
      return;
    }
    if (highlightDone.current === highlightChangeRequestId) return;
    highlightDone.current = highlightChangeRequestId;
    setExpanded((prev) => ({ ...prev, [highlightChangeRequestId]: true }));
    requestAnimationFrame(() => {
      const el = document.querySelector(`[data-testid="change-request-${highlightChangeRequestId}"]`);
      if (el) {
        el.scrollIntoView({ behavior: 'smooth', block: 'center' });
        el.classList.add('ring-2', 'ring-primary', 'ring-offset-2');
        setTimeout(() => el.classList.remove('ring-2', 'ring-primary', 'ring-offset-2'), 2000);
      }
      onHighlightConsumed?.();
    });
  }, [highlightChangeRequestId, loading, changeRequests, onHighlightConsumed]);

  const handleRespond = async (crId) => {
    if (!replyText.trim()) return;
    setSending(true);
    try {
      const res = await fetch(`${API}/change-requests/${crId}/respond`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', ...getAuthHeaders() },
        credentials: 'include',
        body: JSON.stringify({ message: replyText }),
      });
      if (res.ok) {
        toast.success('Response sent');
        setReplyText('');
        setReplyingTo(null);
        fetchChangeRequests();
      } else {
        toast.error('Failed to send response');
      }
    } catch {
      toast.error('Failed to send response');
    } finally {
      setSending(false);
    }
  };

  const handleResolve = async (crId) => {
    try {
      const res = await fetch(`${API}/change-requests/${crId}/resolve`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', ...getAuthHeaders() },
        credentials: 'include',
        body: JSON.stringify({ resolution_note: null }),
      });
      if (res.ok) {
        toast.success('Change request resolved');
        fetchChangeRequests();
      } else {
        toast.error('Failed to resolve');
      }
    } catch {
      toast.error('Failed to resolve');
    }
  };

  const handleClose = async (crId) => {
    try {
      const res = await fetch(`${API}/change-requests/${crId}/close`, {
        method: 'POST',
        headers: getAuthHeaders(),
        credentials: 'include',
      });
      if (res.ok) {
        toast.success('Change request closed');
        fetchChangeRequests();
      } else {
        toast.error('Failed to close');
      }
    } catch {
      toast.error('Failed to close');
    }
  };

  if (loading) return null;
  if (changeRequests.length === 0) return null;

  const openCount = changeRequests.filter(cr => cr.status === 'open' || cr.status === 'under_review').length;

  return (
    <Card className={cn('rounded-lg', openCount > 0 ? 'border-amber-500/30' : 'border-border')} data-testid="change-request-panel">
      <CardHeader className="pb-3">
        <CardTitle className="text-base font-outfit flex items-center gap-2">
          <MessageSquare className="w-4 h-4 text-muted-foreground" />
          Change Requests
          {openCount > 0 && (
            <Badge variant="outline" className="ml-auto border-amber-500/30 text-amber-700 bg-amber-500/10">
              {openCount} open
            </Badge>
          )}
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-3">
        {changeRequests.map(cr => {
          const config = STATUS_CONFIG[cr.status] || STATUS_CONFIG.open;
          const StatusIcon = config.icon;
          const isExpanded = expanded[cr.change_request_id];

          return (
            <div
              key={cr.change_request_id}
              className={cn('rounded-lg border p-3', cr.status === 'open' && 'border-amber-500/30 bg-amber-500/5')}
              data-testid={`change-request-${cr.change_request_id}`}
            >
              {/* Header */}
              <div
                className="flex items-center gap-2 cursor-pointer"
                onClick={() => setExpanded(prev => ({ ...prev, [cr.change_request_id]: !prev[cr.change_request_id] }))}
              >
                <StatusIcon className={cn('w-4 h-4', cr.status === 'open' ? 'text-amber-600' : cr.status === 'resolved' ? 'text-emerald-600' : 'text-muted-foreground')} />
                <span className="text-sm font-medium flex-1 truncate">
                  {cr.messages[0]?.content.substring(0, 80)}{cr.messages[0]?.content.length > 80 ? '...' : ''}
                </span>
                <Badge variant="outline" className={cn('text-[10px]', config.color)}>{config.label}</Badge>
                {isExpanded ? <ChevronUp className="w-4 h-4 text-muted-foreground" /> : <ChevronDown className="w-4 h-4 text-muted-foreground" />}
              </div>

              {/* Expanded messages */}
              {isExpanded && (
                <div className="mt-3 space-y-3">
                  {cr.messages.map(msg => (
                    <div key={msg.message_id} className={cn('p-3 rounded-lg', msg.author_role === 'agent' ? 'bg-primary/5 ml-4' : 'bg-muted/50 mr-4')}>
                      <div className="flex items-center gap-2 mb-1">
                        <User className="w-3 h-3 text-muted-foreground" />
                        <span className="text-xs font-medium capitalize">{msg.author_role}</span>
                        <span className="text-xs text-muted-foreground ml-auto">
                          {new Date(msg.created_at).toLocaleDateString('de-CH', { day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit' })}
                        </span>
                      </div>
                      <p className="text-sm whitespace-pre-wrap">{msg.content}</p>
                    </div>
                  ))}

                  {/* Reply input */}
                  {isAgent && (cr.status === 'open' || cr.status === 'under_review') && (
                    <div className="space-y-2 pt-2 border-t border-border">
                      {replyingTo === cr.change_request_id ? (
                        <div className="space-y-2">
                          <Textarea
                            value={replyText}
                            onChange={(e) => setReplyText(e.target.value)}
                            placeholder="Type your response..."
                            rows={3}
                            data-testid={`reply-input-${cr.change_request_id}`}
                          />
                          <div className="flex gap-2">
                            <Button size="sm" onClick={() => handleRespond(cr.change_request_id)} disabled={sending || !replyText.trim()} data-testid={`send-reply-${cr.change_request_id}`}>
                              {sending ? <Loader2 className="w-4 h-4 animate-spin mr-1" /> : <Send className="w-4 h-4 mr-1" />}
                              Send
                            </Button>
                            <Button size="sm" variant="outline" onClick={() => { setReplyingTo(null); setReplyText(''); }}>Cancel</Button>
                          </div>
                        </div>
                      ) : (
                        <div className="flex gap-2">
                          <Button size="sm" variant="outline" onClick={() => setReplyingTo(cr.change_request_id)} data-testid={`reply-btn-${cr.change_request_id}`}>
                            <MessageSquare className="w-4 h-4 mr-1" /> Reply
                          </Button>
                          <Button size="sm" variant="outline" className="text-emerald-700 border-emerald-500/30 hover:bg-emerald-500/10" onClick={() => handleResolve(cr.change_request_id)} data-testid={`resolve-btn-${cr.change_request_id}`}>
                            <CheckCircle className="w-4 h-4 mr-1" /> Resolve
                          </Button>
                        </div>
                      )}
                    </div>
                  )}

                  {/* Close resolved */}
                  {isAgent && cr.status === 'resolved' && (
                    <div className="pt-2 border-t border-border">
                      <Button size="sm" variant="ghost" className="text-muted-foreground" onClick={() => handleClose(cr.change_request_id)} data-testid={`close-btn-${cr.change_request_id}`}>
                        <XCircle className="w-4 h-4 mr-1" /> Close
                      </Button>
                    </div>
                  )}
                </div>
              )}
            </div>
          );
        })}
      </CardContent>
    </Card>
  );
};
