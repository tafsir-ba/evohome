import { useState, useEffect } from 'react';
import { useSearchParams } from 'react-router-dom';
import { AgentLayout } from '../../components/AgentLayout';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '../../components/ui/card';
import { Button } from '../../components/ui/button';
import { Badge } from '../../components/ui/badge';
import { Progress } from '../../components/ui/progress';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '../../components/ui/dialog';
import { toast } from 'sonner';
import { useSettings } from '../../context/SettingsContext';
import { 
  CreditCard, 
  Check, 
  Building2,
  Zap,
  Crown,
  Loader2,
  ExternalLink,
  Mail,
  AlertTriangle,
  Settings,
  Calendar,
  AlertCircle,
  RefreshCw
} from 'lucide-react';
import { cn } from '../../lib/utils';

const API = process.env.REACT_APP_BACKEND_URL + '/api';

export const AgentBilling = () => {
  const { t } = useSettings();
  const [searchParams] = useSearchParams();
  const [loading, setLoading] = useState(true);
  const [processingPlan, setProcessingPlan] = useState(null);
  const [subscriptionStatus, setSubscriptionStatus] = useState(null);
  const [plans, setPlans] = useState([]);
  const [openingPortal, setOpeningPortal] = useState(false);
  const [syncingSubscription, setSyncingSubscription] = useState(false);

  useEffect(() => {
    fetchBillingData();
    
    // Check for successful checkout
    const sessionId = searchParams.get('session_id');
    const success = searchParams.get('success');
    const canceled = searchParams.get('canceled');
    
    if (success === 'true' && sessionId) {
      verifyCheckoutSession(sessionId);
    } else if (canceled === 'true') {
      toast.info('Checkout was canceled');
    }
  }, [searchParams]);

  const fetchBillingData = async () => {
    try {
      const [statusRes, plansRes] = await Promise.all([
        fetch(`${API}/billing/status`, { credentials: 'include' }),
        fetch(`${API}/billing/plans`, { credentials: 'include' })
      ]);
      
      if (statusRes.ok && plansRes.ok) {
        setSubscriptionStatus(await statusRes.json());
        setPlans(await plansRes.json());
      }
    } catch (error) {
      console.error('Failed to fetch billing data:', error);
      toast.error('Failed to load billing information');
    } finally {
      setLoading(false);
    }
  };

  const verifyCheckoutSession = async (sessionId) => {
    try {
      const res = await fetch(`${API}/billing/verify-session`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
        body: JSON.stringify({ session_id: sessionId })
      });
      
      if (res.ok) {
        const result = await res.json();
        if (result.success) {
          toast.success('Subscription activated successfully!');
          fetchBillingData();
        }
      }
    } catch (error) {
      console.error('Failed to verify session:', error);
    }
    
    // Clear URL params
    window.history.replaceState({}, '', '/agent/billing');
  };

  const handleSyncSubscription = async () => {
    setSyncingSubscription(true);
    try {
      const res = await fetch(`${API}/billing/sync`, {
        method: 'POST',
        credentials: 'include'
      });
      
      if (res.ok) {
        const result = await res.json();
        if (result.synced) {
          toast.success(`Subscription synced: ${result.plan_id?.toUpperCase() || 'Free'} plan`);
          fetchBillingData();
        } else {
          toast.info(result.message);
        }
      } else {
        const error = await res.json();
        throw new Error(error.detail || 'Failed to sync subscription');
      }
    } catch (error) {
      toast.error(error.message);
    } finally {
      setSyncingSubscription(false);
    }
  };

  const handleSubscribe = async (planId) => {
    setProcessingPlan(planId);
    
    try {
      const res = await fetch(`${API}/billing/create-checkout-session`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
        body: JSON.stringify({ 
          plan_id: planId,
          origin_url: window.location.origin
        })
      });
      
      if (res.ok) {
        const data = await res.json();
        if (data.checkout_url) {
          window.location.href = data.checkout_url;
        }
      } else {
        const error = await res.json();
        throw new Error(error.detail || 'Failed to start checkout');
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
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
        body: JSON.stringify({ 
          return_url: window.location.href
        })
      });
      
      if (res.ok) {
        const data = await res.json();
        if (data.portal_url) {
          window.location.href = data.portal_url;
        }
      } else {
        const error = await res.json();
        throw new Error(error.detail || 'Failed to open billing portal');
      }
    } catch (error) {
      toast.error(error.message);
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

  const getStatusColor = (status) => {
    switch (status) {
      case 'active': return 'bg-green-500/10 text-green-600';
      case 'past_due': return 'bg-red-500/10 text-red-600';
      case 'canceled':
      case 'canceling': return 'bg-amber-500/10 text-amber-600';
      default: return 'bg-muted text-muted-foreground';
    }
  };

  if (loading) {
    return (
      <AgentLayout>
        <div className="animate-pulse space-y-6">
          <div className="h-8 w-48 bg-muted rounded" />
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
            {[1, 2, 3, 4].map(i => (
              <div key={i} className="h-80 bg-muted rounded-lg" />
            ))}
          </div>
        </div>
      </AgentLayout>
    );
  }

  const usagePercent = subscriptionStatus?.usage_percent || 0;
  const isNearLimit = subscriptionStatus?.near_limit;
  const isAtLimit = !subscriptionStatus?.can_create_property && subscriptionStatus?.property_limit;

  return (
    <AgentLayout>
      <div className="space-y-8" data-testid="agent-billing">
        {/* Header */}
        <div>
          <h1 className="text-2xl sm:text-3xl font-outfit font-semibold text-foreground tracking-tight">
            {t('billing.title')}
          </h1>
          <p className="text-muted-foreground mt-1">{t('billing.subtitle')}</p>
        </div>

        {/* 80% Usage Warning */}
        {isNearLimit && !isAtLimit && (
          <Card className="border-amber-500/50 bg-amber-500/5 rounded-lg">
            <CardContent className="py-4 px-5 flex items-center gap-4">
              <div className="w-10 h-10 bg-amber-500/10 rounded-lg flex items-center justify-center flex-shrink-0">
                <AlertTriangle className="w-5 h-5 text-amber-500" />
              </div>
              <div className="flex-1">
                <p className="font-medium text-foreground">Approaching property limit</p>
                <p className="text-sm text-muted-foreground">
                  You're using {subscriptionStatus?.property_usage} of {subscriptionStatus?.property_limit} properties ({Math.round(usagePercent)}%). 
                  Consider upgrading to avoid interruption.
                </p>
              </div>
              <Button 
                variant="outline" 
                className="border-amber-500/50 text-amber-600 hover:bg-amber-500/10"
                onClick={() => document.getElementById('plans-section')?.scrollIntoView({ behavior: 'smooth' })}
              >
                <Zap className="w-4 h-4 mr-2" />
                View Plans
              </Button>
            </CardContent>
          </Card>
        )}

        {/* Payment Failed Warning */}
        {subscriptionStatus?.subscription_status === 'past_due' && (
          <Card className="border-red-500/50 bg-red-500/5 rounded-lg">
            <CardContent className="py-4 px-5 flex items-center gap-4">
              <div className="w-10 h-10 bg-red-500/10 rounded-lg flex items-center justify-center flex-shrink-0">
                <AlertCircle className="w-5 h-5 text-red-500" />
              </div>
              <div className="flex-1">
                <p className="font-medium text-red-600">Payment failed</p>
                <p className="text-sm text-muted-foreground">
                  Your last payment was unsuccessful. Please update your payment method to maintain access.
                </p>
              </div>
              {subscriptionStatus?.stripe_customer_id && (
                <Button 
                  variant="destructive"
                  onClick={handleManageSubscription}
                  disabled={openingPortal}
                >
                  {openingPortal ? (
                    <Loader2 className="w-4 h-4 animate-spin mr-2" />
                  ) : (
                    <CreditCard className="w-4 h-4 mr-2" />
                  )}
                  Update Payment
                </Button>
              )}
            </CardContent>
          </Card>
        )}

        {/* Current Plan Summary */}
        <Card className="border-border rounded-lg bg-gradient-to-br from-primary/5 to-transparent">
          <CardContent className="p-6">
            <div className="flex flex-col lg:flex-row lg:items-start justify-between gap-6">
              <div className="space-y-4">
                <div className="flex items-center gap-3">
                  <div className={cn("w-12 h-12 rounded-xl flex items-center justify-center", getPlanColor(subscriptionStatus?.plan_id))}>
                    {getPlanIcon(subscriptionStatus?.plan_id)}
                  </div>
                  <div>
                    <p className="text-sm text-muted-foreground">Current Plan</p>
                    <h2 className="text-2xl font-outfit font-semibold">{subscriptionStatus?.plan_name}</h2>
                  </div>
                </div>
                
                <div className="flex items-center gap-2">
                  <Badge className={cn("rounded-full", getStatusColor(subscriptionStatus?.subscription_status))}>
                    {subscriptionStatus?.subscription_status === 'past_due' ? 'Payment Failed' : 
                     subscriptionStatus?.subscription_status === 'canceling' ? 'Canceling' :
                     subscriptionStatus?.subscription_status === 'canceled' ? 'Canceled' : 'Active'}
                  </Badge>
                  
                  {subscriptionStatus?.current_period_end && (
                    <span className="text-xs text-muted-foreground flex items-center gap-1">
                      <Calendar className="w-3 h-3" />
                      Renews {new Date(subscriptionStatus.current_period_end * 1000).toLocaleDateString()}
                    </span>
                  )}
                </div>
              </div>
              
              <div className="flex-1 max-w-md">
                <div className="flex items-center justify-between mb-2">
                  <span className="text-sm text-muted-foreground">Property Usage</span>
                  <span className="text-sm font-medium">
                    {subscriptionStatus?.property_usage} / {subscriptionStatus?.property_limit ?? '∞'}
                  </span>
                </div>
                <Progress 
                  value={usagePercent} 
                  className={cn("h-2", isAtLimit && "bg-red-200", isNearLimit && !isAtLimit && "bg-amber-200")} 
                />
                <p className="text-xs text-muted-foreground mt-2">
                  {isAtLimit 
                    ? 'Property limit reached - upgrade to create more'
                    : subscriptionStatus?.property_limit 
                      ? `${subscriptionStatus.property_limit - subscriptionStatus.property_usage} properties remaining`
                      : 'Unlimited properties'
                  }
                </p>
              </div>
              
              {/* Manage Subscription Button */}
              <div className="flex flex-col sm:flex-row gap-2">
                {subscriptionStatus?.stripe_customer_id && (
                  <Button 
                    variant="outline" 
                    className="rounded-lg"
                    onClick={handleManageSubscription}
                    disabled={openingPortal}
                    data-testid="manage-subscription-btn"
                  >
                    {openingPortal ? (
                      <Loader2 className="w-4 h-4 animate-spin mr-2" />
                    ) : (
                      <Settings className="w-4 h-4 mr-2" />
                    )}
                    Manage Subscription
                  </Button>
                )}
                
                {/* Sync Subscription Button - for fixing sync issues */}
                <Button 
                  variant="ghost" 
                  size="sm"
                  className="rounded-lg text-muted-foreground hover:text-foreground"
                  onClick={handleSyncSubscription}
                  disabled={syncingSubscription}
                  title="Sync subscription status from Stripe"
                  data-testid="sync-subscription-btn"
                >
                  <RefreshCw className={cn("w-4 h-4", syncingSubscription && "animate-spin")} />
                  <span className="ml-1 hidden sm:inline">Sync</span>
                </Button>
              </div>
            </div>
          </CardContent>
        </Card>

        {/* Plans Grid */}
        <div id="plans-section">
          <h2 className="text-xl font-outfit font-semibold mb-4">Available Plans</h2>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
            {plans.map(plan => {
              const isCurrent = subscriptionStatus?.plan_id === plan.plan_id;
              const isUpgrade = !isCurrent && 
                (plan.plan_id !== 'free') && 
                (subscriptionStatus?.plan_id === 'free' || 
                 (subscriptionStatus?.plan_id === 'starter' && plan.plan_id === 'pro'));
              
              return (
                <Card 
                  key={plan.plan_id} 
                  className={cn(
                    "border-border rounded-lg transition-all relative overflow-hidden",
                    isCurrent && "border-primary ring-1 ring-primary/20",
                    isUpgrade && "hover:border-primary/50 hover:shadow-md"
                  )}
                  data-testid={`plan-card-${plan.plan_id}`}
                >
                  {isCurrent && (
                    <div className="absolute top-0 right-0 bg-primary text-primary-foreground text-[10px] font-semibold px-2 py-0.5 rounded-bl-lg">
                      CURRENT
                    </div>
                  )}
                  
                  <CardHeader className="pb-4">
                    <div className={cn("w-10 h-10 rounded-lg flex items-center justify-center mb-2", getPlanColor(plan.plan_id))}>
                      {getPlanIcon(plan.plan_id)}
                    </div>
                    <CardTitle className="text-lg font-outfit">{plan.name}</CardTitle>
                    <CardDescription>
                      {plan.is_enterprise ? (
                        <span className="text-lg font-semibold text-foreground">Custom pricing</span>
                      ) : plan.price === 0 ? (
                        <span className="text-lg font-semibold text-foreground">Free</span>
                      ) : (
                        <>
                          <span className="text-2xl font-semibold text-foreground">CHF {plan.price}</span>
                          <span className="text-sm text-muted-foreground">/month</span>
                        </>
                      )}
                    </CardDescription>
                  </CardHeader>
                  
                  <CardContent className="space-y-4">
                    <ul className="space-y-2">
                      {plan.features.map((feature, idx) => (
                        <li key={idx} className="flex items-start gap-2 text-sm">
                          <Check className="w-4 h-4 text-primary flex-shrink-0 mt-0.5" />
                          <span className="text-muted-foreground">{feature}</span>
                        </li>
                      ))}
                    </ul>
                    
                    {plan.is_enterprise ? (
                      <Button 
                        variant="outline" 
                        className="w-full rounded-lg"
                        onClick={() => window.location.href = 'mailto:hello@evo-home.ch?subject=Enterprise Plan Inquiry'}
                        data-testid="contact-sales-btn"
                      >
                        <Mail className="w-4 h-4 mr-2" />
                        Contact Sales
                      </Button>
                    ) : isCurrent ? (
                      <Button variant="outline" className="w-full rounded-lg" disabled>
                        Current Plan
                      </Button>
                    ) : plan.plan_id === 'free' ? (
                      <Button variant="outline" className="w-full rounded-lg" disabled>
                        {subscriptionStatus?.plan_id !== 'free' ? 'Downgrade at period end' : 'Free Plan'}
                      </Button>
                    ) : (
                      <Button 
                        className="w-full rounded-lg"
                        onClick={() => handleSubscribe(plan.plan_id)}
                        disabled={processingPlan === plan.plan_id}
                        data-testid={`subscribe-${plan.plan_id}-btn`}
                      >
                        {processingPlan === plan.plan_id ? (
                          <>
                            <Loader2 className="w-4 h-4 animate-spin mr-2" />
                            Processing...
                          </>
                        ) : (
                          <>
                            <ExternalLink className="w-4 h-4 mr-2" />
                            {isUpgrade ? 'Upgrade' : 'Subscribe'}
                          </>
                        )}
                      </Button>
                    )}
                  </CardContent>
                </Card>
              );
            })}
          </div>
        </div>

        {/* Subscription Details (for paid subscribers) */}
        {subscriptionStatus?.stripe_subscription_id && (
          <Card className="border-border rounded-lg">
            <CardHeader>
              <CardTitle className="text-lg font-outfit flex items-center gap-2">
                <CreditCard className="w-5 h-5 text-muted-foreground" />
                Subscription Details
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-3 text-sm">
              <div className="flex justify-between items-center py-2 border-b border-border">
                <span className="text-muted-foreground">Plan</span>
                <span className="font-medium">{subscriptionStatus.plan_name}</span>
              </div>
              <div className="flex justify-between items-center py-2 border-b border-border">
                <span className="text-muted-foreground">Status</span>
                <Badge className={cn("rounded-full", getStatusColor(subscriptionStatus.subscription_status))}>
                  {subscriptionStatus.subscription_status}
                </Badge>
              </div>
              <div className="flex justify-between items-center py-2 border-b border-border">
                <span className="text-muted-foreground">Property Usage</span>
                <span className="font-medium">
                  {subscriptionStatus.property_usage} / {subscriptionStatus.property_limit ?? '∞'}
                </span>
              </div>
              {subscriptionStatus.current_period_end && (
                <div className="flex justify-between items-center py-2 border-b border-border">
                  <span className="text-muted-foreground">Next Billing Date</span>
                  <span className="font-medium">
                    {new Date(subscriptionStatus.current_period_end * 1000).toLocaleDateString()}
                  </span>
                </div>
              )}
              <div className="pt-2">
                <Button 
                  variant="outline" 
                  size="sm"
                  className="w-full rounded-lg"
                  onClick={handleManageSubscription}
                  disabled={openingPortal}
                >
                  {openingPortal ? (
                    <Loader2 className="w-4 h-4 animate-spin mr-2" />
                  ) : (
                    <ExternalLink className="w-4 h-4 mr-2" />
                  )}
                  Manage in Stripe
                </Button>
              </div>
            </CardContent>
          </Card>
        )}
      </div>
    </AgentLayout>
  );
};
