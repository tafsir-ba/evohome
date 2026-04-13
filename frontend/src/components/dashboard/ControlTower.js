import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { Card, CardContent } from '../ui/card';
import { Button } from '../ui/button';
import { cn } from '../../lib/utils';
import { API, getAuthHeaders } from './utils';
import {
  CreditCard,
  FileText,
  Building2,
  RefreshCw,
  ArrowRight,
  Users,
  DollarSign,
  BarChart3,
  MessageSquareWarning,
  CheckSquare,
} from 'lucide-react';

export const ControlTower = ({
  projectCount = 0,
  onRefresh,
  title = 'Command Center',
  subtitle = 'What needs your attention — then share updates with clients.',
}) => {
  const navigate = useNavigate();
  const [stats, setStats] = useState(null);
  const [loading, setLoading] = useState(true);

  const fetchStats = async () => {
    setLoading(true);
    try {
      const res = await fetch(`${API}/stats/agent`, {
        credentials: 'include',
        headers: getAuthHeaders(),
      });
      if (res.ok) setStats(await res.json());
    } catch (error) {
      console.error('Failed to fetch stats:', error);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { fetchStats(); }, []);

  const handleRefresh = () => {
    fetchStats();
    if (onRefresh) onRefresh();
  };

  if (loading) {
    return (
      <div className="space-y-3" data-testid="control-tower-loading">
        <div className="flex items-center justify-between">
          <div>
            <div className="h-7 w-40 bg-muted rounded animate-pulse" />
            <div className="h-4 w-56 bg-muted rounded animate-pulse mt-1" />
          </div>
        </div>
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
          {[1, 2, 3].map((i) => <div key={i} className="h-20 bg-muted rounded-lg animate-pulse" />)}
        </div>
        <div className="grid grid-cols-4 gap-3">
          {[1, 2, 3, 4].map((i) => <div key={i} className="h-16 bg-muted rounded-lg animate-pulse" />)}
        </div>
      </div>
    );
  }

  if (!stats) return null;

  return (
    <>
      {/* Header */}
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <h1 className="text-xl sm:text-2xl font-outfit font-semibold text-foreground tracking-tight">
            {title}
          </h1>
          <p className="text-xs sm:text-sm text-muted-foreground mt-0.5">
            {subtitle}
          </p>
        </div>
        <Button
          variant="ghost"
          size="sm"
          onClick={handleRefresh}
          className="text-muted-foreground hover:text-foreground shrink-0"
          data-testid="refresh-dashboard-btn"
        >
          <RefreshCw className="w-4 h-4" />
        </Button>
      </div>

      <p className="text-xs font-medium text-muted-foreground uppercase tracking-wide">Needs attention</p>
      {/* Action Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-3" data-testid="action-cards">
        <ActionCard
          count={(stats.change_requests?.length || 0) + (stats.open_change_requests || 0)}
          label="Change Requests"
          icon={MessageSquareWarning}
          activeColor="amber"
          onClick={() => navigate('/agent/documents')}
          testId="action-card-change-requests"
        />
        <ActionCard
          count={stats.pending_invoices || 0}
          label="Pending Invoices"
          icon={CreditCard}
          activeColor="red"
          onClick={() => navigate('/agent/documents')}
          testId="action-card-pending-invoices"
        />
        <ActionCard
          count={stats.pending_quotes || 0}
          label="Pending Quotes"
          icon={FileText}
          activeColor="blue"
          onClick={() => navigate('/agent/documents')}
          testId="action-card-pending-quotes"
        />
        <ActionCard
          count={(stats.pending_decisions || 0) + (stats.challenged_decisions || 0)}
          label="Pending Decisions"
          icon={CheckSquare}
          activeColor="amber"
          onClick={() => navigate('/agent/decisions')}
          testId="action-card-pending-decisions"
        />
      </div>

      <p className="text-xs font-medium text-muted-foreground uppercase tracking-wide pt-2">Overview</p>
      {/* KPI Strip */}
      <div className="grid grid-cols-1 sm:grid-cols-2 xl:grid-cols-4 gap-3" data-testid="kpi-strip">
        <KpiItem icon={Users} value={stats.total_clients || 0} label="Total Clients" />
        <KpiItem icon={Building2} value={projectCount} label="Active Projects" />
        <KpiItem
          icon={DollarSign}
          value={new Intl.NumberFormat('de-CH', { notation: 'compact', maximumFractionDigits: 1 }).format(stats.total_revenue || 0)}
          label="Revenue (CHF)"
        />
        <KpiItem icon={BarChart3} value={stats.approved_quotes?.length || 0} label="Approved Quotes" />
      </div>
    </>
  );
};

const ActionCard = ({ count, label, icon: Icon, activeColor, onClick, testId }) => {
  const isActive = count > 0;
  const colorMap = {
    amber: { border: 'border-amber-500/40 bg-amber-500/5', bg: 'bg-amber-500/15', text: 'text-amber-600' },
    red: { border: 'border-red-500/30 bg-red-500/5', bg: 'bg-red-500/15', text: 'text-red-600' },
    blue: { border: 'border-blue-500/30 bg-blue-500/5', bg: 'bg-blue-500/15', text: 'text-blue-600' },
  };
  const colors = colorMap[activeColor] || colorMap.blue;

  return (
    <Card
      className={cn(
        'border-border cursor-pointer transition-all hover:shadow-md group',
        isActive && colors.border
      )}
      onClick={onClick}
      data-testid={testId}
    >
      <CardContent className="py-4 px-4 sm:px-5">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2.5 min-w-0">
            <div className={cn('w-9 h-9 sm:w-10 sm:h-10 rounded-lg flex items-center justify-center flex-shrink-0', isActive ? colors.bg : 'bg-muted')}>
              <Icon className={cn('w-4 h-4 sm:w-5 sm:h-5', isActive ? colors.text : 'text-muted-foreground')} />
            </div>
            <div className="min-w-0">
              <p className="text-xl sm:text-2xl font-semibold font-outfit">{count}</p>
              <p className="text-xs text-muted-foreground truncate">{label}</p>
            </div>
          </div>
          <ArrowRight className="w-4 h-4 text-muted-foreground opacity-0 group-hover:opacity-100 transition-opacity" />
        </div>
      </CardContent>
    </Card>
  );
};

const KpiItem = ({ icon: Icon, value, label }) => (
  <div className="flex items-center gap-3 p-3 rounded-lg border border-border bg-card min-w-0">
    <Icon className="w-4 h-4 text-muted-foreground flex-shrink-0" />
    <div className="min-w-0">
      <p className="text-lg font-semibold font-outfit truncate">{value}</p>
      <p className="text-[11px] text-muted-foreground truncate">{label}</p>
    </div>
  </div>
);
