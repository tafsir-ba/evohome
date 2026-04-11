import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { AgentLayout } from '../../components/AgentLayout';
import { useDataContext } from '../../context/DataContext';
import { Card, CardContent, CardHeader, CardTitle } from '../../components/ui/card';
import { Button } from '../../components/ui/button';
import { Input } from '../../components/ui/input';
import { Label } from '../../components/ui/label';
import { Textarea } from '../../components/ui/textarea';
import { Badge } from '../../components/ui/badge';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../../components/ui/select';
import { Checkbox } from '../../components/ui/checkbox';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '../../components/ui/dialog';
import { toast } from 'sonner';
import { cn } from '../../lib/utils';
import { ChangeRequestPanel } from '../../components/ChangeRequestPanel';
import {
  Plus,
  CheckSquare,
  Send,
  Clock,
  CheckCircle,
  XCircle,
  AlertCircle,
  Calendar,
  Users,
  Building2,
  ExternalLink,
  Paperclip,
  Loader2,
  Trash2,
  Pencil,
  Upload,
} from 'lucide-react';

const API = process.env.REACT_APP_BACKEND_URL + '/api';
const getAuthHeaders = () => {
  const token = localStorage.getItem('auth_token');
  return token ? { 'Authorization': `Bearer ${token}` } : {};
};

const STATUS_CONFIG = {
  draft: { label: 'Draft', color: 'bg-muted text-muted-foreground', icon: Pencil },
  pending: { label: 'Pending', color: 'bg-amber-500/10 text-amber-700 border-amber-500/30', icon: Clock },
  approved: { label: 'Approved', color: 'bg-emerald-500/10 text-emerald-700 border-emerald-500/30', icon: CheckCircle },
  rejected: { label: 'Rejected', color: 'bg-red-500/10 text-red-700 border-red-500/30', icon: XCircle },
  'Change Requested': { label: 'Change Requested', color: 'bg-blue-500/10 text-blue-700 border-blue-500/30', icon: AlertCircle },
  closed: { label: 'Closed', color: 'bg-muted text-muted-foreground', icon: CheckSquare },
};

export const AgentDecisions = () => {
  const navigate = useNavigate();
  const { projects } = useDataContext();
  const [decisions, setDecisions] = useState([]);
  const [loading, setLoading] = useState(true);
  const [createOpen, setCreateOpen] = useState(false);
  const [detailOpen, setDetailOpen] = useState(false);
  const [selectedDecision, setSelectedDecision] = useState(null);
  const [filter, setFilter] = useState('all');

  // Create form state
  const [form, setForm] = useState({
    project_id: '',
    title: '',
    description: '',
    deadline: '',
    external_link: '',
    client_ids: [],
  });
  const [clients, setClients] = useState([]);
  const [saving, setSaving] = useState(false);
  const [sendingId, setSendingId] = useState(null);
  const [uploadingAttachment, setUploadingAttachment] = useState(false);

  const fetchDecisions = async () => {
    try {
      const res = await fetch(`${API}/decisions`, { credentials: 'include', headers: getAuthHeaders() });
      if (res.ok) {
        const data = await res.json();
        setDecisions(data.decisions || []);
      }
    } catch (error) {
      console.error('Failed to fetch decisions:', error);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { fetchDecisions(); }, []);

  const fetchProjectClients = async (projectId) => {
    if (!projectId) { setClients([]); return; }
    try {
      const res = await fetch(`${API}/projects/${projectId}/context`, { credentials: 'include', headers: getAuthHeaders() });
      if (res.ok) {
        const data = await res.json();
        setClients(data.clients || []);
      }
    } catch (error) {
      console.error('Failed to fetch clients:', error);
    }
  };

  const handleCreate = async () => {
    if (!form.project_id || !form.title) {
      toast.error('Project and title are required');
      return;
    }
    setSaving(true);
    try {
      const res = await fetch(`${API}/decisions`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', ...getAuthHeaders() },
        credentials: 'include',
        body: JSON.stringify({
          ...form,
          client_ids: form.client_ids.length > 0 ? form.client_ids : undefined,
          coverage_type: form.client_ids.length > 0 ? 'clients' : 'project',
        }),
      });
      if (res.ok) {
        toast.success('Decision created');
        setCreateOpen(false);
        setForm({ project_id: '', title: '', description: '', deadline: '', external_link: '', client_ids: [] });
        fetchDecisions();
      } else {
        const err = await res.json();
        toast.error(err.detail || 'Failed to create decision');
      }
    } catch {
      toast.error('Failed to create decision');
    } finally {
      setSaving(false);
    }
  };

  const handleSend = async (decisionId) => {
    setSendingId(decisionId);
    try {
      const res = await fetch(`${API}/decisions/${decisionId}/send`, {
        method: 'POST', credentials: 'include', headers: getAuthHeaders(),
      });
      if (res.ok) {
        toast.success('Decision sent to buyers');
        fetchDecisions();
      } else {
        const err = await res.json();
        toast.error(err.detail || 'Failed to send');
      }
    } catch {
      toast.error('Failed to send decision');
    } finally {
      setSendingId(null);
    }
  };

  const handleClose = async (decisionId) => {
    try {
      const res = await fetch(`${API}/decisions/${decisionId}/close`, {
        method: 'POST', credentials: 'include', headers: getAuthHeaders(),
      });
      if (res.ok) {
        toast.success('Decision closed');
        fetchDecisions();
        if (selectedDecision?.decision_id === decisionId) fetchDetail(decisionId);
      }
    } catch {
      toast.error('Failed to close');
    }
  };

  const handleDelete = async (decisionId) => {
    try {
      const res = await fetch(`${API}/decisions/${decisionId}`, {
        method: 'DELETE', credentials: 'include', headers: getAuthHeaders(),
      });
      if (res.ok) {
        toast.success('Decision deleted');
        fetchDecisions();
        if (selectedDecision?.decision_id === decisionId) { setDetailOpen(false); setSelectedDecision(null); }
      } else {
        const err = await res.json();
        toast.error(err.detail || 'Failed to delete');
      }
    } catch {
      toast.error('Failed to delete');
    }
  };

  const handleUploadAttachment = async (decisionId, file) => {
    setUploadingAttachment(true);
    try {
      const formData = new FormData();
      formData.append('file', file);
      const res = await fetch(`${API}/decisions/${decisionId}/upload-attachment`, {
        method: 'POST', credentials: 'include', headers: getAuthHeaders(), body: formData,
      });
      if (res.ok) {
        toast.success('Attachment uploaded');
        fetchDetail(decisionId);
      } else {
        toast.error('Failed to upload');
      }
    } catch {
      toast.error('Upload failed');
    } finally {
      setUploadingAttachment(false);
    }
  };

  const fetchDetail = async (decisionId) => {
    try {
      const res = await fetch(`${API}/decisions/${decisionId}`, { credentials: 'include', headers: getAuthHeaders() });
      if (res.ok) {
        setSelectedDecision(await res.json());
      }
    } catch {
      toast.error('Failed to load decision');
    }
  };

  const openDetail = (decision) => {
    fetchDetail(decision.decision_id);
    setDetailOpen(true);
  };

  const filtered = filter === 'all' ? decisions : decisions.filter(d => d.status === filter);

  return (
    <AgentLayout>
      <div className="space-y-6" data-testid="decisions-page">
        {/* Header */}
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-outfit font-semibold">Decisions</h1>
            <p className="text-sm text-muted-foreground mt-0.5">{decisions.length} decision{decisions.length !== 1 ? 's' : ''}</p>
          </div>
          <Button onClick={() => setCreateOpen(true)} data-testid="new-decision-btn">
            <Plus className="w-4 h-4 mr-2" /> New Decision
          </Button>
        </div>

        {/* Filters */}
        <div className="flex gap-2 flex-wrap">
          {['all', 'draft', 'pending', 'approved', 'rejected', 'Change Requested', 'closed'].map(f => (
            <Button key={f} variant={filter === f ? 'default' : 'outline'} size="sm" onClick={() => setFilter(f)} className="capitalize">
              {f === 'all' ? 'All' : (STATUS_CONFIG[f]?.label || f)}
            </Button>
          ))}
        </div>

        {/* Decision List */}
        {loading ? (
          <div className="space-y-3">{[1,2,3].map(i => <div key={i} className="h-20 bg-muted rounded-lg animate-pulse" />)}</div>
        ) : filtered.length === 0 ? (
          <Card className="border-dashed">
            <CardContent className="py-12 text-center">
              <CheckSquare className="w-10 h-10 text-muted-foreground mx-auto mb-3" />
              <p className="text-muted-foreground">{filter === 'all' ? 'No decisions yet' : `No ${filter} decisions`}</p>
              <Button variant="outline" size="sm" className="mt-4" onClick={() => setCreateOpen(true)}>Create your first decision</Button>
            </CardContent>
          </Card>
        ) : (
          <div className="space-y-2">
            {filtered.map(d => {
              const config = STATUS_CONFIG[d.status] || STATUS_CONFIG.draft;
              const StatusIcon = config.icon;
              const isOverdue = d.deadline && d.status === 'pending' && new Date(d.deadline) < new Date();
              return (
                <Card
                  key={d.decision_id}
                  className={cn('border-border hover:shadow-sm transition-all cursor-pointer', isOverdue && 'border-red-500/30')}
                  onClick={() => openDetail(d)}
                  data-testid={`decision-card-${d.decision_id}`}
                >
                  <CardContent className="py-4 px-5">
                    <div className="flex items-center gap-4">
                      <StatusIcon className={cn('w-5 h-5 flex-shrink-0', d.status === 'approved' ? 'text-emerald-600' : d.status === 'pending' ? 'text-amber-600' : d.status === 'rejected' ? 'text-red-600' : 'text-muted-foreground')} />
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2">
                          <p className="font-medium truncate">{d.title}</p>
                          <Badge variant="outline" className={cn('text-[10px]', config.color)}>{config.label}</Badge>
                          {isOverdue && <Badge variant="outline" className="text-[10px] border-red-500/30 text-red-700 bg-red-500/10">Overdue</Badge>}
                        </div>
                        <div className="flex items-center gap-3 mt-1 text-xs text-muted-foreground">
                          {d.project_name && <span className="flex items-center gap-1"><Building2 className="w-3 h-3" />{d.project_name}</span>}
                          {d.deadline && <span className="flex items-center gap-1"><Calendar className="w-3 h-3" />{new Date(d.deadline).toLocaleDateString('de-CH')}</span>}
                          {d.recipient_count > 0 && <span className="flex items-center gap-1"><Users className="w-3 h-3" />{d.approved_count}/{d.recipient_count} approved</span>}
                        </div>
                      </div>
                      <div className="flex gap-2 flex-shrink-0">
                        {d.status === 'draft' && (
                          <>
                            <Button size="sm" variant="outline" onClick={(e) => { e.stopPropagation(); handleSend(d.decision_id); }} disabled={sendingId === d.decision_id} data-testid={`send-decision-${d.decision_id}`}>
                              {sendingId === d.decision_id ? <Loader2 className="w-4 h-4 animate-spin" /> : <><Send className="w-4 h-4 mr-1" />Send</>}
                            </Button>
                            <Button size="sm" variant="ghost" className="text-destructive" onClick={(e) => { e.stopPropagation(); handleDelete(d.decision_id); }}>
                              <Trash2 className="w-4 h-4" />
                            </Button>
                          </>
                        )}
                        {d.status === 'Change Requested' && (
                          <Button size="sm" variant="outline" onClick={(e) => { e.stopPropagation(); handleSend(d.decision_id); }} disabled={sendingId === d.decision_id}>
                            <Send className="w-4 h-4 mr-1" />Resend
                          </Button>
                        )}
                      </div>
                    </div>
                  </CardContent>
                </Card>
              );
            })}
          </div>
        )}
      </div>

      {/* Create Dialog */}
      <Dialog open={createOpen} onOpenChange={setCreateOpen}>
        <DialogContent className="max-w-lg max-h-[90vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle>New Decision</DialogTitle>
            <DialogDescription>Request a formal approval from your clients.</DialogDescription>
          </DialogHeader>
          <div className="space-y-4 py-4">
            <div className="space-y-2">
              <Label>Project *</Label>
              <Select value={form.project_id} onValueChange={(v) => { setForm(f => ({ ...f, project_id: v, client_ids: [] })); fetchProjectClients(v); }}>
                <SelectTrigger data-testid="decision-project-select"><SelectValue placeholder="Select project" /></SelectTrigger>
                <SelectContent>
                  {projects.map(p => <SelectItem key={p.project_id} value={p.project_id}>{p.name}</SelectItem>)}
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-2">
              <Label>Title *</Label>
              <Input value={form.title} onChange={e => setForm(f => ({ ...f, title: e.target.value }))} placeholder="e.g., Validate Kitchen Layout" data-testid="decision-title-input" />
            </div>
            <div className="space-y-2">
              <Label>Description</Label>
              <Textarea value={form.description} onChange={e => setForm(f => ({ ...f, description: e.target.value }))} placeholder="Describe what the client needs to approve..." rows={4} data-testid="decision-description-input" />
            </div>
            <div className="space-y-2">
              <Label>Deadline</Label>
              <Input type="date" value={form.deadline} onChange={e => setForm(f => ({ ...f, deadline: e.target.value }))} data-testid="decision-deadline-input" />
            </div>
            <div className="space-y-2">
              <Label>External Link (optional)</Label>
              <Input value={form.external_link} onChange={e => setForm(f => ({ ...f, external_link: e.target.value }))} placeholder="https://docusign.com/..." data-testid="decision-link-input" />
            </div>
            {form.project_id && clients.length > 0 && (
              <div className="space-y-2">
                <Label>Recipients (leave empty for entire project)</Label>
                <div className="border rounded-lg p-3 max-h-40 overflow-y-auto space-y-2">
                  {clients.map(c => (
                    <div key={c.client_id} className="flex items-center space-x-2">
                      <Checkbox
                        checked={form.client_ids.includes(c.client_id)}
                        onCheckedChange={checked => setForm(f => ({
                          ...f,
                          client_ids: checked ? [...f.client_ids, c.client_id] : f.client_ids.filter(id => id !== c.client_id)
                        }))}
                      />
                      <label className="text-sm">{c.name}{c.unit_reference && <span className="text-muted-foreground ml-1">({c.unit_reference})</span>}</label>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setCreateOpen(false)}>Cancel</Button>
            <Button onClick={handleCreate} disabled={saving} data-testid="create-decision-submit">
              {saving ? <Loader2 className="w-4 h-4 animate-spin mr-2" /> : <Plus className="w-4 h-4 mr-2" />}
              Create Decision
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Detail Dialog */}
      <Dialog open={detailOpen} onOpenChange={setDetailOpen}>
        <DialogContent className="max-w-2xl max-h-[90vh] overflow-y-auto">
          {selectedDecision && <DecisionDetail decision={selectedDecision} onSend={handleSend} onClose={handleClose} onUpload={handleUploadAttachment} uploadingAttachment={uploadingAttachment} sendingId={sendingId} />}
        </DialogContent>
      </Dialog>
    </AgentLayout>
  );
};

const DecisionDetail = ({ decision, onSend, onClose, onUpload, uploadingAttachment, sendingId }) => {
  const config = STATUS_CONFIG[decision.status] || STATUS_CONFIG.draft;
  const StatusIcon = config.icon;

  return (
    <>
      <DialogHeader>
        <DialogTitle className="flex items-center gap-2">
          <StatusIcon className={cn('w-5 h-5', decision.status === 'approved' ? 'text-emerald-600' : decision.status === 'pending' ? 'text-amber-600' : 'text-muted-foreground')} />
          {decision.title}
        </DialogTitle>
        <DialogDescription className="flex items-center gap-3">
          <Badge variant="outline" className={cn('text-xs', config.color)}>{config.label}</Badge>
          {decision.project_name && <span className="flex items-center gap-1 text-xs"><Building2 className="w-3 h-3" />{decision.project_name}</span>}
          {decision.deadline && <span className="flex items-center gap-1 text-xs"><Calendar className="w-3 h-3" />{new Date(decision.deadline).toLocaleDateString('de-CH')}</span>}
        </DialogDescription>
      </DialogHeader>

      <div className="space-y-4 py-4">
        {/* Description */}
        {decision.description && (
          <div>
            <p className="text-xs font-semibold uppercase tracking-wider text-muted-foreground mb-1">Description</p>
            <p className="text-sm whitespace-pre-wrap">{decision.description}</p>
          </div>
        )}

        {/* External Link */}
        {decision.external_link && (
          <div>
            <p className="text-xs font-semibold uppercase tracking-wider text-muted-foreground mb-1">External Link</p>
            <a href={decision.external_link} target="_blank" rel="noopener noreferrer" className="text-sm text-primary flex items-center gap-1 hover:underline">
              <ExternalLink className="w-4 h-4" />{decision.external_link}
            </a>
          </div>
        )}

        {/* Attachments */}
        {decision.attachments?.length > 0 && (
          <div>
            <p className="text-xs font-semibold uppercase tracking-wider text-muted-foreground mb-1">Attachments</p>
            <div className="space-y-1">
              {decision.attachments.map((att, i) => (
                <a key={att.filename || `att-${i}`} href={att.url} target="_blank" rel="noopener noreferrer" className="flex items-center gap-2 p-2 rounded-lg bg-muted/50 hover:bg-muted text-sm">
                  <Paperclip className="w-4 h-4 text-muted-foreground" />
                  <span className="truncate">{att.filename || att.url}</span>
                </a>
              ))}
            </div>
          </div>
        )}

        {/* Upload attachment (draft/change requested only) */}
        {(decision.status === 'draft' || decision.status === 'Change Requested') && (
          <label className="flex items-center gap-2 p-2 border border-dashed rounded-lg cursor-pointer hover:bg-muted/30 transition-colors">
            <input type="file" className="hidden" onChange={e => { if (e.target.files?.[0]) onUpload(decision.decision_id, e.target.files[0]); }} />
            {uploadingAttachment ? <Loader2 className="w-4 h-4 animate-spin" /> : <Upload className="w-4 h-4 text-muted-foreground" />}
            <span className="text-sm text-muted-foreground">Add attachment</span>
          </label>
        )}

        {/* Recipients */}
        {decision.recipients?.length > 0 && (
          <div>
            <p className="text-xs font-semibold uppercase tracking-wider text-muted-foreground mb-2">Recipients</p>
            <div className="space-y-2">
              {decision.recipients.map(r => (
                <div key={r.client_id} className="flex items-center justify-between p-2 rounded-lg border border-border">
                  <div className="flex items-center gap-2">
                    <Users className="w-4 h-4 text-muted-foreground" />
                    <div>
                      <p className="text-sm font-medium">{r.client_name}</p>
                      <p className="text-xs text-muted-foreground">{r.client_email}</p>
                    </div>
                  </div>
                  <Badge variant="outline" className={cn('text-[10px]', STATUS_CONFIG[r.status]?.color || 'bg-muted text-muted-foreground')}>
                    {STATUS_CONFIG[r.status]?.label || r.status}
                  </Badge>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Change Requests */}
        <ChangeRequestPanel entityType="decision" entityId={decision.decision_id} isAgent={true} />
      </div>

      <DialogFooter>
        {decision.status === 'draft' && (
          <Button onClick={() => onSend(decision.decision_id)} disabled={sendingId === decision.decision_id} data-testid="detail-send-decision">
            {sendingId === decision.decision_id ? <Loader2 className="w-4 h-4 animate-spin mr-2" /> : <Send className="w-4 h-4 mr-2" />}
            Send to Buyers
          </Button>
        )}
        {decision.status === 'Change Requested' && (
          <Button onClick={() => onSend(decision.decision_id)} disabled={sendingId === decision.decision_id}>
            <Send className="w-4 h-4 mr-2" />Resend
          </Button>
        )}
        {['approved', 'rejected'].includes(decision.status) && (
          <Button variant="outline" onClick={() => onClose(decision.decision_id)}>
            <CheckSquare className="w-4 h-4 mr-2" />Close Decision
          </Button>
        )}
      </DialogFooter>
    </>
  );
};

export default AgentDecisions;
