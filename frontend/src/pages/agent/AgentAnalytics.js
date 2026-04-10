import { useState, useEffect } from 'react';
import { AgentLayout } from '../../components/AgentLayout';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '../../components/ui/card';
import { Button } from '../../components/ui/button';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../../components/ui/select';
import { useSettings } from '../../context/SettingsContext';
import { toast } from 'sonner';
import { 
  TrendingUp, 
  TrendingDown,
  FileText, 
  Receipt, 
  Users, 
  Building2,
  Calendar,
  DollarSign,
  CheckCircle,
  Clock,
  XCircle,
  Loader2,
  ArrowUpRight,
  ArrowDownRight
} from 'lucide-react';

const API = process.env.REACT_APP_BACKEND_URL + '/api';

const formatCurrency = (amount) => {
  return new Intl.NumberFormat('de-CH', {
    style: 'currency',
    currency: 'CHF',
    minimumFractionDigits: 0,
    maximumFractionDigits: 0
  }).format(amount || 0);
};

const StatCard = ({ title, value, subtext, icon: Icon, trend, trendValue, color = 'primary' }) => {
  const colorClasses = {
    primary: 'bg-primary/10 text-primary',
    emerald: 'bg-emerald-500/10 text-emerald-600',
    amber: 'bg-amber-500/10 text-amber-600',
    red: 'bg-red-500/10 text-red-600',
    blue: 'bg-blue-500/10 text-blue-600'
  };

  return (
    <Card className="border-border">
      <CardContent className="pt-6">
        <div className="flex items-start justify-between">
          <div>
            <p className="text-sm text-muted-foreground">{title}</p>
            <p className="text-2xl font-bold text-foreground mt-1">{value}</p>
            {subtext && <p className="text-xs text-muted-foreground mt-1">{subtext}</p>}
          </div>
          <div className={`p-3 rounded-lg ${colorClasses[color]}`}>
            <Icon className="w-5 h-5" />
          </div>
        </div>
        {trend && (
          <div className="flex items-center gap-1 mt-3 pt-3 border-t border-border">
            {trend === 'up' ? (
              <ArrowUpRight className="w-4 h-4 text-emerald-600" />
            ) : (
              <ArrowDownRight className="w-4 h-4 text-red-600" />
            )}
            <span className={trend === 'up' ? 'text-emerald-600 text-sm' : 'text-red-600 text-sm'}>
              {trendValue}
            </span>
            <span className="text-muted-foreground text-sm ml-1">vs last month</span>
          </div>
        )}
      </CardContent>
    </Card>
  );
};

const DocumentStatusChart = ({ data }) => {
  const total = Object.values(data).reduce((a, b) => a + b, 0) || 1;
  
  const statuses = [
    { key: 'approved', label: 'Approved', color: 'bg-emerald-500', value: data.approved || 0 },
    { key: 'sent', label: 'Pending', color: 'bg-amber-500', value: data.sent || 0 },
    { key: 'rejected', label: 'Rejected', color: 'bg-red-500', value: data.rejected || 0 },
    { key: 'draft', label: 'Draft', color: 'bg-gray-400', value: data.draft || 0 }
  ];

  return (
    <div className="space-y-3">
      {statuses.map(status => (
        <div key={status.key} className="space-y-1">
          <div className="flex items-center justify-between text-sm">
            <span className="text-muted-foreground">{status.label}</span>
            <span className="font-medium text-foreground">{status.value}</span>
          </div>
          <div className="h-2 bg-muted rounded-full overflow-hidden">
            <div 
              className={`h-full ${status.color} rounded-full transition-all`}
              style={{ width: `${(status.value / total) * 100}%` }}
            />
          </div>
        </div>
      ))}
    </div>
  );
};

export const AgentAnalytics = () => {
  const { t } = useSettings();
  const [loading, setLoading] = useState(true);
  const [period, setPeriod] = useState('month');
  const [stats, setStats] = useState({
    totalQuotes: 0,
    totalInvoices: 0,
    totalClients: 0,
    totalProjects: 0,
    totalRevenue: 0,
    pendingAmount: 0,
    quoteStats: { approved: 0, sent: 0, rejected: 0, draft: 0 },
    invoiceStats: { paid: 0, sent: 0, draft: 0 },
    recentActivity: []
  });

  useEffect(() => {
    fetchAnalytics();
  }, [period]);

  const fetchAnalytics = async () => {
    setLoading(true);
    try {
      const res = await fetch(`${API}/analytics?period=${period}`, {
        credentials: 'include'
      });
      
      if (res.ok) {
        const data = await res.json();
        setStats(data);
      }
    } catch (error) {
      console.error('Failed to fetch analytics:', error);
      toast.error('Failed to load analytics');
    } finally {
      setLoading(false);
    }
  };

  if (loading) {
    return (
      <AgentLayout>
        <div className="flex items-center justify-center h-64">
          <Loader2 className="w-8 h-8 animate-spin text-primary" />
        </div>
      </AgentLayout>
    );
  }

  return (
    <AgentLayout>
      <div className="space-y-6" data-testid="agent-analytics">
        {/* Header */}
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
          <div>
            <h1 className="text-2xl sm:text-3xl font-outfit font-semibold text-foreground tracking-tight">
              Analytics
            </h1>
            <p className="text-muted-foreground mt-1">Overview of your business performance</p>
          </div>
          <Select value={period} onValueChange={setPeriod}>
            <SelectTrigger className="w-[180px]">
              <Calendar className="w-4 h-4 mr-2" />
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="week">Last 7 days</SelectItem>
              <SelectItem value="month">Last 30 days</SelectItem>
              <SelectItem value="quarter">Last 90 days</SelectItem>
              <SelectItem value="year">Last year</SelectItem>
              <SelectItem value="all">All time</SelectItem>
            </SelectContent>
          </Select>
        </div>

        {/* Main Stats */}
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          <StatCard
            title="Total Revenue"
            value={formatCurrency(stats.totalRevenue)}
            subtext={`${stats.invoiceStats?.paid || 0} invoices paid`}
            icon={DollarSign}
            color="emerald"
          />
          <StatCard
            title="Pending Payments"
            value={formatCurrency(stats.pendingAmount)}
            subtext={`${stats.invoiceStats?.sent || 0} awaiting payment`}
            icon={Clock}
            color="amber"
          />
          <StatCard
            title="Total Quotes"
            value={stats.totalQuotes}
            subtext={`${stats.quoteStats?.approved || 0} approved`}
            icon={FileText}
            color="blue"
          />
          <StatCard
            title="Active Clients"
            value={stats.totalClients}
            subtext={`Across ${stats.totalProjects} projects`}
            icon={Users}
            color="primary"
          />
        </div>

        {/* Charts Row */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* Quote Status Distribution */}
          <Card className="border-border">
            <CardHeader>
              <CardTitle className="text-lg font-outfit">Quote Status</CardTitle>
              <CardDescription>Distribution of your quotes by status</CardDescription>
            </CardHeader>
            <CardContent>
              <DocumentStatusChart data={stats.quoteStats} />
            </CardContent>
          </Card>

          {/* Invoice Status Distribution */}
          <Card className="border-border">
            <CardHeader>
              <CardTitle className="text-lg font-outfit">Invoice Status</CardTitle>
              <CardDescription>Distribution of your invoices by status</CardDescription>
            </CardHeader>
            <CardContent>
              <div className="space-y-3">
                <div className="space-y-1">
                  <div className="flex items-center justify-between text-sm">
                    <span className="text-muted-foreground">Paid</span>
                    <span className="font-medium text-foreground">{stats.invoiceStats?.paid || 0}</span>
                  </div>
                  <div className="h-2 bg-muted rounded-full overflow-hidden">
                    <div 
                      className="h-full bg-emerald-500 rounded-full transition-all"
                      style={{ width: `${((stats.invoiceStats?.paid || 0) / (stats.totalInvoices || 1)) * 100}%` }}
                    />
                  </div>
                </div>
                <div className="space-y-1">
                  <div className="flex items-center justify-between text-sm">
                    <span className="text-muted-foreground">Sent (Awaiting)</span>
                    <span className="font-medium text-foreground">{stats.invoiceStats?.sent || 0}</span>
                  </div>
                  <div className="h-2 bg-muted rounded-full overflow-hidden">
                    <div 
                      className="h-full bg-amber-500 rounded-full transition-all"
                      style={{ width: `${((stats.invoiceStats?.sent || 0) / (stats.totalInvoices || 1)) * 100}%` }}
                    />
                  </div>
                </div>
                <div className="space-y-1">
                  <div className="flex items-center justify-between text-sm">
                    <span className="text-muted-foreground">Draft</span>
                    <span className="font-medium text-foreground">{stats.invoiceStats?.draft || 0}</span>
                  </div>
                  <div className="h-2 bg-muted rounded-full overflow-hidden">
                    <div 
                      className="h-full bg-gray-400 rounded-full transition-all"
                      style={{ width: `${((stats.invoiceStats?.draft || 0) / (stats.totalInvoices || 1)) * 100}%` }}
                    />
                  </div>
                </div>
              </div>
            </CardContent>
          </Card>
        </div>

        {/* Summary Cards */}
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
          <Card className="border-border">
            <CardContent className="pt-6">
              <div className="flex items-center gap-4">
                <div className="p-3 rounded-lg bg-emerald-500/10">
                  <CheckCircle className="w-6 h-6 text-emerald-600" />
                </div>
                <div>
                  <p className="text-2xl font-bold text-foreground">{stats.quoteStats?.approved || 0}</p>
                  <p className="text-sm text-muted-foreground">Quotes Approved</p>
                </div>
              </div>
            </CardContent>
          </Card>
          
          <Card className="border-border">
            <CardContent className="pt-6">
              <div className="flex items-center gap-4">
                <div className="p-3 rounded-lg bg-amber-500/10">
                  <Clock className="w-6 h-6 text-amber-600" />
                </div>
                <div>
                  <p className="text-2xl font-bold text-foreground">{(stats.quoteStats?.sent || 0) + (stats.invoiceStats?.sent || 0)}</p>
                  <p className="text-sm text-muted-foreground">Awaiting Response</p>
                </div>
              </div>
            </CardContent>
          </Card>
          
          <Card className="border-border">
            <CardContent className="pt-6">
              <div className="flex items-center gap-4">
                <div className="p-3 rounded-lg bg-primary/10">
                  <Building2 className="w-6 h-6 text-primary" />
                </div>
                <div>
                  <p className="text-2xl font-bold text-foreground">{stats.totalProjects}</p>
                  <p className="text-sm text-muted-foreground">Active Projects</p>
                </div>
              </div>
            </CardContent>
          </Card>
        </div>
      </div>
    </AgentLayout>
  );
};
