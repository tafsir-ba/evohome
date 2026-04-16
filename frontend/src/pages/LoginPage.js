import { useState } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { toast } from 'sonner';
import { parseApiError } from '../lib/api';
import { User, Briefcase, Building2, ShoppingBag, Mail, Lock, Loader2, ArrowLeft, Sparkles } from 'lucide-react';
import { ThemeToggle } from '../components/ThemeToggle';
import { cn } from '../lib/utils';

const API = process.env.REACT_APP_BACKEND_URL + '/api';

export const LoginPage = () => {
  const [demoLoading, setDemoLoading] = useState(null);
  const [googleLoading, setGoogleLoading] = useState(false);
  const [emailLoading, setEmailLoading] = useState(false);
  const [selectedRole, setSelectedRole] = useState('buyer');
  const [authMode, setAuthMode] = useState('select'); // 'select', 'email-login', 'email-register'
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [name, setName] = useState('');
  const { loginWithGoogle, enterDemo, setAuthUser } = useAuth();
  const navigate = useNavigate();

  const handleGoogleLogin = (role) => {
    setGoogleLoading(true);
    loginWithGoogle(role);
  };

  const handleDemoEnter = async (persona, buyerSlot = 1) => {
    const key = persona === 'buyer' ? `buyer${buyerSlot}` : 'agent';
    setDemoLoading(key);
    try {
      const data = await enterDemo({ persona, buyerSlot, fresh: true });
      toast.success(
        persona === 'agent'
          ? 'Demo agent ready — fresh sample data loaded.'
          : 'Demo buyer ready — fresh sample data loaded.'
      );
      navigate(data.redirect || (persona === 'agent' ? '/agent/home' : '/buyer/dashboard'));
    } catch (error) {
      toast.error(error.message);
    } finally {
      setDemoLoading(null);
    }
  };

  const handleEmailAuth = async (e) => {
    e.preventDefault();
    setEmailLoading(true);
    
    try {
      const isRegister = authMode === 'email-register';
      const endpoint = selectedRole === 'agent' 
        ? isRegister ? '/auth/register' : '/auth/login'
        : isRegister ? '/auth/buyer/register' : '/auth/buyer/login';
      
      const body = isRegister 
        ? { email, password, name }
        : { email, password };
      
      const res = await fetch(`${API}${endpoint}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
        body: JSON.stringify(body)
      });
      
      if (res.ok) {
        const data = await res.json();
        if (data.token) {
          localStorage.setItem('auth_token', data.token);
        }
        setAuthUser(data);
        toast.success(isRegister ? 'Account created successfully!' : 'Login successful!');
        navigate(selectedRole === 'agent' ? '/agent/home' : '/buyer/dashboard');
      } else {
        const error = await parseApiError(res);
        throw new Error(error.message || 'Authentication failed');
      }
    } catch (error) {
      toast.error(error.message);
    } finally {
      setEmailLoading(false);
    }
  };

  const resetForm = () => {
    setEmail('');
    setPassword('');
    setName('');
    setAuthMode('select');
  };

  return (
    <div className="min-h-screen bg-background flex transition-colors">
      {/* Left Panel - Hero */}
      <div className="hidden lg:flex lg:w-1/2 bg-gradient-to-br from-slate-900 via-slate-800 to-slate-900 dark:from-black dark:via-slate-900 dark:to-black relative overflow-hidden">
        <div 
          className="absolute inset-0 opacity-20"
          style={{
            backgroundImage: `radial-gradient(circle at 25% 25%, rgba(37, 99, 235, 0.4) 0%, transparent 50%),
                             radial-gradient(circle at 75% 75%, rgba(59, 130, 246, 0.3) 0%, transparent 50%)`,
          }}
        />
        <div 
          className="absolute inset-0 opacity-5"
          style={{
            backgroundImage: `url("data:image/svg+xml,%3Csvg width='60' height='60' viewBox='0 0 60 60' xmlns='http://www.w3.org/2000/svg'%3E%3Cg fill='none' fill-rule='evenodd'%3E%3Cg fill='%23ffffff' fill-opacity='0.4'%3E%3Cpath d='M36 34v-4h-2v4h-4v2h4v4h2v-4h4v-2h-4zm0-30V0h-2v4h-4v2h4v4h2V6h4V4h-4zM6 34v-4H4v4H0v2h4v4h2v-4h4v-2H6zM6 4V0H4v4H0v2h4v4h2V6h4V4H6z'/%3E%3C/g%3E%3C/g%3E%3C/svg%3E")`,
          }}
        />
        <div className="relative z-10 flex flex-col justify-between p-12 w-full">
          <div>
            <Link to="/" className="flex items-center gap-3 mb-20">
              <img 
                src="/evohome-logo-white.png" 
                alt="Evohome" 
                className="h-10 w-auto"
              />
            </Link>
            
            <h1 className="text-5xl lg:text-6xl font-outfit font-bold text-white leading-[1.1] mb-8">
              Post-Sale<br />Management<br />
              <span className="bg-gradient-to-r from-blue-400 to-sky-400 bg-clip-text text-transparent">Simplified.</span>
            </h1>
            
            <p className="text-white/60 text-lg max-w-md leading-relaxed">
              Streamline your real estate post-sale workflow. Manage upgrades, approvals, invoices, and payments in one place.
            </p>
          </div>
          
          <div className="space-y-4">
            <div className="flex items-center gap-4 text-white/40 text-sm">
              <div className="w-12 h-[1px] bg-gradient-to-r from-white/30 to-transparent" />
              <span>Trusted by developers across Switzerland</span>
            </div>
          </div>
        </div>
      </div>
      
      {/* Right Panel - Login Form */}
      <div className="flex-1 flex flex-col px-6 sm:px-8 lg:px-16 py-8">
        {/* Header */}
        <div className="flex items-center justify-between mb-8">
          <div className="lg:hidden flex items-center gap-3">
            <Link to="/">
              <img 
                src="/evohome-logo.png" 
                alt="Evohome" 
                className="h-8 w-auto"
              />
            </Link>
          </div>
          <div className="lg:ml-auto">
            <ThemeToggle />
          </div>
        </div>
        
        <div className="flex-1 flex items-center justify-center">
          <div className="max-w-md w-full">
            {authMode === 'select' ? (
              <>
                <div className="mb-8">
                  <h2 className="text-2xl sm:text-3xl font-outfit font-bold text-foreground mb-2">Welcome</h2>
                  <p className="text-muted-foreground text-sm sm:text-base">Select your role to sign in</p>
                </div>
                
                {/* Role Selection Tabs */}
                <div className="flex gap-2 p-1 bg-muted rounded-xl mb-6">
                  <button
                    onClick={() => setSelectedRole('buyer')}
                    className={cn(
                      "flex-1 flex items-center justify-center gap-2 py-3 px-4 rounded-lg text-sm font-medium transition-all",
                      selectedRole === 'buyer'
                        ? "bg-background text-foreground shadow-sm"
                        : "text-muted-foreground hover:text-foreground"
                    )}
                    data-testid="role-tab-buyer"
                  >
                    <ShoppingBag className="w-4 h-4" />
                    <span className="hidden sm:inline">I'm a</span> Buyer
                  </button>
                  <button
                    onClick={() => setSelectedRole('agent')}
                    className={cn(
                      "flex-1 flex items-center justify-center gap-2 py-3 px-4 rounded-lg text-sm font-medium transition-all",
                      selectedRole === 'agent'
                        ? "bg-background text-foreground shadow-sm"
                        : "text-muted-foreground hover:text-foreground"
                    )}
                    data-testid="role-tab-agent"
                  >
                    <Building2 className="w-4 h-4" />
                    <span className="hidden sm:inline">I'm an</span> Agent
                  </button>
                </div>

                {/* Auth Options */}
                <div className="space-y-4">
                  {/* Google Login - Primary */}
                  <div className={cn(
                    "p-4 sm:p-5 rounded-xl border",
                    selectedRole === 'buyer' 
                      ? "bg-blue-500/5 border-blue-500/20" 
                      : "bg-emerald-500/5 border-emerald-500/20"
                  )}>
                    <p className="text-sm text-foreground mb-4">
                      {selectedRole === 'buyer' 
                        ? 'View quotes, approve upgrades, and manage your property.'
                        : 'Manage clients, create quotes, and track payments.'}
                    </p>
                    
                    <Button
                      type="button"
                      className={cn(
                        "w-full h-11 sm:h-12 rounded-xl font-medium shadow-lg transition-all",
                        selectedRole === 'buyer'
                          ? "bg-primary hover:bg-primary/90 text-primary-foreground shadow-primary/25"
                          : "bg-emerald-600 hover:bg-emerald-700 text-white shadow-emerald-600/25"
                      )}
                      onClick={() => handleGoogleLogin(selectedRole)}
                      disabled={googleLoading}
                      data-testid={`google-login-${selectedRole}-btn`}
                    >
                      {googleLoading ? (
                        <Loader2 className="w-5 h-5 animate-spin" />
                      ) : (
                        <>
                          <svg className="w-5 h-5 mr-3" viewBox="0 0 24 24">
                            <path fill="currentColor" d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"/>
                            <path fill="currentColor" d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"/>
                            <path fill="currentColor" d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z"/>
                            <path fill="currentColor" d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z"/>
                          </svg>
                          Continue with Google
                        </>
                      )}
                    </Button>
                    
                    <div className="relative my-4">
                      <div className="absolute inset-0 flex items-center">
                        <div className="w-full border-t border-border" />
                      </div>
                      <div className="relative flex justify-center text-xs">
                        <span className="bg-background px-2 text-muted-foreground">or</span>
                      </div>
                    </div>
                    
                    <Button
                      variant="outline"
                      className="w-full h-11 rounded-xl"
                      onClick={() => setAuthMode('email-login')}
                      data-testid={`email-login-${selectedRole}-btn`}
                    >
                      <Mail className="w-4 h-4 mr-2" />
                      Continue with Email
                    </Button>
                  </div>
                  
                  {/* Demo — resets sandbox data then signs you in */}
                  <div className="p-4 bg-muted/50 rounded-xl border border-border space-y-3">
                    <div className="flex items-start gap-2">
                      <Sparkles className="w-4 h-4 text-primary shrink-0 mt-0.5" />
                      <div>
                        <p className="text-xs font-semibold tracking-widest uppercase text-muted-foreground">
                          Try demo
                        </p>
                        <p className="text-xs text-muted-foreground mt-1 leading-relaxed">
                          Loads a clean sample project each time, then opens the app with a demo account.
                        </p>
                      </div>
                    </div>
                    {selectedRole === 'buyer' ? (
                      <div className="grid grid-cols-2 gap-2">
                        {[
                          { slot: 1, label: 'Sophie' },
                          { slot: 2, label: 'Thomas' },
                          { slot: 3, label: 'Luca' },
                          { slot: 4, label: 'Emma' },
                        ].map(({ slot, label }) => (
                          <Button
                            key={slot}
                            type="button"
                            variant="outline"
                            className="h-10 sm:h-11 rounded-xl border-border hover:border-primary hover:bg-primary/5 hover:text-primary text-xs transition-all"
                            onClick={() => handleDemoEnter('buyer', slot)}
                            disabled={demoLoading !== null}
                            data-testid={slot === 1 ? 'demo-buyer-btn' : `demo-buyer-${slot}-btn`}
                          >
                            {demoLoading === `buyer${slot}` ? (
                              <Loader2 className="w-4 h-4 animate-spin" />
                            ) : (
                              <>
                                <User className="w-3 h-3 mr-1" />
                                {label}
                              </>
                            )}
                          </Button>
                        ))}
                      </div>
                    ) : (
                      <Button
                        type="button"
                        variant="outline"
                        className="w-full h-10 sm:h-11 rounded-xl border-border hover:border-emerald-600 hover:bg-emerald-600/5 hover:text-emerald-600 transition-all"
                        onClick={() => handleDemoEnter('agent')}
                        disabled={demoLoading !== null}
                        data-testid="demo-agent-btn"
                      >
                        {demoLoading === 'agent' ? (
                          <Loader2 className="w-4 h-4 animate-spin" />
                        ) : (
                          <>
                            <Briefcase className="w-4 h-4 mr-2" />
                            Agent — Marc Dubois
                          </>
                        )}
                      </Button>
                    )}
                  </div>
                </div>
              </>
            ) : (
              /* Email Login/Register Form */
              <div>
                <button 
                  onClick={resetForm}
                  className="flex items-center gap-2 text-sm text-muted-foreground hover:text-foreground mb-6 transition-colors"
                >
                  <ArrowLeft className="w-4 h-4" />
                  Back
                </button>
                
                <div className="mb-6">
                  <h2 className="text-2xl font-outfit font-bold text-foreground mb-1">
                    {authMode === 'email-register' ? 'Create Account' : 'Sign In'}
                  </h2>
                  <p className="text-sm text-muted-foreground">
                    {authMode === 'email-register' 
                      ? `Create your ${selectedRole} account`
                      : `Sign in to your ${selectedRole} account`}
                  </p>
                </div>
                
                <form onSubmit={handleEmailAuth} className="space-y-4">
                  {authMode === 'email-register' && (
                    <div className="space-y-2">
                      <Label htmlFor="name">Full Name</Label>
                      <Input
                        id="name"
                        type="text"
                        value={name}
                        onChange={(e) => setName(e.target.value)}
                        placeholder="John Doe"
                        required
                        className="h-11 rounded-lg"
                      />
                    </div>
                  )}
                  
                  <div className="space-y-2">
                    <Label htmlFor="email">Email</Label>
                    <div className="relative">
                      <Mail className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
                      <Input
                        id="email"
                        type="email"
                        value={email}
                        onChange={(e) => setEmail(e.target.value)}
                        placeholder="you@example.com"
                        required
                        className="h-11 rounded-lg pl-10"
                      />
                    </div>
                  </div>
                  
                  <div className="space-y-2">
                    <div className="flex items-center justify-between">
                      <Label htmlFor="password">Password</Label>
                      {authMode === 'email-login' && (
                        <Link 
                          to="/forgot-password" 
                          className="text-xs text-primary hover:underline"
                          data-testid="forgot-password-link"
                        >
                          Forgot password?
                        </Link>
                      )}
                    </div>
                    <div className="relative">
                      <Lock className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
                      <Input
                        id="password"
                        type="password"
                        value={password}
                        onChange={(e) => setPassword(e.target.value)}
                        placeholder="••••••••"
                        required
                        minLength={6}
                        className="h-11 rounded-lg pl-10"
                      />
                    </div>
                  </div>
                  
                  <Button
                    type="submit"
                    className={cn(
                      "w-full h-11 rounded-lg font-medium",
                      selectedRole === 'agent' && "bg-emerald-600 hover:bg-emerald-700"
                    )}
                    disabled={emailLoading}
                  >
                    {emailLoading ? (
                      <Loader2 className="w-4 h-4 animate-spin" />
                    ) : (
                      authMode === 'email-register' ? 'Create Account' : 'Sign In'
                    )}
                  </Button>
                </form>
                
                <p className="mt-4 text-center text-sm text-muted-foreground">
                  {authMode === 'email-register' ? (
                    <>
                      Already have an account?{' '}
                      <button 
                        onClick={() => setAuthMode('email-login')}
                        className="text-primary hover:underline font-medium"
                      >
                        Sign in
                      </button>
                    </>
                  ) : (
                    <>
                      Don't have an account?{' '}
                      <button 
                        onClick={() => setAuthMode('email-register')}
                        className="text-primary hover:underline font-medium"
                      >
                        Create one
                      </button>
                    </>
                  )}
                </p>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};
