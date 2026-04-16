import { useState, useEffect } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import { toast } from 'sonner';
import { Loader2, Users, CheckCircle, XCircle } from 'lucide-react';
import { useAuth } from '../context/AuthContext';

const API = process.env.REACT_APP_BACKEND_URL + '/api';

export const AcceptInvitePage = () => {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const token = searchParams.get('token');
  const { setAuthUser, checkAuth } = useAuth();
  
  const [status, setStatus] = useState('loading'); // loading, needs_registration, accepted, error
  const [inviteInfo, setInviteInfo] = useState(null);
  const [error, setError] = useState(null);
  
  // Registration form state
  const [name, setName] = useState('');
  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [registering, setRegistering] = useState(false);

  useEffect(() => {
    if (!token) {
      setStatus('error');
      setError('Invalid invitation link. Please check your email for the correct link.');
      return;
    }
    
    acceptInvitation();
  }, [token]);

  const acceptInvitation = async () => {
    try {
      const res = await fetch(`${API}/team/accept?token=${token}`, {
        method: 'POST',
        credentials: 'include'
      });
      
      if (res.ok) {
        const data = await res.json();
        
        if (data.status === 'needs_registration') {
          setInviteInfo(data);
          setStatus('needs_registration');
        } else if (data.status === 'accepted') {
          if (data.token) {
            localStorage.setItem('auth_token', data.token);
            setAuthUser({ user_id: data.user_id, role: 'agent', token: data.token });
          }
          await checkAuth();
          setStatus('accepted');
          toast.success('Bienvenue sur Evohome');
          setTimeout(() => navigate('/agent/home'), 2000);
        }
      } else {
        const errorData = await res.json();
        setStatus('error');
        setError(errorData.detail || 'Failed to accept invitation');
      }
    } catch (err) {
      setStatus('error');
      setError('Network error. Please try again.');
    }
  };

  const handleRegister = async (e) => {
    e.preventDefault();
    
    if (password !== confirmPassword) {
      toast.error('Les mots de passe ne correspondent pas');
      return;
    }
    
    if (password.length < 8) {
      toast.error('Le mot de passe doit contenir au moins 8 caracteres');
      return;
    }
    
    setRegistering(true);
    try {
      const formData = new FormData();
      formData.append('email', inviteInfo.email);
      formData.append('name', name);
      formData.append('password', password);
      formData.append('token', token);
      
      const res = await fetch(`${API}/team/register-invited`, {
        method: 'POST',
        credentials: 'include',
        body: formData
      });
      
      if (res.ok) {
        const data = await res.json();
        if (data.token) {
          localStorage.setItem('auth_token', data.token);
          setAuthUser({ user_id: data.user_id, role: 'agent', token: data.token });
        }
        await checkAuth();
        setStatus('accepted');
        toast.success('Compte cree, bienvenue sur Evohome');
        setTimeout(() => navigate('/agent/home'), 2000);
      } else {
        const errorData = await res.json();
        throw new Error(errorData.detail || "L'inscription a echoue");
      }
    } catch (err) {
      toast.error(err.message);
    } finally {
      setRegistering(false);
    }
  };

  if (status === 'loading') {
    return (
      <div className="min-h-screen flex items-center justify-center bg-background">
        <Card className="w-full max-w-md mx-4">
          <CardContent className="flex flex-col items-center justify-center py-12">
            <Loader2 className="w-8 h-8 animate-spin text-primary mb-4" />
            <p className="text-muted-foreground">Traitement de votre invitation...</p>
          </CardContent>
        </Card>
      </div>
    );
  }

  if (status === 'error') {
    return (
      <div className="min-h-screen flex items-center justify-center bg-background">
        <Card className="w-full max-w-md mx-4">
          <CardContent className="flex flex-col items-center justify-center py-12">
            <div className="w-16 h-16 rounded-full bg-destructive/10 flex items-center justify-center mb-4">
              <XCircle className="w-8 h-8 text-destructive" />
            </div>
            <h2 className="text-xl font-semibold mb-2">Erreur d'invitation</h2>
            <p className="text-muted-foreground text-center mb-6">{error}</p>
            <Button onClick={() => navigate('/login')}>
              Aller a la connexion
            </Button>
          </CardContent>
        </Card>
      </div>
    );
  }

  if (status === 'accepted') {
    return (
      <div className="min-h-screen flex items-center justify-center bg-background">
        <Card className="w-full max-w-md mx-4">
          <CardContent className="flex flex-col items-center justify-center py-12">
            <div className="w-16 h-16 rounded-full bg-green-100 dark:bg-green-900/30 flex items-center justify-center mb-4">
              <CheckCircle className="w-8 h-8 text-green-600 dark:text-green-400" />
            </div>
            <h2 className="text-xl font-semibold mb-2">Bienvenue dans l'equipe</h2>
            <p className="text-muted-foreground text-center mb-2">
              Votre invitation a ete acceptee.
            </p>
            <p className="text-sm text-muted-foreground">
              Redirection vers le tableau de bord...
            </p>
          </CardContent>
        </Card>
      </div>
    );
  }

  // Registration form for new users
  return (
    <div className="min-h-screen flex items-center justify-center bg-background p-4">
      <Card className="w-full max-w-md">
        <CardHeader className="text-center">
          <div className="w-16 h-16 rounded-full bg-primary/10 flex items-center justify-center mx-auto mb-4">
            <Users className="w-8 h-8 text-primary" />
          </div>
          <CardTitle className="text-2xl">Rejoindre l'equipe de {inviteInfo?.invited_by_name}</CardTitle>
          <CardDescription>
            Vous etes invite en tant que <strong>{inviteInfo?.role}</strong>.
            Creez votre compte pour commencer.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleRegister} className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="email">Email</Label>
              <Input
                id="email"
                type="email"
                value={inviteInfo?.email || ''}
                disabled
                className="bg-muted"
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="name">Votre nom</Label>
              <Input
                id="name"
                type="text"
                placeholder="Jean Dupont"
                value={name}
                onChange={(e) => setName(e.target.value)}
                required
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="password">Password</Label>
              <Input
                id="password"
                type="password"
                placeholder="••••••••"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
                minLength={8}
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="confirmPassword">Confirmer le mot de passe</Label>
              <Input
                id="confirmPassword"
                type="password"
                placeholder="••••••••"
                value={confirmPassword}
                onChange={(e) => setConfirmPassword(e.target.value)}
                required
                minLength={8}
              />
            </div>
            <Button type="submit" className="w-full" disabled={registering}>
              {registering ? (
                <>
                  <Loader2 className="w-4 h-4 animate-spin mr-2" />
                  Creation du compte...
                </>
              ) : (
                'Creer le compte et rejoindre'
              )}
            </Button>
          </form>
          
          <div className="mt-6 text-center">
            <p className="text-sm text-muted-foreground">
              Vous avez deja un compte ?{' '}
              <Button variant="link" className="p-0 h-auto" onClick={() => navigate('/login')}>
                Se connecter
              </Button>
            </p>
          </div>
        </CardContent>
      </Card>
    </div>
  );
};

export default AcceptInvitePage;
