import { useState, useEffect } from 'react';
import { useParams, Link } from 'react-router-dom';
import { AgentLayout } from '../../components/AgentLayout';
import { Card, CardContent, CardHeader, CardTitle } from '../../components/ui/card';
import { Button } from '../../components/ui/button';
import { toast } from 'sonner';
import { 
  ArrowLeft,
  Eye,
  User,
  Building2,
  Home,
  Mail,
  Phone,
  Users,
  Globe,
  FileText,
  Bell,
  Receipt,
  Clock,
  CheckCircle,
  XCircle,
  Download,
  Paperclip
} from 'lucide-react';
import { cn } from '../../lib/utils';

const API = process.env.REACT_APP_BACKEND_URL + '/api';

/**
 * Client Preview Page - "View as Client"
 * 
 * Allows agents to see what a specific client sees.
 * Uses same /activities endpoint with client_id filter.
 * UI-level read-only enforcement (no backend changes).
 */
export const ClientPreview = () => {
  const { clientId } = useParams();
  const [loading, setLoading] = useState(true);
  const [previewData, setPreviewData] = useState(null);
  const [activeTab, setActiveTab] = useState('documents');

  useEffect(() => {
    const fetchPreviewData = async () => {
      try {
        const res = await fetch(`${API}/clients/${clientId}/preview`, {
          credentials: 'include'
        });
        
        if (res.ok) {
          const data = await res.json();
          setPreviewData(data);
        } else {
          toast.error('Failed to load client preview');
        }
      } catch (error) {
        console.error('Preview fetch error:', error);
        toast.error('Failed to load preview');
      } finally {
        setLoading(false);
      }
    };

    fetchPreviewData();
  }, [clientId]);

  if (loading) {
    return (
      <AgentLayout>
        <div className="animate-pulse space-y-4">
          <div className="h-12 bg-muted rounded-lg w-1/3" />
          <div className="h-64 bg-muted rounded-lg" />
        </div>
      </AgentLayout>
    );
  }

  if (!previewData) {
    return (
      <AgentLayout>
        <div className="text-center py-12">
          <p className="text-muted-foreground">Client not found</p>
          <Link to="/agent/clients">
            <Button variant="outline" className="mt-4">
              <ArrowLeft className="w-4 h-4 mr-2" />
              Back to Clients
            </Button>
          </Link>
        </div>
      </AgentLayout>
    );
  }

  const { client, project, activities, team, documents } = previewData;
  
  // Count pending documents
  const pendingDocs = documents?.filter(d => d.status === 'Sent' || d.status === 'Draft') || [];

  // Status config for documents
  const getStatusConfig = (status) => {
    const configs = {
      'Sent': { icon: Clock, color: 'text-amber-500', bg: 'bg-amber-500/10', label: 'Awaiting Response' },
      'Approved': { icon: CheckCircle, color: 'text-emerald-500', bg: 'bg-emerald-500/10', label: 'Approved' },
      'Rejected': { icon: XCircle, color: 'text-red-500', bg: 'bg-red-500/10', label: 'Rejected' },
      'Change Requested': { icon: Clock, color: 'text-orange-500', bg: 'bg-orange-500/10', label: 'Change Requested' },
      'Paid': { icon: CheckCircle, color: 'text-emerald-500', bg: 'bg-emerald-500/10', label: 'Paid' },
      'Draft': { icon: FileText, color: 'text-muted-foreground', bg: 'bg-muted', label: 'Draft' }
    };
    return configs[status] || configs['Draft'];
  };

  const formatCurrency = (amount, currency = 'CHF') => {
    return new Intl.NumberFormat('de-CH', { style: 'currency', currency }).format(amount);
  };

  return (
    <AgentLayout>
      <div className="space-y-6">
        {/* VIEW ONLY Banner */}
        <div className="bg-amber-500/10 border border-amber-500/30 rounded-lg p-4 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-full bg-amber-500/20 flex items-center justify-center">
              <Eye className="w-5 h-5 text-amber-600" />
            </div>
            <div>
              <p className="font-semibold text-amber-700">VIEW ONLY</p>
              <p className="text-sm text-amber-600/80">
                You're viewing what <strong>{client.name}</strong> sees
              </p>
            </div>
          </div>
          <Link to="/agent/clients">
            <Button variant="outline" size="sm" className="border-amber-500/30 hover:bg-amber-500/10">
              <ArrowLeft className="w-4 h-4 mr-2" />
              Exit Preview
            </Button>
          </Link>
        </div>

        {/* Client Info Header */}
        <Card className="border-border">
          <CardContent className="py-4">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-4">
                <div className="w-12 h-12 rounded-full bg-primary/10 flex items-center justify-center">
                  <User className="w-6 h-6 text-primary" />
                </div>
                <div>
                  <h2 className="text-xl font-outfit font-semibold">{client.name}</h2>
                  <div className="flex items-center gap-3 text-sm text-muted-foreground mt-0.5">
                    {project && (
                      <span className="flex items-center gap-1">
                        <Building2 className="w-3.5 h-3.5" />
                        {project.name}
                      </span>
                    )}
                    {client.unit_reference && (
                      <span className="flex items-center gap-1">
                        <Home className="w-3.5 h-3.5" />
                        Unit {client.unit_reference}
                      </span>
                    )}
                  </div>
                </div>
              </div>
            </div>
          </CardContent>
        </Card>

        {/* Tab Navigation */}
        <div className="flex gap-1 p-1 bg-muted rounded-lg">
          <button
            onClick={() => setActiveTab('documents')}
            className={cn(
              "flex-1 flex items-center justify-center gap-2 px-4 py-2.5 rounded-md text-sm font-medium transition-all",
              activeTab === 'documents'
                ? "bg-background text-foreground shadow-sm"
                : "text-muted-foreground hover:text-foreground"
            )}
            data-testid="preview-tab-documents"
          >
            <FileText className="w-4 h-4" />
            Quotes & Invoices
            {pendingDocs.length > 0 && (
              <span className="ml-1 px-1.5 py-0.5 text-[10px] font-bold rounded-full bg-primary text-primary-foreground">
                {pendingDocs.length}
              </span>
            )}
          </button>
          <button
            onClick={() => setActiveTab('updates')}
            className={cn(
              "flex-1 flex items-center justify-center gap-2 px-4 py-2.5 rounded-md text-sm font-medium transition-all",
              activeTab === 'updates'
                ? "bg-background text-foreground shadow-sm"
                : "text-muted-foreground hover:text-foreground"
            )}
            data-testid="preview-tab-updates"
          >
            <Bell className="w-4 h-4" />
            Updates
            {activities.length > 0 && (
              <span className="ml-1 px-1.5 py-0.5 text-[10px] font-bold rounded-full bg-muted text-muted-foreground">
                {activities.length}
              </span>
            )}
          </button>
          <button
            onClick={() => setActiveTab('team')}
            className={cn(
              "flex-1 flex items-center justify-center gap-2 px-4 py-2.5 rounded-md text-sm font-medium transition-all",
              activeTab === 'team'
                ? "bg-background text-foreground shadow-sm"
                : "text-muted-foreground hover:text-foreground"
            )}
            data-testid="preview-tab-team"
          >
            <Users className="w-4 h-4" />
            Team
            {team.length > 0 && (
              <span className="ml-1 px-1.5 py-0.5 text-[10px] font-bold rounded-full bg-muted text-muted-foreground">
                {team.length}
              </span>
            )}
          </button>
        </div>

        {/* Quotes & Invoices Tab */}
        {activeTab === 'documents' && (
          <div className="space-y-4">
            {(!documents || documents.length === 0) ? (
              <Card>
                <CardContent className="py-12 text-center">
                  <FileText className="w-12 h-12 text-muted-foreground/30 mx-auto mb-4" />
                  <p className="text-muted-foreground">No quotes or invoices for this client yet</p>
                </CardContent>
              </Card>
            ) : (
              documents.map(doc => {
                const statusConfig = getStatusConfig(doc.status);
                const StatusIcon = statusConfig.icon;
                const isQuote = doc.type === 'quote';
                
                return (
                  <Card key={doc.document_id} className="border-border overflow-hidden" data-testid={`preview-doc-${doc.document_id}`}>
                    {/* Type indicator bar */}
                    <div className={cn("h-1", isQuote ? "bg-blue-500" : "bg-emerald-500")} />
                    
                    <CardContent className="p-4">
                      <div className="flex items-start justify-between gap-4">
                        <div className="flex-1 min-w-0">
                          {/* Type and status badges */}
                          <div className="flex items-center gap-2 mb-2">
                            <span className={cn(
                              "text-[10px] font-semibold uppercase tracking-wider px-2 py-0.5 rounded-full",
                              isQuote ? "bg-blue-500/10 text-blue-600" : "bg-emerald-500/10 text-emerald-600"
                            )}>
                              {isQuote ? 'Quote' : 'Invoice'}
                            </span>
                            <span className={cn(
                              "text-[10px] font-medium px-2 py-0.5 rounded-full flex items-center gap-1",
                              statusConfig.bg, statusConfig.color
                            )}>
                              <StatusIcon className="w-3 h-3" />
                              {statusConfig.label}
                            </span>
                          </div>
                          
                          {/* Title and number */}
                          <h3 className="font-semibold text-foreground">{doc.title}</h3>
                          <p className="text-sm text-muted-foreground mt-0.5">
                            {doc.document_number} · {doc.unit_reference}
                          </p>
                          
                          {/* Summary */}
                          {doc.summary && (
                            <p className="text-sm text-muted-foreground mt-2 line-clamp-2">{doc.summary}</p>
                          )}
                          
                          {/* Change request comment */}
                          {doc.change_request_comment && (
                            <div className="mt-3 p-3 bg-orange-500/10 rounded-lg border border-orange-500/20">
                              <p className="text-xs font-medium text-orange-600 mb-1">Change Requested:</p>
                              <p className="text-sm text-orange-700">{doc.change_request_comment}</p>
                            </div>
                          )}
                        </div>
                        
                        {/* Amount */}
                        <div className="text-right flex-shrink-0">
                          <p className="text-xl font-semibold text-foreground">
                            {formatCurrency(doc.amount, doc.currency)}
                          </p>
                          <p className="text-xs text-muted-foreground mt-1">
                            {new Date(doc.created_at).toLocaleDateString('en-GB', { day: 'numeric', month: 'short', year: 'numeric' })}
                          </p>
                        </div>
                      </div>
                    </CardContent>
                  </Card>
                );
              })
            )}
          </div>
        )}

        {/* Updates Tab */}
        {activeTab === 'updates' && (
          <div className="space-y-4">
            {activities.length === 0 ? (
              <Card>
                <CardContent className="py-12 text-center">
                  <p className="text-muted-foreground">No updates for this client yet</p>
                </CardContent>
              </Card>
            ) : (
              activities.map(activity => (
                <Card key={activity.activity_id} className="border-border" data-testid={`preview-activity-${activity.activity_id}`}>
                  <CardHeader className="pb-2">
                    <div className="flex items-center gap-2 text-xs text-muted-foreground">
                      <span className="px-2 py-0.5 rounded-full bg-muted uppercase tracking-wider font-medium">
                        {activity.type}
                      </span>
                      {activity.unit_reference && (
                        <span className="px-2 py-0.5 rounded-full bg-muted">
                          {activity.unit_reference}
                        </span>
                      )}
                    </div>
                    <CardTitle className="text-base mt-2">{activity.title || 'Update'}</CardTitle>
                    <p className="text-xs text-muted-foreground">
                      {activity.author_name} · {new Date(activity.created_at).toLocaleDateString('en-GB', { day: 'numeric', month: 'short' })}
                    </p>
                  </CardHeader>
                  <CardContent>
                    {activity.content && (
                      <p className="text-sm text-muted-foreground whitespace-pre-wrap">
                        {activity.content}
                      </p>
                    )}
                    {activity.file_name && (
                      <div className="mt-3 p-3 bg-muted rounded-lg flex items-center gap-2">
                        <span className="text-sm">{activity.file_name}</span>
                      </div>
                    )}
                    {activity.replies && activity.replies.length > 0 && (
                      <div className="mt-4 pt-4 border-t border-border space-y-2">
                        <p className="text-xs font-medium text-muted-foreground">
                          {activity.replies.length} REPLIES
                        </p>
                        {activity.replies.map(reply => (
                          <div key={reply.reply_id} className="pl-4 border-l-2 border-primary/30">
                            <p className="text-sm">{reply.content}</p>
                            <p className="text-xs text-muted-foreground mt-1">
                              {reply.author_name} · {new Date(reply.created_at).toLocaleDateString('en-GB', { day: 'numeric', month: 'short' })}
                            </p>
                          </div>
                        ))}
                      </div>
                    )}
                  </CardContent>
                </Card>
              ))
            )}
          </div>
        )}

        {/* Team Tab */}
        {activeTab === 'team' && (
          <div className="space-y-3">
            {team.length === 0 ? (
              <Card>
                <CardContent className="py-12 text-center">
                  <Users className="w-12 h-12 text-muted-foreground/30 mx-auto mb-4" />
                  <p className="text-muted-foreground">No team members assigned to this project</p>
                </CardContent>
              </Card>
            ) : (
              team.map(member => (
                <Card key={member.member_id} className="border-border" data-testid={`preview-team-${member.member_id}`}>
                  <CardContent className="py-4">
                    <div className="flex items-start justify-between">
                      <div className="flex items-start gap-3">
                        <div className="w-10 h-10 rounded-full bg-primary/10 flex items-center justify-center">
                          <User className="w-5 h-5 text-primary" />
                        </div>
                        <div>
                          <h3 className="font-medium">{member.name}</h3>
                          <p className="text-sm text-muted-foreground">{member.role}</p>
                        </div>
                      </div>
                      <div className="flex items-center gap-2">
                        {member.email && (
                          <a href={`mailto:${member.email}`}>
                            <Button variant="ghost" size="icon" className="h-8 w-8">
                              <Mail className="w-4 h-4" />
                            </Button>
                          </a>
                        )}
                        {member.phone && (
                          <a href={`tel:${member.phone}`}>
                            <Button variant="ghost" size="icon" className="h-8 w-8">
                              <Phone className="w-4 h-4" />
                            </Button>
                          </a>
                        )}
                        {member.website && (
                          <a href={member.website} target="_blank" rel="noopener noreferrer">
                            <Button variant="ghost" size="icon" className="h-8 w-8">
                              <Globe className="w-4 h-4" />
                            </Button>
                          </a>
                        )}
                      </div>
                    </div>
                    {member.notes && (
                      <p className="text-sm text-muted-foreground mt-2 pl-13">
                        {member.notes}
                      </p>
                    )}
                  </CardContent>
                </Card>
              ))
            )}
          </div>
        )}
      </div>
    </AgentLayout>
  );
};

export default ClientPreview;
