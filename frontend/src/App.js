import { BrowserRouter, Routes, Route, Navigate, useLocation, Outlet } from "react-router-dom";
import { Toaster } from "./components/ui/sonner";
import { AuthProvider, useAuth } from "./context/AuthContext";
import { SettingsProvider } from "./context/SettingsContext";
import { DataProvider } from "./context/DataContext";
import { ThemeProvider } from "./components/ThemeProvider";

// Pages
import { LandingPage } from "./pages/LandingPage";
import { LoginPage } from "./pages/LoginPage";
import { RegisterPage } from "./pages/RegisterPage";
import { ForgotPasswordPage } from "./pages/ForgotPasswordPage";
import { ResetPasswordPage } from "./pages/ResetPasswordPage";
import { AuthCallback } from "./pages/AuthCallback";
import { GoogleCallbackPage } from "./pages/GoogleCallbackPage";
import { BuyerTimeline } from "./pages/buyer/BuyerTimeline";
import { AgentDashboard } from "./pages/agent/AgentDashboard";
import { AgentClients } from "./pages/agent/AgentClients";
import { AgentClientDetail } from "./pages/agent/AgentClientDetail";
import { AgentProjects } from "./pages/agent/AgentProjects";
import { AgentQuotes } from "./pages/agent/AgentQuotes";
import { AgentQuoteDetail } from "./pages/agent/AgentQuoteDetail";
import { AgentQuoteUpload } from "./pages/agent/AgentQuoteUpload";
import { AgentQuoteEdit } from "./pages/agent/AgentQuoteEdit";
import { AgentInvoices } from "./pages/agent/AgentInvoices";
import { AgentInvoiceDetail } from "./pages/agent/AgentInvoiceDetail";
import { AgentInvoiceUpload } from "./pages/agent/AgentInvoiceUpload";
import { AgentTimeline } from "./pages/agent/AgentTimeline";
import { AgentFeed } from "./pages/agent/AgentFeed";
import { AgentTeam } from "./pages/agent/AgentTeam";
import { ClientPreview } from "./pages/agent/ClientPreview";
import { AgentWorkflow } from "./pages/agent/AgentWorkflow";
import { AgentBilling } from "./pages/agent/AgentBilling";
import { AgentSettings } from "./pages/agent/AgentSettings";
import { AgentAnalytics } from "./pages/agent/AgentAnalytics";
import { AgentVault } from "./pages/agent/AgentVault";
import { AgentHomePage } from "./pages/agent/AgentHomePage";
import { AcceptInvitePage } from "./pages/AcceptInvitePage";
import { GanttChartTool } from "./pages/tools/GanttChartTool";

import "./App.css";

// Feature flag for new agent homepage - set to false to rollback to legacy dashboard
const USE_NEW_AGENT_HOME = true;

// REMINDER: DO NOT HARDCODE THE URL, OR ADD ANY FALLBACKS OR REDIRECT URLS, THIS BREAKS THE AUTH

const ProtectedRoute = ({ children, allowedRoles }) => {
  const { user, loading } = useAuth();
  const location = useLocation();
  
  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-background">
        <div className="text-center">
          <div className="w-8 h-8 border-2 border-primary border-t-transparent rounded-full animate-spin mx-auto mb-4"></div>
          <p className="text-sm text-muted-foreground">Loading...</p>
        </div>
      </div>
    );
  }
  
  if (!user) {
    return <Navigate to="/login" state={{ from: location }} replace />;
  }
  
  if (allowedRoles && !allowedRoles.includes(user.role)) {
    // Redirect to appropriate dashboard based on role
    if (user.role === 'buyer') {
      return <Navigate to="/buyer/dashboard" replace />;
    } else if (user.role === 'agent') {
      // Use feature flag to determine default agent entry point
      return <Navigate to={USE_NEW_AGENT_HOME ? "/agent/home" : "/agent/dashboard-legacy"} replace />;
    }
    return <Navigate to="/login" replace />;
  }
  
  return children;
};

/** CMP data shell — only mounts for /agent/* routes (not standalone tools). */
const CmpDataLayout = () => (
  <DataProvider>
    <Outlet />
  </DataProvider>
);

const AppRouter = () => {
  const location = useLocation();
  
  // Check URL fragment for session_id (OAuth callback) - synchronous check
  if (location.hash?.includes('session_id=')) {
    return <AuthCallback />;
  }
  
  return (
    <Routes>
      {/* Public routes */}
      <Route path="/login" element={<LoginPage />} />
      <Route path="/register" element={<RegisterPage />} />
      <Route path="/forgot-password" element={<ForgotPasswordPage />} />
      <Route path="/reset-password" element={<ResetPasswordPage />} />
      <Route path="/auth/callback" element={<AuthCallback />} />
      <Route path="/auth/google/callback" element={<GoogleCallbackPage />} />
      <Route path="/team/accept" element={<AcceptInvitePage />} />

      {/* Standalone tools — any authenticated user */}
      <Route path="/tools/gantt-chart" element={
        <ProtectedRoute>
          <GanttChartTool />
        </ProtectedRoute>
      } />
      
      {/* Buyer routes - Single timeline page */}
      <Route path="/buyer/dashboard" element={
        <ProtectedRoute allowedRoles={['buyer']}>
          <BuyerTimeline />
        </ProtectedRoute>
      } />
      <Route path="/buyer/*" element={
        <ProtectedRoute allowedRoles={['buyer']}>
          <BuyerTimeline />
        </ProtectedRoute>
      } />
      
      {/* Agent routes — CMP DataProvider scoped to /agent/* only */}
      <Route element={<CmpDataLayout />}>
        <Route path="/agent/home" element={
          <ProtectedRoute allowedRoles={['agent']}>
            <AgentHomePage />
          </ProtectedRoute>
        } />
        <Route path="/agent/dashboard-legacy" element={
          <ProtectedRoute allowedRoles={['agent']}>
            <AgentDashboard />
          </ProtectedRoute>
        } />
        <Route path="/agent/dashboard" element={
          <ProtectedRoute allowedRoles={['agent']}>
            {USE_NEW_AGENT_HOME ? <Navigate to="/agent/home" replace /> : <AgentDashboard />}
          </ProtectedRoute>
        } />
        <Route path="/agent/clients" element={
          <ProtectedRoute allowedRoles={['agent']}>
            <AgentClients />
          </ProtectedRoute>
        } />
        <Route path="/agent/clients/:clientId" element={
          <ProtectedRoute allowedRoles={['agent']}>
            <AgentClientDetail />
          </ProtectedRoute>
        } />
        <Route path="/agent/projects" element={
          <ProtectedRoute allowedRoles={['agent']}>
            <AgentProjects />
          </ProtectedRoute>
        } />
        <Route path="/agent/quotes" element={
          <ProtectedRoute allowedRoles={['agent']}>
            <AgentQuotes />
          </ProtectedRoute>
        } />
        <Route path="/agent/quotes/new" element={
          <ProtectedRoute allowedRoles={['agent']}>
            <AgentQuoteUpload />
          </ProtectedRoute>
        } />
        <Route path="/agent/quotes/:quoteId" element={
          <ProtectedRoute allowedRoles={['agent']}>
            <AgentQuoteDetail />
          </ProtectedRoute>
        } />
        <Route path="/agent/quotes/edit/:quoteId" element={
          <ProtectedRoute allowedRoles={['agent']}>
            <AgentQuoteUpload />
          </ProtectedRoute>
        } />
        <Route path="/agent/invoices" element={
          <ProtectedRoute allowedRoles={['agent']}>
            <AgentInvoices />
          </ProtectedRoute>
        } />
        <Route path="/agent/invoices/new" element={
          <ProtectedRoute allowedRoles={['agent']}>
            <AgentInvoiceUpload />
          </ProtectedRoute>
        } />
        <Route path="/agent/invoices/:invoiceId" element={
          <ProtectedRoute allowedRoles={['agent']}>
            <AgentInvoiceDetail />
          </ProtectedRoute>
        } />
        <Route path="/agent/invoices/edit/:invoiceId" element={
          <ProtectedRoute allowedRoles={['agent']}>
            <AgentInvoiceUpload />
          </ProtectedRoute>
        } />
        <Route path="/agent/timeline" element={
          <ProtectedRoute allowedRoles={['agent']}>
            <AgentTimeline />
          </ProtectedRoute>
        } />
        <Route path="/agent/feed" element={
          <ProtectedRoute allowedRoles={['agent']}>
            <AgentFeed />
          </ProtectedRoute>
        } />
        <Route path="/agent/team" element={
          <ProtectedRoute allowedRoles={['agent']}>
            <AgentTeam />
          </ProtectedRoute>
        } />
        <Route path="/agent/clients/:clientId/preview" element={
          <ProtectedRoute allowedRoles={['agent']}>
            <ClientPreview />
          </ProtectedRoute>
        } />
        <Route path="/agent/workflow" element={
          <ProtectedRoute allowedRoles={['agent']}>
            <AgentWorkflow />
          </ProtectedRoute>
        } />
        <Route path="/agent/billing" element={
          <ProtectedRoute allowedRoles={['agent']}>
            <AgentBilling />
          </ProtectedRoute>
        } />
        <Route path="/agent/settings" element={
          <ProtectedRoute allowedRoles={['agent']}>
            <AgentSettings />
          </ProtectedRoute>
        } />
        <Route path="/agent/analytics" element={
          <ProtectedRoute allowedRoles={['agent']}>
            <AgentAnalytics />
          </ProtectedRoute>
        } />
        <Route path="/agent/vault" element={
          <ProtectedRoute allowedRoles={['agent']}>
            <AgentVault />
          </ProtectedRoute>
        } />
      </Route>
      
      {/* Default redirect */}
      <Route path="/" element={<LandingPage />} />
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
};

function App() {
  return (
    <BrowserRouter>
      <ThemeProvider>
        <AuthProvider>
          <SettingsProvider>
            <AppRouter />
            <Toaster position="top-right" richColors />
          </SettingsProvider>
        </AuthProvider>
      </ThemeProvider>
    </BrowserRouter>
  );
}

export default App;
