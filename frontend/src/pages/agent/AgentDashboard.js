import { useState, useEffect, useCallback } from 'react';
import { Link } from 'react-router-dom';
import { AgentLayout } from '../../components/AgentLayout';
import { useSettings } from '../../context/SettingsContext';
import { useAuth } from '../../context/AuthContext';
import { formatDocContext } from '../../lib/utils';
import { useWebSocket } from '../../hooks/useWebSocket';
import { StatusBadge, formatDate } from '../../components/StatusBadge';
import { Card, CardContent, CardHeader, CardTitle } from '../../components/ui/card';
import { Button } from '../../components/ui/button';
import { toast } from 'sonner';
import { 
  Users, 
  FileText, 
  Receipt, 
  TrendingUp,
  ArrowRight,
  Plus,
  AlertCircle,
  MessageSquare,
  Wifi,
  WifiOff
} from 'lucide-react';

const API = process.env.REACT_APP_BACKEND_URL + '/api';

const getAuthHeaders = () => {
  const token = localStorage.getItem('auth_token');
  return token ? { 'Authorization': `Bearer ${token}` } : {};
};

export const AgentDashboard = () => {
  const { t, formatCurrency } = useSettings();
  const { user } = useAuth();
  const [stats, setStats] = useState(null);
  const [loading, setLoading] = useState(true);

  // Fetch stats function (memoized for WebSocket callback)
  const fetchStats = useCallback(async () => {
    try {
      const response = await fetch(`${API}/stats/agent`, { credentials: 'include', headers: getAuthHeaders() });
      if (response.ok) {
        setStats(await response.json());
      }
    } catch (error) {
      console.error('Failed to fetch stats:', error);
      toast.error('Failed to load dashboard data');
    } finally {
      setLoading(false);
    }
  }, []);

  // WebSocket for real-time updates
  const handleWebSocketMessage = useCallback((message) => {
    // Refresh stats when buyer takes action on documents
    if (['quote_approved', 'quote_rejected', 'change_requested', 'payment_confirmed'].includes(message.type)) {
      fetchStats();
    }
  }, [fetchStats]);

  const { isConnected } = useWebSocket(user?.user_id, handleWebSocketMessage);

  useEffect(() => {
    fetchStats();
  }, [fetchStats]);

  if (loading) {
    return (
      <AgentLayout>
        <div className="animate-pulse space-y-6">
          <div className="h-8 w-48 bg-muted rounded" />
          <div className="grid grid-cols-1 md:grid-cols-4 gap-6">
            {[1, 2, 3, 4].map(i => (
              <div key={i} className="h-32 bg-muted rounded-lg" />
            ))}
          </div>
        </div>
      </AgentLayout>
    );
  }

  return (
    <AgentLayout>
      <div className="space-y-8" data-testid="agent-dashboard">
        {/* Header */}
        <div className="flex flex-col sm:flex-row sm:items-start sm:justify-between gap-4">
          <div>
            <h1 className="text-2xl sm:text-3xl font-outfit font-semibold text-foreground tracking-tight">
              {t('dashboard.title')}
            </h1>
            <p className="text-muted-foreground mt-1 text-sm sm:text-base">{t('dashboard.welcome')}</p>
          </div>
          <div className="flex gap-2 sm:gap-3">
            <Link to="/agent/documents/new?type=quote" className="flex-1 sm:flex-none">
              <Button className="w-full sm:w-auto rounded-lg text-xs sm:text-sm" data-testid="create-quote-btn">
                <Plus className="w-4 h-4 mr-1 sm:mr-2" />
                <span className="hidden xs:inline">{t('dashboard.newQuote')}</span>
                <span className="xs:hidden">Quote</span>
              </Button>
            </Link>
            <Link to="/agent/documents/new?type=invoice" className="flex-1 sm:flex-none">
              <Button variant="outline" className="w-full sm:w-auto rounded-lg text-xs sm:text-sm" data-testid="create-invoice-btn">
                <Plus className="w-4 h-4 mr-1 sm:mr-2" />
                <span className="hidden xs:inline">{t('dashboard.newInvoice')}</span>
                <span className="xs:hidden">Invoice</span>
              </Button>
            </Link>
          </div>
        </div>

        {/* Stats Cards - All clickable */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
          <Link to="/agent/clients" data-testid="stats-clients">
            <Card className="border-border rounded-lg hover:border-primary/30 hover:shadow-lg transition-all cursor-pointer">
              <CardContent className="pt-6">
                <div className="flex items-start justify-between">
                  <div>
                    <p className="text-xs font-medium tracking-widest uppercase text-muted-foreground">{t('dashboard.activeClients')}</p>
                    <p className="text-3xl font-outfit font-semibold text-foreground mt-2">{stats?.total_clients || 0}</p>
                  </div>
                  <div className="w-10 h-10 bg-muted rounded-lg flex items-center justify-center">
                    <Users className="w-5 h-5 text-muted-foreground" />
                  </div>
                </div>
              </CardContent>
            </Card>
          </Link>

          <Link to="/agent/documents" data-testid="stats-quotes">
            <Card className="border-border rounded-lg hover:border-primary/30 hover:shadow-lg transition-all cursor-pointer">
              <CardContent className="pt-6">
                <div className="flex items-start justify-between">
                  <div>
                    <p className="text-xs font-medium tracking-widest uppercase text-muted-foreground">{t('dashboard.pendingQuotes')}</p>
                    <p className="text-3xl font-outfit font-semibold text-foreground mt-2">{stats?.pending_quotes || 0}</p>
                  </div>
                  <div className="w-10 h-10 bg-blue-500/10 rounded-lg flex items-center justify-center">
                    <FileText className="w-5 h-5 text-blue-600" />
                  </div>
                </div>
              </CardContent>
            </Card>
          </Link>

          <Link to="/agent/documents" data-testid="stats-invoices">
            <Card className="border-border rounded-lg hover:border-primary/30 hover:shadow-lg transition-all cursor-pointer">
              <CardContent className="pt-6">
                <div className="flex items-start justify-between">
                  <div>
                    <p className="text-xs font-medium tracking-widest uppercase text-muted-foreground">{t('dashboard.pendingInvoices')}</p>
                    <p className="text-3xl font-outfit font-semibold text-foreground mt-2">{stats?.pending_invoices || 0}</p>
                  </div>
                  <div className="w-10 h-10 bg-purple-500/10 rounded-lg flex items-center justify-center">
                    <Receipt className="w-5 h-5 text-purple-600" />
                  </div>
                </div>
              </CardContent>
            </Card>
          </Link>

          <Card className="border-border rounded-lg">
            <CardContent className="pt-6">
              <div className="flex items-start justify-between">
                <div>
                  <p className="text-xs font-medium tracking-widest uppercase text-muted-foreground">Total Revenue</p>
                  <p className="text-3xl font-outfit font-semibold text-foreground mt-2">{formatCurrency(stats?.total_revenue || 0)}</p>
                </div>
                <div className="w-10 h-10 bg-green-500/10 rounded-lg flex items-center justify-center">
                  <TrendingUp className="w-5 h-5 text-green-600" />
                </div>
              </div>
            </CardContent>
          </Card>
        </div>

        {/* Main Content */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
          {/* Change Requests - Priority - Aggregated across entity types */}
          <Card className="border-border rounded-lg">
            <CardHeader className="border-b border-border">
              <div className="flex items-center justify-between">
                <CardTitle className="text-lg font-outfit font-semibold flex items-center gap-2">
                  <AlertCircle className="w-5 h-5 text-amber-500" />
                  Change Requests
                </CardTitle>
                <span className="text-xs font-medium px-2 py-1 bg-amber-500/10 text-amber-700 dark:text-amber-400 rounded-lg">
                  {stats?.change_requests?.length || 0} pending
                </span>
              </div>
            </CardHeader>
            <CardContent className="p-0">
              {stats?.change_requests?.length > 0 ? (
                <div className="divide-y divide-border">
                  {stats.change_requests.map((doc) => {
                    const detailPath = `/agent/documents/${doc.document_id}`;
                    return (
                      <Link 
                        key={doc.document_id} 
                        to={detailPath}
                        className="flex items-start gap-4 p-4 hover:bg-muted/50 transition-colors"
                        data-testid={`change-request-${doc.document_id}`}
                      >
                        <div className="w-8 h-8 bg-amber-500/10 rounded-lg flex items-center justify-center flex-shrink-0 mt-0.5">
                          <MessageSquare className="w-4 h-4 text-amber-600" />
                        </div>
                        <div className="flex-1 min-w-0">
                          <div className="flex items-center gap-2">
                            <p className="font-medium text-foreground truncate">{doc.title}</p>
                            <span className="text-xs px-1.5 py-0.5 bg-muted rounded capitalize">{doc.type}</span>
                          </div>
                          <p className="text-sm text-muted-foreground">{formatDocContext({ document_number: doc.document_number, client_name: doc.client_name, unit_reference: doc.unit_reference })}</p>
                          {doc.change_request_comment && (
                            <p className="text-sm text-amber-700 dark:text-amber-400 mt-2 line-clamp-2 bg-amber-500/10 p-2 rounded-lg">
                              "{doc.change_request_comment}"
                            </p>
                          )}
                        </div>
                        <ArrowRight className="w-4 h-4 text-muted-foreground flex-shrink-0 mt-1" />
                      </Link>
                    );
                  })}
                </div>
              ) : (
                <div className="p-8 text-center">
                  <MessageSquare className="w-12 h-12 text-muted-foreground/30 mx-auto mb-3" />
                  <p className="text-muted-foreground">No change requests</p>
                </div>
              )}
            </CardContent>
          </Card>

          {/* Recent Activity - Clickable header */}
          <Card className="border-border rounded-lg">
            <CardHeader className="border-b border-border">
              <Link to="/agent/documents" className="flex items-center justify-between hover:opacity-80 transition-opacity">
                <CardTitle className="text-lg font-outfit font-semibold">Recent Quotes</CardTitle>
                <div className="flex items-center gap-2">
                  <span className="text-sm text-primary">View all</span>
                  <ArrowRight className="w-4 h-4 text-primary" />
                </div>
              </Link>
            </CardHeader>
            <CardContent className="p-0">
              {stats?.recent_documents?.length > 0 ? (
                <div className="divide-y divide-border">
                  {stats.recent_documents.filter(d => d.type === 'quote').slice(0, 5).map((quote) => (
                    <Link 
                      key={quote.document_id} 
                      to={`/agent/documents/${quote.document_id}`}
                      className="flex items-center justify-between p-4 hover:bg-muted/50 transition-colors"
                      data-testid={`recent-quote-${quote.document_id}`}
                    >
                      <div className="flex-1 min-w-0">
                        <p className="font-medium text-foreground truncate">{quote.title}</p>
                        <p className="text-sm text-muted-foreground">{quote.document_number}</p>
                      </div>
                      <div className="flex items-center gap-4">
                        <div className="text-right">
                          <p className="font-medium text-foreground">{formatCurrency(quote.amount)}</p>
                          <StatusBadge status={quote.status} />
                        </div>
                        <ArrowRight className="w-4 h-4 text-muted-foreground" />
                      </div>
                    </Link>
                  ))}
                </div>
              ) : (
                <div className="p-8 text-center">
                  <FileText className="w-12 h-12 text-muted-foreground/30 mx-auto mb-3" />
                  <p className="text-muted-foreground">No quotes yet</p>
                  <Link to="/agent/documents/new?type=quote">
                    <Button variant="outline" className="mt-4 rounded-lg">
                      Create your first quote
                    </Button>
                  </Link>
                </div>
              )}
            </CardContent>
          </Card>
        </div>

        {/* Quick Actions - All clickable */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <Link to="/agent/clients" className="card-swiss p-4 flex items-center gap-4 hover:shadow-lg transition-all" data-testid="quick-action-clients">
            <div className="w-12 h-12 bg-muted rounded-lg flex items-center justify-center">
              <Users className="w-6 h-6 text-muted-foreground" />
            </div>
            <div className="flex-1">
              <p className="font-medium text-foreground">Manage Clients</p>
              <p className="text-sm text-muted-foreground">View and edit client details</p>
            </div>
            <ArrowRight className="w-5 h-5 text-muted-foreground" />
          </Link>
          
          <Link to="/agent/documents" className="card-swiss p-4 flex items-center gap-4 hover:shadow-lg transition-all" data-testid="quick-action-quotes">
            <div className="w-12 h-12 bg-blue-500/10 rounded-lg flex items-center justify-center">
              <FileText className="w-6 h-6 text-blue-600" />
            </div>
            <div className="flex-1">
              <p className="font-medium text-foreground">All Quotes</p>
              <p className="text-sm text-muted-foreground">Track quote statuses</p>
            </div>
            <ArrowRight className="w-5 h-5 text-muted-foreground" />
          </Link>
          
          <Link to="/agent/documents" className="card-swiss p-4 flex items-center gap-4 hover:shadow-lg transition-all" data-testid="quick-action-invoices">
            <div className="w-12 h-12 bg-purple-500/10 rounded-lg flex items-center justify-center">
              <Receipt className="w-6 h-6 text-purple-600" />
            </div>
            <div className="flex-1">
              <p className="font-medium text-foreground">All Invoices</p>
              <p className="text-sm text-muted-foreground">Manage payments</p>
            </div>
            <ArrowRight className="w-5 h-5 text-muted-foreground" />
          </Link>
        </div>
      </div>
    </AgentLayout>
  );
};
