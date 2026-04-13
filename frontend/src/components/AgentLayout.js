import { Link, useLocation } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { useSettings } from '../context/SettingsContext';
import { cn } from '../lib/utils';
import { 
  Home, 
  Users, 
  FileText, 
  LogOut,
  Menu,
  X,
  Building2,
  MessageSquare,
  UserCircle,
  GitBranch,
  Settings,
  BarChart3,
  FolderArchive,
  MoreHorizontal,
  ChevronDown,
  ChevronUp,
  CheckSquare,
  Shield
} from 'lucide-react';
import { useEffect, useState } from 'react';
import { Button } from './ui/button';
import { ThemeToggle } from './ThemeToggle';
import { NotificationCenter } from './NotificationCenter';

export const AgentLayout = ({ children }) => {
  const { user, logout } = useAuth();
  const { t, getLogo, getCompanyName } = useSettings();
  const location = useLocation();
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [moreExpanded, setMoreExpanded] = useState(false);

  const logoUrl = getLogo();
  const companyName = getCompanyName();

  const isPlatformAdmin = (user?.email || '').toLowerCase() === 'tafsir@evo-home.ch';

  // Primary navigation items
  const navigation = [
    { name: t('nav.dashboard'), href: '/agent/home', icon: Home },
    { name: t('nav.projects'), href: '/agent/projects', icon: Building2 },
    { name: t('nav.clients'), href: '/agent/clients', icon: Users },
    { name: t('nav.timeline'), href: '/agent/workflow', icon: GitBranch },
    { name: t('nav.team'), href: '/agent/team', icon: UserCircle },
    { name: t('nav.feed'), href: '/agent/feed', icon: MessageSquare },
    { name: 'Decisions', href: '/agent/decisions', icon: CheckSquare },
    { name: t('nav.quotes') + ' / ' + t('nav.invoices'), href: '/agent/documents', icon: FileText },
    ...(isPlatformAdmin ? [{ name: 'Admin', href: '/agent/admin', icon: Shield }] : []),
    { name: t('nav.settings'), href: '/agent/settings', icon: Settings },
  ];

  // Secondary navigation (in "More" menu)
  const moreNavigation = [
    { name: 'Vault', href: '/agent/vault', icon: FolderArchive },
    { name: t('nav.analytics'), href: '/agent/analytics', icon: BarChart3 },
  ];

  // Check if any "more" item is currently active
  const isMoreActive = moreNavigation.some(item => 
    location.pathname === item.href || location.pathname.startsWith(item.href + '/')
  );

  const isActive = (href) => location.pathname === href || location.pathname.startsWith(href + '/');
  const inPrimary = navigation.find((item) => isActive(item.href));
  const inMore = moreNavigation.find((item) => isActive(item.href));
  const activeItemLabel = inPrimary?.name || inMore?.name || t('nav.dashboard');
  const mobileQuickNavigation = [
    { name: t('nav.dashboard'), mobileName: t('nav.dashboard'), href: '/agent/home', icon: Home },
    { name: t('nav.projects'), mobileName: t('nav.projects'), href: '/agent/projects', icon: Building2 },
    { name: t('nav.feed'), mobileName: t('nav.feed'), href: '/agent/feed', icon: MessageSquare },
    { name: t('nav.quotes') + ' / ' + t('nav.invoices'), mobileName: 'Docs', href: '/agent/documents', icon: FileText },
  ];

  useEffect(() => {
    setSidebarOpen(false);
  }, [location.pathname]);

  return (
    <div className="min-h-screen bg-background transition-colors overflow-x-hidden">
      {/* Mobile sidebar backdrop */}
      {sidebarOpen && (
        <div 
          className="fixed inset-0 bg-black/40 backdrop-blur-sm z-40 lg:hidden"
          onClick={() => setSidebarOpen(false)}
        />
      )}
      
      {/* Sidebar */}
      <aside className={cn(
        "fixed left-0 top-0 h-screen w-[86vw] max-w-72 lg:w-64 bg-card border-r border-border z-50 transition-transform duration-300",
        sidebarOpen ? "translate-x-0" : "-translate-x-full lg:translate-x-0"
      )}>
        <div className="flex flex-col h-full">
          {/* Logo */}
          <div className="flex items-center justify-between px-6 h-16 border-b border-border">
            <Link to="/agent/home" className="flex items-center gap-3" data-testid="logo-link">
              {logoUrl ? (
                <img 
                  src={logoUrl} 
                  alt={companyName} 
                  className="w-9 h-9 rounded-lg object-contain"
                />
              ) : (
                <div className="w-9 h-9 bg-primary rounded-lg flex items-center justify-center shadow-sm">
                  <Home className="w-5 h-5 text-primary-foreground" />
                </div>
              )}
              <span className="text-lg font-outfit font-semibold text-foreground tracking-tight">{companyName}</span>
            </Link>
            <button 
              className="lg:hidden p-1.5 hover:bg-muted rounded-lg transition-colors"
              onClick={() => setSidebarOpen(false)}
            >
              <X className="w-5 h-5" />
            </button>
          </div>
          
          {/* Navigation */}
          <nav className="flex-1 px-3 py-6 space-y-1 overflow-y-auto">
            {navigation.map((item) => {
              const Icon = item.icon;
              const active = isActive(item.href);
              return (
                <Link
                  key={item.href}
                  to={item.href}
                  onClick={() => setSidebarOpen(false)}
                  className={cn(
                    "flex items-center gap-3 px-3 py-3 lg:py-2.5 rounded-lg text-sm font-medium transition-all duration-200",
                    active 
                      ? "bg-primary/10 text-primary shadow-sm" 
                      : "text-muted-foreground hover:bg-muted hover:text-foreground"
                  )}
                  data-testid={`nav-${item.href.split('/').pop()}`}
                >
                  <Icon className={cn("w-5 h-5", active && "text-primary")} />
                  {item.name}
                </Link>
              );
            })}
            
            {/* More Menu */}
            <div className="pt-2">
              <button
                onClick={() => setMoreExpanded(!moreExpanded)}
                className={cn(
                  "w-full flex items-center justify-between gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-all duration-200",
                  isMoreActive
                    ? "bg-primary/10 text-primary shadow-sm"
                    : "text-muted-foreground hover:bg-muted hover:text-foreground"
                )}
                data-testid="nav-more-toggle"
              >
                <div className="flex items-center gap-3">
                  <MoreHorizontal className={cn("w-5 h-5", isMoreActive && "text-primary")} />
                  More
                </div>
                {moreExpanded ? (
                  <ChevronUp className="w-4 h-4" />
                ) : (
                  <ChevronDown className="w-4 h-4" />
                )}
              </button>
              
              {moreExpanded && (
                <div className="mt-1 ml-4 space-y-1 border-l border-border pl-2">
                  {moreNavigation.map((item) => {
                    const Icon = item.icon;
                    const active = isActive(item.href);
                    return (
                      <Link
                        key={item.href}
                        to={item.href}
                        onClick={() => setSidebarOpen(false)}
                        className={cn(
                          "flex items-center gap-3 px-3 py-2.5 lg:py-2 rounded-lg text-sm font-medium transition-all duration-200",
                          active 
                            ? "bg-primary/10 text-primary" 
                            : "text-muted-foreground hover:bg-muted hover:text-foreground"
                        )}
                        data-testid={`nav-${item.href.split('/').pop()}`}
                      >
                        <Icon className={cn("w-4 h-4", active && "text-primary")} />
                        {item.name}
                      </Link>
                    );
                  })}
                </div>
              )}
            </div>
          </nav>
          
          {/* User section */}
          <div className="px-3 py-4 border-t border-border">
            <div className="flex items-center gap-3 px-3 py-2 mb-2">
              <div className="w-9 h-9 bg-primary/10 rounded-lg flex items-center justify-center text-primary text-sm font-semibold">
                {user?.name?.charAt(0) || 'A'}
              </div>
              <div className="flex-1 min-w-0">
                <p className="text-sm font-medium text-foreground truncate">{user?.name}</p>
                <p className="text-xs text-muted-foreground truncate">{user?.email}</p>
              </div>
            </div>
            <Button
              variant="ghost"
              className="w-full justify-start text-muted-foreground hover:text-destructive hover:bg-destructive/10 rounded-lg"
              onClick={logout}
              data-testid="logout-btn"
            >
              <LogOut className="w-4 h-4 mr-3" />
              {t('nav.logout')}
            </Button>
          </div>
        </div>
      </aside>
      
      {/* Main content */}
      <div className="lg:pl-64">
        {/* Top bar */}
        <header className="sticky top-0 z-30 bg-background/80 backdrop-blur-xl border-b border-border h-16 flex items-center px-3 sm:px-4 lg:px-6">
          <button 
            className="lg:hidden p-2 hover:bg-muted rounded-lg mr-2 transition-colors"
            onClick={() => setSidebarOpen(true)}
          >
            <Menu className="w-5 h-5" />
          </button>
          <div className="flex-1 min-w-0">
            <p className="text-sm font-medium text-foreground truncate lg:hidden">{activeItemLabel}</p>
          </div>
          <div className="flex items-center gap-1 sm:gap-2">
            <NotificationCenter />
            <ThemeToggle />
          </div>
        </header>
        
        {/* Page content */}
        <main className="p-3 sm:p-4 lg:p-6 pb-24 lg:pb-6">
          {children}
        </main>
      </div>

      {/* Mobile bottom quick navigation */}
      <nav className="fixed bottom-0 left-0 right-0 z-30 border-t border-border bg-background/95 backdrop-blur lg:hidden">
        <div className="grid grid-cols-4 px-2 py-1.5">
          {mobileQuickNavigation.map((item) => {
            const Icon = item.icon;
            const active = isActive(item.href);
            return (
              <Link
                key={item.href}
                to={item.href}
                className={cn(
                  'flex flex-col items-center justify-center gap-1 rounded-lg px-1 py-2 text-[11px] font-medium transition-colors',
                  active ? 'text-primary bg-primary/10' : 'text-muted-foreground'
                )}
                data-testid={`mobile-nav-${item.href.split('/').pop()}`}
              >
                <Icon className="w-4 h-4" />
                <span className="truncate max-w-full">
                  {item.mobileName || item.name}
                </span>
              </Link>
            );
          })}
        </div>
      </nav>
    </div>
  );
};
