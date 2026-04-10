import { Link } from 'react-router-dom';
import { Button } from '../components/ui/button';
import { Card, CardContent } from '../components/ui/card';
import { ThemeToggle } from '../components/ThemeToggle';
import { 
  Building2, 
  FileText, 
  MessageSquare, 
  Users, 
  CheckCircle2,
  ArrowRight,
  Shield,
  Zap,
  BarChart3,
  Clock,
  Mail,
  Bell,
  FolderOpen,
  XCircle
} from 'lucide-react';

const features = [
  {
    icon: FileText,
    title: 'Smart Quotes & Invoices',
    description: 'AI-powered document extraction. Upload PDFs, get structured data instantly.'
  },
  {
    icon: MessageSquare,
    title: 'Client Communication',
    description: 'Centralized activity feed for seamless communication with buyers.'
  },
  {
    icon: Clock,
    title: 'Timeline Tracking',
    description: 'Visual construction progress tracking that clients love.'
  },
  {
    icon: Users,
    title: 'Team Directory',
    description: 'Keep all project contacts organized and accessible.'
  },
  {
    icon: Shield,
    title: 'Role-Based Access',
    description: 'Agents control, buyers view. Clean separation of concerns.'
  },
  {
    icon: BarChart3,
    title: 'Project Overview',
    description: 'Dashboard insights for all your property developments.'
  }
];

const plans = [
  { name: 'Free', price: '0', properties: '2', highlight: false },
  { name: 'Starter', price: '29', properties: '10', highlight: false },
  { name: 'Pro', price: '79', properties: '50', highlight: true },
  { name: 'Enterprise', price: 'Custom', properties: 'Unlimited', highlight: false }
];

export const LandingPage = () => {
  return (
    <div className="min-h-screen bg-background">
      {/* Navigation */}
      <nav className="fixed top-0 left-0 right-0 z-50 bg-background/80 backdrop-blur-lg border-b border-border">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex items-center justify-between h-16">
            <div className="flex items-center gap-2">
              <img 
                src="/evohome-logo.png" 
                alt="Evohome" 
                className="h-10 w-auto object-contain"
              />
            </div>
            <div className="flex items-center gap-3">
              <ThemeToggle />
              <Link to="/login">
                <Button variant="ghost" size="sm">Login</Button>
              </Link>
              <a href="mailto:hello@evo-home.ch?subject=Evohome Sales Inquiry">
                <Button size="sm" className="rounded-lg">Contact Sales</Button>
              </a>
            </div>
          </div>
        </div>
      </nav>

      {/* Hero Section */}
      <section className="pt-32 pb-20 px-4 sm:px-6 lg:px-8">
        <div className="max-w-7xl mx-auto">
          <div className="text-center max-w-4xl mx-auto">
            <h1 className="text-4xl sm:text-5xl lg:text-6xl font-outfit font-bold tracking-tight text-foreground">
              Real Estate Upgrade Management,{' '}
              <span className="text-primary">Simplified</span>
            </h1>
            <p className="mt-6 text-lg sm:text-xl text-muted-foreground max-w-2xl mx-auto leading-relaxed">
              The all-in-one platform for property developers and agents to manage client upgrades, 
              track construction progress, and streamline communication.
            </p>
            <div className="mt-10 flex flex-col sm:flex-row items-center justify-center gap-4">
              <Link to="/login">
                <Button size="lg" className="rounded-lg px-8 text-base">
                  Get Started
                  <ArrowRight className="w-4 h-4 ml-2" />
                </Button>
              </Link>
              <Link to="/login">
                <Button variant="outline" size="lg" className="rounded-lg px-8 text-base">
                  Try Demo
                </Button>
              </Link>
            </div>
          </div>

          {/* Hero Visual - Buyer Dashboard Mockup */}
          <div className="mt-16 relative">
            <div className="absolute inset-x-0 bottom-0 h-20 bg-gradient-to-t from-background to-transparent z-10 pointer-events-none" />
            <div className="rounded-xl border border-border bg-card shadow-2xl overflow-hidden">
              <div className="bg-muted/50 px-4 py-3 border-b border-border flex items-center gap-2">
                <div className="flex gap-1.5">
                  <div className="w-3 h-3 rounded-full bg-red-500/80" />
                  <div className="w-3 h-3 rounded-full bg-yellow-500/80" />
                  <div className="w-3 h-3 rounded-full bg-green-500/80" />
                </div>
                <span className="text-xs text-muted-foreground ml-2">evohome.ch/buyer/dashboard</span>
              </div>
              {/* Realistic Buyer Dashboard Mockup */}
              <div className="p-4 sm:p-6 bg-background">
                {/* Header */}
                <div className="flex items-center justify-between mb-4">
                  <div className="flex items-center gap-3">
                    <div className="w-10 h-10 rounded-lg bg-primary flex items-center justify-center">
                      <Building2 className="w-5 h-5 text-white" />
                    </div>
                    <div>
                      <p className="text-sm font-semibold text-foreground">Unit A-301</p>
                      <p className="text-xs text-muted-foreground">Dubois Immobilier</p>
                    </div>
                  </div>
                  <div className="text-right hidden sm:block">
                    <p className="text-xs text-muted-foreground">Welcome back,</p>
                    <p className="text-sm font-medium text-foreground">Sophie Müller</p>
                  </div>
                </div>

                {/* Welcome & Status */}
                <div className="mb-4">
                  <p className="text-sm text-muted-foreground">Welcome back, <span className="font-medium text-foreground">Sophie</span></p>
                  <div className="flex items-center gap-2 mt-1">
                    <span className="text-xs text-muted-foreground">Current phase: Foundation</span>
                    <span className="px-2 py-0.5 text-[10px] font-semibold bg-primary text-white rounded-full">2 actions needed</span>
                  </div>
                </div>
                
                {/* Progress Card */}
                <div className="rounded-xl border border-border p-4 mb-4 bg-card">
                  <div className="flex items-center justify-between mb-2">
                    <div className="flex items-center gap-3">
                      <div className="w-9 h-9 rounded-lg bg-primary/10 flex items-center justify-center">
                        <Building2 className="w-4 h-4 text-primary" />
                      </div>
                      <div>
                        <span className="text-xs text-muted-foreground uppercase tracking-wide">Construction Progress</span>
                        <p className="text-base font-semibold text-foreground">Foundation</p>
                      </div>
                    </div>
                    <div className="text-right">
                      <span className="text-lg font-bold text-foreground">40%</span>
                      <p className="text-xs text-muted-foreground">2/5 stages</p>
                    </div>
                  </div>
                  <div className="w-full bg-muted rounded-full h-2 mt-2">
                    <div className="bg-primary rounded-full h-2" style={{width: '40%'}} />
                  </div>
                </div>

                {/* Tabs */}
                <div className="flex gap-1 p-1 bg-muted rounded-lg mb-4">
                  <div className="flex-1 flex items-center justify-center gap-2 px-3 py-2 rounded-md bg-background shadow-sm">
                    <FileText className="w-4 h-4 text-foreground" />
                    <span className="text-sm font-medium text-foreground">Quotes</span>
                    <span className="px-1.5 py-0.5 text-[10px] font-bold rounded-full bg-primary text-white">2</span>
                  </div>
                  <div className="flex-1 flex items-center justify-center gap-2 px-3 py-2 rounded-md text-muted-foreground">
                    <FolderOpen className="w-4 h-4" />
                    <span className="text-sm font-medium">Documents</span>
                  </div>
                  <div className="flex-1 flex items-center justify-center gap-2 px-3 py-2 rounded-md text-muted-foreground">
                    <Bell className="w-4 h-4" />
                    <span className="text-sm font-medium">Updates</span>
                  </div>
                  <div className="flex-1 flex items-center justify-center gap-2 px-3 py-2 rounded-md text-muted-foreground">
                    <Users className="w-4 h-4" />
                    <span className="text-sm font-medium">Team</span>
                  </div>
                </div>

                {/* Quote Card */}
                <div className="rounded-xl border border-border overflow-hidden bg-card">
                  {/* Quote Header with Icon */}
                  <div className="bg-gradient-to-br from-primary/10 via-primary/5 to-transparent py-6 flex flex-col items-center justify-center">
                    <div className="w-12 h-12 rounded-2xl bg-primary/10 flex items-center justify-center mb-2">
                      <FileText className="w-6 h-6 text-primary" />
                    </div>
                    <span className="text-xs text-primary font-medium uppercase tracking-wider">Quote</span>
                  </div>
                  
                  <div className="p-4">
                    <div className="flex items-center gap-2 mb-3">
                      <span className="px-2 py-0.5 text-[10px] font-medium bg-primary/10 text-primary rounded">QUOTE</span>
                      <span className="px-2 py-0.5 text-[10px] font-medium bg-amber-100 text-amber-700 rounded flex items-center gap-1">
                        <Clock className="w-3 h-3" />
                        AWAITING RESPONSE
                      </span>
                      <span className="ml-auto px-2 py-0.5 text-[10px] font-medium bg-red-100 text-red-700 rounded">
                        ACTION REQUIRED
                      </span>
                    </div>
                    <div className="flex items-start justify-between gap-4 mb-2">
                      <div>
                        <h3 className="font-bold text-lg text-foreground">Smart Home Automation System</h3>
                        <p className="text-xs text-muted-foreground">QT-2024-0002 · Smart Living GmbH</p>
                      </div>
                      <p className="text-xl font-bold text-foreground whitespace-nowrap">CHF 22'800.00</p>
                    </div>
                    <p className="text-sm text-muted-foreground mb-3">Complete home automation with KNX controller, smart lighting, climate control, and integrated security.</p>
                    <div className="flex gap-2">
                      <div className="flex-1 h-10 rounded-lg bg-emerald-600 flex items-center justify-center cursor-pointer hover:bg-emerald-700 transition-colors">
                        <CheckCircle2 className="w-4 h-4 text-white mr-1.5" />
                        <span className="text-sm text-white font-medium">Approve</span>
                      </div>
                      <div className="flex-1 h-10 rounded-lg bg-red-500 flex items-center justify-center cursor-pointer hover:bg-red-600 transition-colors">
                        <XCircle className="w-4 h-4 text-white mr-1.5" />
                        <span className="text-sm text-white font-medium">Decline</span>
                      </div>
                      <div className="flex-1 h-10 rounded-lg border border-border flex items-center justify-center cursor-pointer hover:bg-muted transition-colors">
                        <MessageSquare className="w-4 h-4 text-muted-foreground mr-1.5" />
                        <span className="text-sm text-muted-foreground font-medium">Ask Question</span>
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* Who It's For */}
      <section className="py-20 bg-muted/30">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="text-center mb-12">
            <h2 className="text-3xl sm:text-4xl font-outfit font-bold text-foreground">
              Built for Swiss Property Professionals
            </h2>
            <p className="mt-4 text-lg text-muted-foreground max-w-2xl mx-auto">
              Whether you manage 2 properties or 200, Evohome scales with your business.
            </p>
          </div>

          <div className="grid md:grid-cols-2 gap-8 max-w-4xl mx-auto">
            <Card className="border-border rounded-xl bg-card">
              <CardContent className="p-6">
                <div className="w-12 h-12 rounded-lg bg-primary/10 flex items-center justify-center mb-4">
                  <Building2 className="w-6 h-6 text-primary" />
                </div>
                <h3 className="text-xl font-outfit font-semibold mb-2">For Agents</h3>
                <ul className="space-y-2 text-muted-foreground">
                  <li className="flex items-start gap-2">
                    <CheckCircle2 className="w-5 h-5 text-primary flex-shrink-0 mt-0.5" />
                    <span>Manage multiple property developments</span>
                  </li>
                  <li className="flex items-start gap-2">
                    <CheckCircle2 className="w-5 h-5 text-primary flex-shrink-0 mt-0.5" />
                    <span>Create and send quotes & invoices</span>
                  </li>
                  <li className="flex items-start gap-2">
                    <CheckCircle2 className="w-5 h-5 text-primary flex-shrink-0 mt-0.5" />
                    <span>Track construction milestones</span>
                  </li>
                  <li className="flex items-start gap-2">
                    <CheckCircle2 className="w-5 h-5 text-primary flex-shrink-0 mt-0.5" />
                    <span>Communicate with clients in one place</span>
                  </li>
                </ul>
              </CardContent>
            </Card>

            <Card className="border-border rounded-xl bg-card">
              <CardContent className="p-6">
                <div className="w-12 h-12 rounded-lg bg-blue-500/10 flex items-center justify-center mb-4">
                  <Users className="w-6 h-6 text-blue-500" />
                </div>
                <h3 className="text-xl font-outfit font-semibold mb-2">For Buyers</h3>
                <ul className="space-y-2 text-muted-foreground">
                  <li className="flex items-start gap-2">
                    <CheckCircle2 className="w-5 h-5 text-blue-500 flex-shrink-0 mt-0.5" />
                    <span>View upgrade quotes and approve changes</span>
                  </li>
                  <li className="flex items-start gap-2">
                    <CheckCircle2 className="w-5 h-5 text-blue-500 flex-shrink-0 mt-0.5" />
                    <span>Track construction progress in real-time</span>
                  </li>
                  <li className="flex items-start gap-2">
                    <CheckCircle2 className="w-5 h-5 text-blue-500 flex-shrink-0 mt-0.5" />
                    <span>Access team contacts and documents</span>
                  </li>
                  <li className="flex items-start gap-2">
                    <CheckCircle2 className="w-5 h-5 text-blue-500 flex-shrink-0 mt-0.5" />
                    <span>Stay updated with activity feed</span>
                  </li>
                </ul>
              </CardContent>
            </Card>
          </div>
        </div>
      </section>

      {/* Features Grid */}
      <section className="py-20">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="text-center mb-12">
            <h2 className="text-3xl sm:text-4xl font-outfit font-bold text-foreground">
              Everything You Need
            </h2>
            <p className="mt-4 text-lg text-muted-foreground">
              Powerful features designed for real estate workflows.
            </p>
          </div>

          <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-6">
            {features.map((feature, index) => (
              <Card key={index} className="border-border rounded-xl bg-card hover:shadow-lg transition-shadow">
                <CardContent className="p-6">
                  <div className="w-10 h-10 rounded-lg bg-primary/10 flex items-center justify-center mb-4">
                    <feature.icon className="w-5 h-5 text-primary" />
                  </div>
                  <h3 className="text-lg font-outfit font-semibold mb-2">{feature.title}</h3>
                  <p className="text-muted-foreground text-sm">{feature.description}</p>
                </CardContent>
              </Card>
            ))}
          </div>
        </div>
      </section>

      {/* Pricing */}
      <section className="py-20 bg-muted/30">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="text-center mb-12">
            <h2 className="text-3xl sm:text-4xl font-outfit font-bold text-foreground">
              Simple, Transparent Pricing
            </h2>
            <p className="mt-4 text-lg text-muted-foreground">
              Start free, upgrade when you need more.
            </p>
          </div>

          <div className="grid sm:grid-cols-2 lg:grid-cols-4 gap-6 max-w-5xl mx-auto">
            {plans.map((plan, index) => (
              <Card 
                key={index} 
                className={`border-border rounded-xl relative ${plan.highlight ? 'border-primary ring-1 ring-primary/20' : ''}`}
              >
                {plan.highlight && (
                  <div className="absolute -top-3 left-1/2 -translate-x-1/2 bg-primary text-primary-foreground text-xs font-semibold px-3 py-1 rounded-full">
                    Most Popular
                  </div>
                )}
                <CardContent className="p-6 text-center">
                  <h3 className="text-lg font-outfit font-semibold">{plan.name}</h3>
                  <div className="mt-4">
                    {plan.price === 'Custom' ? (
                      <span className="text-2xl font-bold">Custom</span>
                    ) : (
                      <>
                        <span className="text-3xl font-bold">CHF {plan.price}</span>
                        {plan.price !== '0' && <span className="text-muted-foreground">/mo</span>}
                      </>
                    )}
                  </div>
                  <p className="mt-2 text-sm text-muted-foreground">
                    Up to {plan.properties} properties
                  </p>
                  <Link to="/login" className="block mt-6">
                    <Button 
                      variant={plan.highlight ? 'default' : 'outline'} 
                      className="w-full rounded-lg"
                    >
                      {plan.price === '0' ? 'Start Free' : plan.price === 'Custom' ? 'Contact Us' : 'Get Started'}
                    </Button>
                  </Link>
                </CardContent>
              </Card>
            ))}
          </div>
        </div>
      </section>

      {/* CTA */}
      <section className="py-20">
        <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 text-center">
          <h2 className="text-3xl sm:text-4xl font-outfit font-bold text-foreground">
            Ready to Streamline Your Property Management?
          </h2>
          <p className="mt-4 text-lg text-muted-foreground">
            Join agents across Switzerland who trust Evohome for their upgrade management.
          </p>
          <div className="mt-8 flex flex-col sm:flex-row items-center justify-center gap-4">
            <Link to="/login">
              <Button size="lg" className="rounded-lg px-8">
                Start Free Trial
                <ArrowRight className="w-4 h-4 ml-2" />
              </Button>
            </Link>
            <a href="mailto:hello@evo-home.ch?subject=Evohome Demo Request">
              <Button variant="outline" size="lg" className="rounded-lg px-8">
                <Mail className="w-4 h-4 mr-2" />
                Request Demo
              </Button>
            </a>
          </div>
        </div>
      </section>

      {/* Footer */}
      <footer className="border-t border-border py-12">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex flex-col sm:flex-row items-center justify-between gap-4">
            <div className="flex items-center gap-2">
              <img 
                src="/evohome-logo.png" 
                alt="Evohome" 
                className="h-8 w-auto object-contain"
              />
            </div>
            <p className="text-sm text-muted-foreground">
              © {new Date().getFullYear()} Evohome. Made in Switzerland.
            </p>
            <div className="flex items-center gap-4 text-sm text-muted-foreground">
              <a href="mailto:hello@evo-home.ch" className="hover:text-foreground transition-colors">
                Contact
              </a>
              <span>•</span>
              <span>Privacy</span>
              <span>•</span>
              <span>Terms</span>
            </div>
          </div>
        </div>
      </footer>
    </div>
  );
};
