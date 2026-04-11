import { Link, useLocation } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { useSettings } from '../context/SettingsContext';
import { cn } from '../lib/utils';
import { 
  Home, 
  Users, 
  FileText, 
  Receipt, 
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
  CheckSquare
} from 'lucide-react';
import { useState } from 'react';
import { Button } from './ui/button';
import { ThemeToggle } from './ThemeToggle';
import { NotificationCenter } from './NotificationCenter';
import { LanguageToggle } from './LanguageToggle';

const API = process.env.REACT_APP_BACKEND_URL;

export const AgentLayout = ({ children }) => {
  const { user, logout } = useAuth();
  const { t, getLogo, getCompanyName } = useSettings();
  const location = useLocation();
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [moreExpanded, setMoreExpanded] = useState(false);

  const logoUrl = getLogo();
  const companyName = getCompanyName();

  // Primary navigation items
  const navigation = [
    { name: t('nav.dashboard'), href: '/agent/home', icon: Home },
    { name: t('nav.projects'), href: '/agent/projects', icon: Building2 },
    { name: t('nav.clients'), href: '/agent/clients', icon: Users },
    { name: t('nav.timeline'), href: '/agent/workflow', icon: GitBranch },
    { name: t('nav.team'), href: '/agent/team', icon: UserCircle },
    { name: t('nav.feed'), href: '/agent/feed', icon: MessageSquare },
    { name: 'Decisions', href: '/agent/decisions', icon: CheckSquare },
    { name: t('nav.quotes'), href: '/agent/quotes', icon: FileText },
    { name: t('nav.invoices'), href: '/agent/invoices', icon: Receipt },
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

  return (
    <div className="min-h-screen bg-background transition-colors">
      {/* Mobile sidebar backdrop */}
      {sidebarOpen && (
        <div 
          className="fixed inset-0 bg-black/40 backdrop-blur-sm z-40 lg:hidden"
          onClick={() => setSidebarOpen(false)}
        />
      )}
      
      {/* Sidebar */}
      <aside className={cn(
        "fixed left-0 top-0 h-screen w-64 bg-card border-r border-border z-50 transition-transform duration-300",
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
                  className={cn(
                    "flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-all duration-200",
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
                        className={cn(
                          "flex items-center gap-3 px-3 py-2 rounded-lg text-sm font-medium transition-all duration-200",
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
        <header className="sticky top-0 z-30 bg-background/80 backdrop-blur-xl border-b border-border h-16 flex items-center px-6">
          <button 
            className="lg:hidden p-2 hover:bg-muted rounded-lg mr-4 transition-colors"
            onClick={() => setSidebarOpen(true)}
          >
            <Menu className="w-5 h-5" />
          </button>
          <div className="flex-1" />
          <div className="flex items-center gap-2">
            <LanguageToggle />
            <NotificationCenter />
            <ThemeToggle />
          </div>
        </header>
        
        {/* Page content */}
        <main className="p-6">
          {children}
        </main>
      </div>
    </div>
  );
};
