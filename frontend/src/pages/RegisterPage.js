import { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { toast } from 'sonner';
import { Building2, ArrowRight, ArrowLeft } from 'lucide-react';

export const RegisterPage = () => {
  const [name, setName] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const { register } = useAuth();
  const navigate = useNavigate();

  const handleSubmit = async (e) => {
    e.preventDefault();
    
    if (password !== confirmPassword) {
      toast.error('Passwords do not match');
      return;
    }
    
    if (password.length < 6) {
      toast.error('Password must be at least 6 characters');
      return;
    }
    
    setIsLoading(true);
    
    try {
      await register(name, email, password);
      toast.success('Account created successfully!');
      navigate('/agent/home');
    } catch (error) {
      toast.error(error.message);
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-white flex">
      {/* Left Panel - Hero */}
      <div className="hidden lg:flex lg:w-1/2 bg-[#2E3A45] relative overflow-hidden">
        <div className="absolute inset-0 bg-gradient-to-br from-[#2E3A45] to-[#1a2329]" />
        <div 
          className="absolute inset-0 opacity-10"
          style={{
            backgroundImage: `url("data:image/svg+xml,%3Csvg width='60' height='60' viewBox='0 0 60 60' xmlns='http://www.w3.org/2000/svg'%3E%3Cg fill='none' fill-rule='evenodd'%3E%3Cg fill='%23ffffff' fill-opacity='0.4'%3E%3Cpath d='M36 34v-4h-2v4h-4v2h4v4h2v-4h4v-2h-4zm0-30V0h-2v4h-4v2h4v4h2V6h4V4h-4zM6 34v-4H4v4H0v2h4v4h2v-4h4v-2H6zM6 4V0H4v4H0v2h4v4h2V6h4V4H6z'/%3E%3C/g%3E%3C/g%3E%3C/svg%3E")`,
          }}
        />
        <div className="relative z-10 flex flex-col justify-between p-12 w-full">
          <div>
            <div className="flex items-center gap-3 mb-16">
              <img 
                src="/evohome-logo-white.png" 
                alt="Evohome" 
                className="h-10 w-auto"
              />
            </div>
            
            <h1 className="text-4xl lg:text-5xl font-outfit font-bold text-white leading-tight mb-6">
              Join<br />
              <span className="text-primary">Evohome</span><br />
              Today.
            </h1>
            
            <p className="text-white/70 text-lg max-w-md leading-relaxed">
              Create your agent account and start managing post-sale workflows with precision and clarity.
            </p>
          </div>
          
          <div className="space-y-4">
            <div className="flex items-center gap-4 text-white/60 text-sm">
              <div className="w-8 h-[1px] bg-white/30" />
              <span>Swiss precision for real estate</span>
            </div>
          </div>
        </div>
      </div>
      
      {/* Right Panel - Register Form */}
      <div className="flex-1 flex flex-col justify-center px-8 lg:px-16 py-12">
        <div className="lg:hidden flex items-center gap-3 mb-12">
          <img 
            src="/evohome-logo.png" 
            alt="Evohome" 
            className="h-8 w-auto"
          />
        </div>
        
        <div className="max-w-md w-full mx-auto">
          <Link 
            to="/login" 
            className="inline-flex items-center text-sm text-muted-foreground hover:text-primary mb-8 transition-colors"
            data-testid="back-to-login"
          >
            <ArrowLeft className="w-4 h-4 mr-2" />
            Back to login
          </Link>
          
          <div className="mb-10">
            <h2 className="text-3xl font-outfit font-semibold text-[#1A1A1A] mb-2">Create your account</h2>
            <p className="text-muted-foreground">Register as an agent to get started</p>
          </div>
          
          <form onSubmit={handleSubmit} className="space-y-5">
            <div className="space-y-2">
              <Label htmlFor="name" className="text-sm font-medium">Full Name</Label>
              <Input
                id="name"
                type="text"
                value={name}
                onChange={(e) => setName(e.target.value)}
                className="h-12 rounded-sm border-[#E2E8F0] focus:border-primary focus:ring-primary"
                placeholder="Marc Dubois"
                required
                data-testid="name-input"
              />
            </div>
            
            <div className="space-y-2">
              <Label htmlFor="email" className="text-sm font-medium">Email</Label>
              <Input
                id="email"
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                className="h-12 rounded-sm border-[#E2E8F0] focus:border-primary focus:ring-primary"
                placeholder="agent@company.com"
                required
                data-testid="email-input"
              />
            </div>
            
            <div className="space-y-2">
              <Label htmlFor="password" className="text-sm font-medium">Password</Label>
              <Input
                id="password"
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className="h-12 rounded-sm border-[#E2E8F0] focus:border-primary focus:ring-primary"
                placeholder="••••••••"
                required
                data-testid="password-input"
              />
            </div>
            
            <div className="space-y-2">
              <Label htmlFor="confirmPassword" className="text-sm font-medium">Confirm Password</Label>
              <Input
                id="confirmPassword"
                type="password"
                value={confirmPassword}
                onChange={(e) => setConfirmPassword(e.target.value)}
                className="h-12 rounded-sm border-[#E2E8F0] focus:border-primary focus:ring-primary"
                placeholder="••••••••"
                required
                data-testid="confirm-password-input"
              />
            </div>
            
            <Button
              type="submit"
              className="w-full h-12 bg-primary hover:bg-primary/90 rounded-sm font-medium"
              disabled={isLoading}
              data-testid="register-submit-btn"
            >
              {isLoading ? (
                <div className="w-5 h-5 border-2 border-white border-t-transparent rounded-full animate-spin" />
              ) : (
                <>
                  Create Account
                  <ArrowRight className="w-4 h-4 ml-2" />
                </>
              )}
            </Button>
          </form>
          
          <p className="mt-8 text-center text-sm text-muted-foreground">
            Already have an account?{' '}
            <Link to="/login" className="text-primary hover:underline font-medium" data-testid="login-link">
              Sign in
            </Link>
          </p>
        </div>
      </div>
    </div>
  );
};
