import { useState, useEffect, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { AgentLayout } from '../../components/AgentLayout';
import { useSettings } from '../../context/SettingsContext';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '../../components/ui/card';
import { Button } from '../../components/ui/button';
import { Input } from '../../components/ui/input';
import { Label } from '../../components/ui/label';
import { Badge } from '../../components/ui/badge';
import { Progress } from '../../components/ui/progress';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '../../components/ui/select';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '../../components/ui/tabs';
import { toast } from 'sonner';
import { 
  User,
  Globe,
  CreditCard,
  Building2,
  Loader2,
  Check,
  Upload,
  Trash2,
  ExternalLink,
  Zap,
  Crown,
  Calendar,
  Mail,
  Users,
  UserPlus,
  Clock,
  X,
  Shield,
  Phone
} from 'lucide-react';
import { cn } from '../../lib/utils';

const API = process.env.REACT_APP_BACKEND_URL + '/api';
const BASE_URL = process.env.REACT_APP_BACKEND_URL;

const getAuthHeaders = () => {
  const token = localStorage.getItem('auth_token');
  return token ? { 'Authorization': `Bearer ${token}` } : {};
};

const CURRENCIES = [
  { code: 'CHF', name: 'Swiss Franc (CHF)', symbol: 'CHF' },
  { code: 'EUR', name: 'Euro (EUR)', symbol: '€' },
  { code: 'USD', name: 'US Dollar (USD)', symbol: '$' }
];

export const AgentSettings = () => {
  const navigate = useNavigate();
  const fileInputRef = useRef(null);
  const { settings: globalSettings, updateSettings: updateGlobalSettings, t } = useSettings();
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [uploadingLogo, setUploadingLogo] = useState(false);
  const [settings, setSettings] = useState({
    language: 'en',
    currency: 'CHF',
    company_name: '',
    company_logo_url: null,
    billing: {
      iban: '',
      company_name: '',
      address: '',
      postal_code: '',
      city: ''
    },
    profile: {
      display_name: '',
      contact_email: '',
      contact_phone: ''
    }
  });
  const [subscriptionStatus, setSubscriptionStatus] = useState(null);
  const [plans, setPlans] = useState([]);
  const [processingPlan, setProcessingPlan] = useState(null);
  const [openingPortal, setOpeningPortal] = useState(false);
  
  // Team state
  const [teamMembers, setTeamMembers] = useState([]);
  const [invitations, setInvitations] = useState([]);
  const [loadingTeam, setLoadingTeam] = useState(false);
  const [inviteDialogOpen, setInviteDialogOpen] = useState(false);
  const [inviteForm, setInviteForm] = useState({ email: '', role: 'member', message: '' });
  const [sendingInvite, setSendingInvite] = useState(false);

  useEffect(() => {
    fetchData();
  }, []);

  // Sync local settings with global when loaded
  useEffect(() => {
    if (globalSettings) {
      setSettings(prev => ({
        ...prev,
        language: globalSettings.language || prev.language,
        currency: globalSettings.currency || prev.currency,
        company_name: globalSettings.company_name || prev.company_name,
        company_logo_url: globalSettings.company_logo_url || prev.company_logo_url
      }));
    }
  }, [globalSettings]);

  const fetchData = async () => {
    try {
      const [settingsRes, statusRes, plansRes] = await Promise.all([
        fetch(`${API}/settings`, { credentials: 'include', headers: getAuthHeaders() }),
        fetch(`${API}/billing/status`, { credentials: 'include', headers: getAuthHeaders() }),
        fetch(`${API}/billing/plans`, { credentials: 'include', headers: getAuthHeaders() })
      ]);
      
      if (settingsRes.ok) {
        const data = await settingsRes.json();
        setSettings(prev => ({ ...prev, ...data }));
      }
      if (statusRes.ok) setSubscriptionStatus(await statusRes.json());
      if (plansRes.ok) setPlans(await plansRes.json());
    } catch (error) {
      console.error('Failed to fetch settings:', error);
    } finally {
      setLoading(false);
    }
  };

  const fetchTeamData = async () => {
    setLoadingTeam(true);
    try {
      const [membersRes, invitesRes] = await Promise.all([
        fetch(`${API}/team/members`, { credentials: 'include', headers: getAuthHeaders() }),
        fetch(`${API}/team/invitations`, { credentials: 'include', headers: getAuthHeaders() })
      ]);
      
      if (membersRes.ok) setTeamMembers(await membersRes.json());
      if (invitesRes.ok) setInvitations(await invitesRes.json());
    } catch (error) {
      console.error('Failed to fetch team data:', error);
    } finally {
      setLoadingTeam(false);
    }
  };

  const handleSendInvite = async () => {
    if (!inviteForm.email) {
      toast.error('Please enter an email address');
      return;
    }
    
    setSendingInvite(true);
    try {
      const res = await fetch(`${API}/team/invitations`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', ...getAuthHeaders() },
        credentials: 'include',
        body: JSON.stringify(inviteForm)
      });
      
      if (res.ok) {
        toast.success('Invitation sent successfully');
        setInviteDialogOpen(false);
        setInviteForm({ email: '', role: 'member', message: '' });
        fetchTeamData();
      } else {
        const error = await res.json();
        throw new Error(error.detail || 'Failed to send invitation');
      }
    } catch (error) {
      toast.error(error.message);
    } finally {
      setSendingInvite(false);
    }
  };

  const handleCancelInvitation = async (invitationId) => {
    if (!confirm('Cancel this invitation?')) return;
    
    try {
      const res = await fetch(`${API}/team/invitations/${invitationId}`, {
        method: 'DELETE',
        credentials: 'include'
      });
      
      if (res.ok) {
        toast.success('Invitation cancelled');
        fetchTeamData();
      } else {
        throw new Error('Failed to cancel invitation');
      }
    } catch (error) {
      toast.error(error.message);
    }
  };

  const handleRemoveMember = async (memberId) => {
    if (!confirm('Remove this team member? They will lose access to your workspace.')) return;
    
    try {
      const res = await fetch(`${API}/team/members/${memberId}`, {
        method: 'DELETE',
        credentials: 'include'
      });
      
      if (res.ok) {
        toast.success('Team member removed');
        fetchTeamData();
      } else {
        const error = await res.json();
        throw new Error(error.detail || 'Failed to remove member');
      }
    } catch (error) {
      toast.error(error.message);
    }
  };

  const handleSaveSettings = async () => {
    setSaving(true);
    try {
      const res = await fetch(`${API}/settings`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json', ...getAuthHeaders() },
        credentials: 'include',
        body: JSON.stringify({
          language: settings.language,
          currency: settings.currency,
          company_name: settings.company_name,
          billing: settings.billing,
          profile: settings.profile
        })
      });
      
      if (res.ok) {
        // Update global settings context
        await updateGlobalSettings({
          language: settings.language,
          currency: settings.currency,
          company_name: settings.company_name
        });
        toast.success(t('settings.saveChanges') + ' ✓');
      } else {
        throw new Error('Failed to save settings');
      }
    } catch (error) {
      toast.error(error.message);
    } finally {
      setSaving(false);
    }
  };

  const handleLogoUpload = async (e) => {
    const file = e.target.files?.[0];
    if (!file) return;
    
    // Check if user has Pro plan
    if (subscriptionStatus?.plan_id === 'free' || subscriptionStatus?.plan_id === 'starter') {
      toast.error('Logo upload requires Pro plan or higher');
      return;
    }
    
    // Validate file type
    if (!file.type.startsWith('image/')) {
      toast.error('Please upload an image file');
      return;
    }
    
    // Validate file size (max 2MB)
    if (file.size > 2 * 1024 * 1024) {
      toast.error('Image must be less than 2MB');
      return;
    }
    
    setUploadingLogo(true);
    const formData = new FormData();
    formData.append('file', file);
    
    try {
      const token = localStorage.getItem('auth_token');
      const res = await fetch(`${API}/settings/logo`, {
        method: 'POST',
        credentials: 'include',
        headers: token ? { 'Authorization': `Bearer ${token}` } : {},
        body: formData
      });
      
      if (res.ok) {
        const data = await res.json();
        setSettings(prev => ({ ...prev, company_logo_url: data.url }));
        toast.success('Logo uploaded successfully');
      } else {
        const error = await res.json();
        throw new Error(error.detail || 'Failed to upload logo');
      }
    } catch (error) {
      toast.error(error.message);
    } finally {
      setUploadingLogo(false);
      if (fileInputRef.current) fileInputRef.current.value = '';
    }
  };

  const handleDeleteLogo = async () => {
    try {
      const token = localStorage.getItem('auth_token');
      const res = await fetch(`${API}/settings/logo`, {
        method: 'DELETE',
        credentials: 'include',
        headers: token ? { 'Authorization': `Bearer ${token}` } : {},
      });
      
      if (res.ok) {
        setSettings(prev => ({ ...prev, company_logo_url: null }));
        toast.success('Logo removed');
      }
    } catch (error) {
      toast.error('Failed to remove logo');
    }
  };

  const handleSubscribe = async (planId) => {
    setProcessingPlan(planId);
    try {
      const res = await fetch(`${API}/billing/create-checkout-session`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', ...getAuthHeaders() },
        credentials: 'include',
        body: JSON.stringify({ plan_id: planId, origin_url: window.location.origin })
      });
      
      if (res.ok) {
        const data = await res.json();
        if (data.checkout_url) window.location.href = data.checkout_url;
      } else {
        throw new Error('Failed to start checkout');
      }
    } catch (error) {
      toast.error(error.message);
    } finally {
      setProcessingPlan(null);
    }
  };

  const handleManageSubscription = async () => {
    setOpeningPortal(true);
    try {
      const res = await fetch(`${API}/billing/portal`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', ...getAuthHeaders() },
        credentials: 'include',
        body: JSON.stringify({ return_url: window.location.href })
      });
      
      if (res.ok) {
        const data = await res.json();
        if (data.portal_url) window.location.href = data.portal_url;
      }
    } catch (error) {
      toast.error('Failed to open billing portal');
    } finally {
      setOpeningPortal(false);
    }
  };

  const getPlanIcon = (planId) => {
    switch (planId) {
      case 'starter': return <Zap className="w-5 h-5" />;
      case 'pro': return <Crown className="w-5 h-5" />;
      case 'enterprise': return <Building2 className="w-5 h-5" />;
      default: return <CreditCard className="w-5 h-5" />;
    }
  };

  const getPlanColor = (planId) => {
    switch (planId) {
      case 'starter': return 'bg-blue-500/10 text-blue-500';
      case 'pro': return 'bg-purple-500/10 text-purple-500';
      case 'enterprise': return 'bg-amber-500/10 text-amber-500';
      default: return 'bg-muted text-muted-foreground';
    }
  };

  if (loading) {
    return (
      <AgentLayout>
        <div className="animate-pulse space-y-6">
          <div className="h-8 w-32 bg-muted rounded" />
          <div className="h-96 bg-muted rounded-lg" />
        </div>
      </AgentLayout>
    );
  }

  const usagePercent = subscriptionStatus?.property_limit 
    ? Math.round((subscriptionStatus.unit_usage / subscriptionStatus.property_limit) * 100) 
    : 0;
  const canUploadLogo = subscriptionStatus?.plan_id === 'pro' || subscriptionStatus?.plan_id === 'enterprise';

  return (
    <AgentLayout>
      <div className="space-y-6" data-testid="agent-settings">
        <div>
          <h1 className="text-3xl font-outfit font-semibold text-foreground tracking-tight">
            Settings
          </h1>
          <p className="text-muted-foreground mt-1">Manage your account preferences and billing</p>
        </div>

        <Tabs defaultValue="account" className="space-y-6" onValueChange={(value) => {
          if (value === 'team') fetchTeamData();
        }}>
          <TabsList className="bg-muted/50 p-1 rounded-lg">
            <TabsTrigger value="account" className="rounded-md data-[state=active]:bg-background">
              <User className="w-4 h-4 mr-2" />
              Account
            </TabsTrigger>
            <TabsTrigger value="preferences" className="rounded-md data-[state=active]:bg-background">
              <Globe className="w-4 h-4 mr-2" />
              Preferences
            </TabsTrigger>
            <TabsTrigger value="team" className="rounded-md data-[state=active]:bg-background">
              <Users className="w-4 h-4 mr-2" />
              Team
            </TabsTrigger>
            <TabsTrigger value="billing" className="rounded-md data-[state=active]:bg-background">
              <CreditCard className="w-4 h-4 mr-2" />
              Billing
            </TabsTrigger>
          </TabsList>

          {/* Account Tab */}
          <TabsContent value="account" className="space-y-6">
            {/* Agent Profile Card */}
            <Card className="border-border rounded-lg">
              <CardHeader>
                <CardTitle className="text-lg font-outfit flex items-center gap-2">
                  <User className="w-5 h-5" />
                  Your Profile
                </CardTitle>
                <CardDescription>Your contact information shown to clients and in emails</CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="grid gap-4 md:grid-cols-2">
                  <div className="space-y-2">
                    <Label htmlFor="display_name">Display Name</Label>
                    <Input
                      id="display_name"
                      data-testid="profile-display-name-input"
                      value={settings.profile?.display_name || ''}
                      onChange={(e) => setSettings(prev => ({
                        ...prev,
                        profile: { ...prev.profile, display_name: e.target.value }
                      }))}
                      placeholder="Your full name"
                    />
                    <p className="text-xs text-muted-foreground">Used in email signatures</p>
                  </div>
                  
                  <div className="space-y-2">
                    <Label htmlFor="contact_email">Contact Email</Label>
                    <Input
                      id="contact_email"
                      data-testid="profile-contact-email-input"
                      type="email"
                      value={settings.profile?.contact_email || ''}
                      onChange={(e) => setSettings(prev => ({
                        ...prev,
                        profile: { ...prev.profile, contact_email: e.target.value }
                      }))}
                      placeholder="contact@yourcompany.com"
                    />
                    <p className="text-xs text-muted-foreground">Public email for client inquiries</p>
                  </div>
                </div>
                
                <div className="space-y-2 max-w-md">
                  <Label htmlFor="contact_phone">Phone Number</Label>
                  <Input
                    id="contact_phone"
                    data-testid="profile-contact-phone-input"
                    type="tel"
                    value={settings.profile?.contact_phone || ''}
                    onChange={(e) => setSettings(prev => ({
                      ...prev,
                      profile: { ...prev.profile, contact_phone: e.target.value }
                    }))}
                    placeholder="+41 XX XXX XX XX"
                  />
                </div>

                <Button onClick={handleSaveSettings} disabled={saving} className="rounded-lg" data-testid="save-profile-btn">
                  {saving ? <Loader2 className="w-4 h-4 animate-spin mr-2" /> : <Check className="w-4 h-4 mr-2" />}
                  Save Profile
                </Button>
              </CardContent>
            </Card>

            {/* Company Branding Card */}
            <Card className="border-border rounded-lg">
              <CardHeader>
                <CardTitle className="text-lg font-outfit flex items-center gap-2">
                  <Building2 className="w-5 h-5" />
                  Company Branding
                </CardTitle>
                <CardDescription>Customize your company presence in the app</CardDescription>
              </CardHeader>
              <CardContent className="space-y-6">
                {/* Company Name */}
                <div className="space-y-2">
                  <Label htmlFor="company_name">Company Name</Label>
                  <Input
                    id="company_name"
                    value={settings.company_name}
                    onChange={(e) => setSettings(prev => ({ ...prev, company_name: e.target.value }))}
                    placeholder="Your Company Name"
                    className="max-w-md"
                  />
                </div>

                {/* Company Logo */}
                <div className="space-y-3">
                  <div className="flex items-center justify-between">
                    <Label>Company Logo</Label>
                    {!canUploadLogo && (
                      <Badge variant="outline" className="text-xs">
                        <Crown className="w-3 h-3 mr-1" />
                        Pro feature
                      </Badge>
                    )}
                  </div>
                  
                  {settings.company_logo_url ? (
                    <div className="flex items-center gap-4">
                      <div className="w-20 h-20 rounded-lg border border-border overflow-hidden bg-muted flex items-center justify-center">
                        <img 
                          src={`${BASE_URL}${settings.company_logo_url}`}
                          alt="Company logo"
                          className="max-w-full max-h-full object-contain"
                          onError={(e) => {
                            e.target.style.display = 'none';
                          }}
                        />
                      </div>
                      <div className="space-y-2">
                        <Button
                          variant="outline"
                          size="sm"
                          onClick={() => fileInputRef.current?.click()}
                          disabled={uploadingLogo || !canUploadLogo}
                        >
                          {uploadingLogo ? <Loader2 className="w-4 h-4 animate-spin mr-2" /> : <Upload className="w-4 h-4 mr-2" />}
                          Change
                        </Button>
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={handleDeleteLogo}
                          className="text-destructive hover:text-destructive"
                        >
                          <Trash2 className="w-4 h-4 mr-2" />
                          Remove
                        </Button>
                      </div>
                    </div>
                  ) : (
                    <div 
                      className={cn(
                        "w-full max-w-md h-32 border-2 border-dashed rounded-lg flex flex-col items-center justify-center gap-2 transition-colors",
                        canUploadLogo ? "border-muted-foreground/25 hover:border-primary/50 cursor-pointer" : "border-muted opacity-50"
                      )}
                      onClick={() => canUploadLogo && fileInputRef.current?.click()}
                    >
                      {uploadingLogo ? (
                        <Loader2 className="w-8 h-8 animate-spin text-muted-foreground" />
                      ) : (
                        <>
                          <Upload className="w-8 h-8 text-muted-foreground" />
                          <p className="text-sm text-muted-foreground">
                            {canUploadLogo ? 'Click to upload logo' : 'Upgrade to Pro to upload logo'}
                          </p>
                          <p className="text-xs text-muted-foreground">PNG, JPG up to 2MB</p>
                        </>
                      )}
                    </div>
                  )}
                  <input
                    ref={fileInputRef}
                    type="file"
                    accept="image/*"
                    onChange={handleLogoUpload}
                    className="hidden"
                  />
                </div>

                <Button onClick={handleSaveSettings} disabled={saving} className="rounded-lg">
                  {saving ? <Loader2 className="w-4 h-4 animate-spin mr-2" /> : <Check className="w-4 h-4 mr-2" />}
                  Save Changes
                </Button>
              </CardContent>
            </Card>
          </TabsContent>

          {/* Preferences Tab */}
          <TabsContent value="preferences" className="space-y-6">
            <Card className="border-border rounded-lg">
              <CardHeader>
                <CardTitle className="text-lg font-outfit">Regional Settings</CardTitle>
                <CardDescription>Set your preferred currency for documents</CardDescription>
              </CardHeader>
              <CardContent className="space-y-6">
                <div className="max-w-xs">
                  <div className="space-y-2">
                    <Label htmlFor="currency">Default Currency</Label>
                    <Select
                      value={settings.currency}
                      onValueChange={(v) => setSettings(prev => ({ ...prev, currency: v }))}
                    >
                      <SelectTrigger id="currency">
                        <SelectValue placeholder="Select currency" />
                      </SelectTrigger>
                      <SelectContent>
                        {CURRENCIES.map(curr => (
                          <SelectItem key={curr.code} value={curr.code}>
                            {curr.name}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                    <p className="text-xs text-muted-foreground">
                      Language can be changed using the toggle in the top navigation bar.
                    </p>
                  </div>
                </div>

                <Button onClick={handleSaveSettings} disabled={saving} className="rounded-lg">
                  {saving ? <Loader2 className="w-4 h-4 animate-spin mr-2" /> : <Check className="w-4 h-4 mr-2" />}
                  Save Changes
                </Button>
              </CardContent>
            </Card>
          </TabsContent>

          {/* Team Tab */}
          <TabsContent value="team" className="space-y-6">
            <Card className="border-border rounded-lg">
              <CardHeader className="flex flex-row items-center justify-between">
                <div>
                  <CardTitle className="text-lg font-outfit">Team Members</CardTitle>
                  <CardDescription>Invite others to collaborate in your workspace</CardDescription>
                </div>
                <Button onClick={() => setInviteDialogOpen(true)} className="gap-2">
                  <UserPlus className="w-4 h-4" />
                  Invite Member
                </Button>
              </CardHeader>
              <CardContent>
                {loadingTeam ? (
                  <div className="flex items-center justify-center py-8">
                    <Loader2 className="w-6 h-6 animate-spin text-muted-foreground" />
                  </div>
                ) : (
                  <div className="space-y-4">
                    {/* Team Members List */}
                    {teamMembers.length === 0 ? (
                      <p className="text-center py-8 text-muted-foreground">
                        You're the only member. Invite others to collaborate!
                      </p>
                    ) : (
                      <div className="space-y-3">
                        {teamMembers.map((member) => (
                          <div key={member.user_id} className="flex items-center justify-between p-4 border rounded-lg">
                            <div className="flex items-center gap-4">
                              <div className="w-10 h-10 rounded-full bg-primary/10 flex items-center justify-center">
                                {member.picture ? (
                                  <img src={member.picture} alt="" className="w-10 h-10 rounded-full" />
                                ) : (
                                  <User className="w-5 h-5 text-primary" />
                                )}
                              </div>
                              <div>
                                <p className="font-medium">{member.name}</p>
                                <p className="text-sm text-muted-foreground">{member.email}</p>
                              </div>
                            </div>
                            <div className="flex items-center gap-3">
                              <span className={cn(
                                "px-2 py-1 text-xs rounded-full",
                                member.team_role === 'owner' 
                                  ? "bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-400"
                                  : member.team_role === 'admin'
                                  ? "bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-400"
                                  : "bg-muted text-muted-foreground"
                              )}>
                                {member.team_role === 'owner' && <Crown className="w-3 h-3 inline mr-1" />}
                                {member.team_role === 'admin' && <Shield className="w-3 h-3 inline mr-1" />}
                                {member.team_role.charAt(0).toUpperCase() + member.team_role.slice(1)}
                              </span>
                              {member.team_role !== 'owner' && (
                                <Button
                                  variant="ghost"
                                  size="sm"
                                  onClick={() => handleRemoveMember(member.user_id)}
                                  className="text-destructive hover:text-destructive"
                                >
                                  <X className="w-4 h-4" />
                                </Button>
                              )}
                            </div>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                )}
              </CardContent>
            </Card>

            {/* Pending Invitations */}
            <Card className="border-border rounded-lg">
              <CardHeader>
                <CardTitle className="text-lg font-outfit">Pending Invitations</CardTitle>
                <CardDescription>Invitations that haven't been accepted yet</CardDescription>
              </CardHeader>
              <CardContent>
                {invitations.filter(inv => inv.status === 'pending').length === 0 ? (
                  <p className="text-center py-6 text-muted-foreground">
                    No pending invitations
                  </p>
                ) : (
                  <div className="space-y-3">
                    {invitations.filter(inv => inv.status === 'pending').map((invitation) => (
                      <div key={invitation.invitation_id} className="flex items-center justify-between p-4 border rounded-lg bg-muted/30">
                        <div className="flex items-center gap-4">
                          <div className="w-10 h-10 rounded-full bg-amber-100 dark:bg-amber-900/30 flex items-center justify-center">
                            <Clock className="w-5 h-5 text-amber-600 dark:text-amber-400" />
                          </div>
                          <div>
                            <p className="font-medium">{invitation.email}</p>
                            <p className="text-sm text-muted-foreground">
                              Invited as {invitation.role} • Expires {new Date(invitation.expires_at).toLocaleDateString()}
                            </p>
                          </div>
                        </div>
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => handleCancelInvitation(invitation.invitation_id)}
                          className="text-destructive hover:text-destructive"
                        >
                          Cancel
                        </Button>
                      </div>
                    ))}
                  </div>
                )}
              </CardContent>
            </Card>

            {/* Invite Dialog */}
            {inviteDialogOpen && (
              <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
                <Card className="w-full max-w-md mx-4">
                  <CardHeader>
                    <CardTitle className="flex items-center gap-2">
                      <UserPlus className="w-5 h-5" />
                      Invite Team Member
                    </CardTitle>
                    <CardDescription>
                      Send an invitation to join your workspace
                    </CardDescription>
                  </CardHeader>
                  <CardContent className="space-y-4">
                    <div className="space-y-2">
                      <Label htmlFor="invite-email">Email Address</Label>
                      <Input
                        id="invite-email"
                        type="email"
                        placeholder="colleague@example.com"
                        value={inviteForm.email}
                        onChange={(e) => setInviteForm(prev => ({ ...prev, email: e.target.value }))}
                      />
                    </div>
                    <div className="space-y-2">
                      <Label htmlFor="invite-role">Role</Label>
                      <Select
                        value={inviteForm.role}
                        onValueChange={(value) => setInviteForm(prev => ({ ...prev, role: value }))}
                      >
                        <SelectTrigger id="invite-role">
                          <SelectValue />
                        </SelectTrigger>
                        <SelectContent>
                          <SelectItem value="member">Member - Can view and edit</SelectItem>
                          <SelectItem value="admin">Admin - Full access</SelectItem>
                        </SelectContent>
                      </Select>
                    </div>
                    <div className="space-y-2">
                      <Label htmlFor="invite-message">Personal Message (optional)</Label>
                      <textarea
                        id="invite-message"
                        className="w-full px-3 py-2 border rounded-md bg-background text-sm min-h-[80px] resize-none"
                        placeholder="Add a personal note to your invitation..."
                        value={inviteForm.message}
                        onChange={(e) => setInviteForm(prev => ({ ...prev, message: e.target.value }))}
                      />
                    </div>
                    <div className="flex gap-3 pt-2">
                      <Button
                        variant="outline"
                        className="flex-1"
                        onClick={() => {
                          setInviteDialogOpen(false);
                          setInviteForm({ email: '', role: 'member', message: '' });
                        }}
                      >
                        Cancel
                      </Button>
                      <Button
                        className="flex-1"
                        onClick={handleSendInvite}
                        disabled={sendingInvite || !inviteForm.email}
                      >
                        {sendingInvite ? (
                          <Loader2 className="w-4 h-4 animate-spin mr-2" />
                        ) : (
                          <Mail className="w-4 h-4 mr-2" />
                        )}
                        Send Invitation
                      </Button>
                    </div>
                  </CardContent>
                </Card>
              </div>
            )}
          </TabsContent>

          {/* Billing Tab - Redirect to dedicated page */}
          <TabsContent value="billing" className="space-y-6">
            {/* Current Plan Summary */}
            <Card className="border-border rounded-lg bg-gradient-to-br from-primary/5 to-transparent">
              <CardContent className="p-6">
                <div className="flex flex-col md:flex-row md:items-center justify-between gap-6">
                  <div className="flex items-center gap-3">
                    <div className={cn("w-12 h-12 rounded-xl flex items-center justify-center", getPlanColor(subscriptionStatus?.plan_id))}>
                      {getPlanIcon(subscriptionStatus?.plan_id)}
                    </div>
                    <div>
                      <p className="text-sm text-muted-foreground">Current Plan</p>
                      <h3 className="text-2xl font-outfit font-semibold">{subscriptionStatus?.plan_name || 'Free'}</h3>
                    </div>
                  </div>
                  <div className="flex-1 max-w-sm">
                    <div className="flex items-center justify-between mb-2">
                      <span className="text-sm text-muted-foreground">Property Usage</span>
                      <span className="text-sm font-medium">
                        {subscriptionStatus?.unit_usage || 0} / {subscriptionStatus?.property_limit ?? '∞'}
                      </span>
                    </div>
                    <Progress value={usagePercent} className="h-2" />
                  </div>
                  <Button
                    onClick={() => navigate('/agent/billing')}
                    className="rounded-lg"
                    data-testid="go-to-billing-btn"
                  >
                    <ExternalLink className="w-4 h-4 mr-2" />
                    Manage Billing
                  </Button>
                </div>
              </CardContent>
            </Card>

            {/* Payment Settings (IBAN for QR codes) */}
            <Card className="border-border rounded-lg">
              <CardHeader>
                <CardTitle className="text-lg font-outfit">Payment Settings</CardTitle>
                <CardDescription>Configure your banking details for Swiss QR invoices</CardDescription>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="grid gap-4 sm:grid-cols-2">
                  <div className="space-y-2">
                    <Label htmlFor="billing_iban">IBAN</Label>
                    <Input
                      id="billing_iban"
                      value={settings.billing?.iban || ''}
                      onChange={(e) => setSettings(prev => ({
                        ...prev,
                        billing: { ...prev.billing, iban: e.target.value }
                      }))}
                      placeholder="CH93 0076 2011 6238 5295 7"
                      className="font-mono"
                    />
                    <p className="text-xs text-muted-foreground">Swiss IBAN for QR payment codes</p>
                  </div>
                  <div className="space-y-2">
                    <Label htmlFor="billing_company">Company Name (for invoices)</Label>
                    <Input
                      id="billing_company"
                      value={settings.billing?.company_name || ''}
                      onChange={(e) => setSettings(prev => ({
                        ...prev,
                        billing: { ...prev.billing, company_name: e.target.value }
                      }))}
                      placeholder="Your Company SA"
                    />
                  </div>
                  <div className="space-y-2">
                    <Label htmlFor="billing_address">Street Address</Label>
                    <Input
                      id="billing_address"
                      value={settings.billing?.address || ''}
                      onChange={(e) => setSettings(prev => ({
                        ...prev,
                        billing: { ...prev.billing, address: e.target.value }
                      }))}
                      placeholder="Rue du Rhône 1"
                    />
                  </div>
                  <div className="grid grid-cols-2 gap-2">
                    <div className="space-y-2">
                      <Label htmlFor="billing_postal_code">Postal Code</Label>
                      <Input
                        id="billing_postal_code"
                        value={settings.billing?.postal_code || ''}
                        onChange={(e) => setSettings(prev => ({
                          ...prev,
                          billing: { ...prev.billing, postal_code: e.target.value }
                        }))}
                        placeholder="1204"
                      />
                    </div>
                    <div className="space-y-2">
                      <Label htmlFor="billing_city">City</Label>
                      <Input
                        id="billing_city"
                        value={settings.billing?.city || ''}
                        onChange={(e) => setSettings(prev => ({
                          ...prev,
                          billing: { ...prev.billing, city: e.target.value }
                        }))}
                        placeholder="Genève"
                      />
                    </div>
                  </div>
                </div>
                <Button onClick={handleSaveSettings} disabled={saving} className="mt-4">
                  {saving ? <Loader2 className="w-4 h-4 animate-spin mr-2" /> : <Check className="w-4 h-4 mr-2" />}
                  Save Payment Settings
                </Button>
              </CardContent>
            </Card>
          </TabsContent>
        </Tabs>
      </div>
    </AgentLayout>
  );
};
