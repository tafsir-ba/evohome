import { createContext, useContext, useState, useEffect, useCallback } from 'react';
import { useAuth } from './AuthContext';

const API = process.env.REACT_APP_BACKEND_URL + '/api';

// Translation dictionaries
const translations = {
  en: {
    // Common
    common: {
      save: 'Save',
      cancel: 'Cancel',
      delete: 'Delete',
      edit: 'Edit',
      create: 'Create',
      loading: 'Loading...',
      search: 'Search',
      noResults: 'No results found',
      viewAll: 'View All',
      back: 'Back',
      next: 'Next',
      submit: 'Submit',
      confirm: 'Confirm',
      close: 'Close',
      yes: 'Yes',
      no: 'No',
      or: 'or',
      and: 'and',
      required: 'Required',
      optional: 'Optional',
    },
    // Navigation
    nav: {
      dashboard: 'Dashboard',
      projects: 'Projects',
      clients: 'Clients',
      workflow: 'Workflow',
      timeline: 'Timeline',
      feed: 'Feed',
      team: 'Team',
      quotes: 'Quotes',
      invoices: 'Invoices',
      analytics: 'Analytics',
      settings: 'Settings',
      billing: 'Billing',
      logout: 'Logout',
    },
    // Dashboard
    dashboard: {
      title: 'Dashboard',
      welcome: 'Welcome back',
      totalProjects: 'Total Projects',
      activeClients: 'Active Clients',
      pendingQuotes: 'Pending Quotes',
      pendingInvoices: 'Pending Invoices',
      recentActivity: 'Recent Activity',
      quickActions: 'Quick Actions',
      newQuote: 'New Quote',
      newInvoice: 'New Invoice',
      viewProjects: 'View Projects',
    },
    // Projects
    projects: {
      title: 'Projects',
      subtitle: 'Manage your real estate developments',
      newProject: 'New Project',
      projectName: 'Project Name',
      address: 'Address',
      description: 'Description',
      totalUnits: 'Total Units',
      constructionStart: 'Construction Start',
      estimatedCompletion: 'Estimated Completion',
      clients: 'clients',
      units: 'units',
      propertyUsage: 'Property usage',
      upgradeRequired: 'Upgrade required',
      limitReached: 'Property limit reached',
      upgradePlan: 'Upgrade Plan',
    },
    // Clients
    clients: {
      title: 'Clients',
      subtitle: 'Manage your client relationships',
      newClient: 'New Client',
      clientName: 'Client Name',
      email: 'Email',
      phone: 'Phone',
      unit: 'Unit',
      project: 'Project',
      view: 'View',
      viewAsClient: 'View as Client',
      total: 'total clients',
      inProject: 'clients in project',
    },
    // Documents
    documents: {
      quotes: 'Quotes',
      invoices: 'Invoices',
      quotesAndInvoices: 'Quotes & Invoices',
      newQuote: 'New Quote',
      newInvoice: 'New Invoice',
      uploadPdf: 'Upload PDF',
      dragDrop: 'Drag and drop or click to upload',
      extracting: 'Extracting document data...',
      amount: 'Amount',
      status: 'Status',
      dueDate: 'Due Date',
      supplier: 'Supplier',
      description: 'Description',
      lineItems: 'Line Items',
      total: 'Total',
      send: 'Send',
      approve: 'Approve',
      reject: 'Reject',
      requestChange: 'Request Change',
      markPaid: 'Mark as Paid',
      download: 'Download',
      viewPdf: 'View PDF',
    },
    // Status
    status: {
      draft: 'Draft',
      sent: 'Sent',
      approved: 'Approved',
      rejected: 'Rejected',
      changeRequested: 'Change Requested',
      paid: 'Paid',
      pending: 'Pending',
      active: 'Active',
      inactive: 'Inactive',
      completed: 'Completed',
      inProgress: 'In Progress',
      notStarted: 'Not Started',
    },
    // Settings
    settings: {
      title: 'Settings',
      subtitle: 'Manage your account preferences and billing',
      account: 'Account',
      preferences: 'Preferences',
      billing: 'Billing',
      companyBranding: 'Company Branding',
      companyName: 'Company Name',
      companyLogo: 'Company Logo',
      uploadLogo: 'Click to upload logo',
      logoRequiresPro: 'Upgrade to Pro to upload logo',
      changeLogo: 'Change',
      removeLogo: 'Remove',
      proFeature: 'Pro feature',
      regionalSettings: 'Regional Settings',
      language: 'Language',
      currency: 'Default Currency',
      saveChanges: 'Save Changes',
      currentPlan: 'Current Plan',
      projectUsage: 'Project Usage',
      projectsRemaining: 'projects remaining',
      unlimited: 'Unlimited',
      manageSubscription: 'Manage Subscription',
      availablePlans: 'Available Plans',
      upgrade: 'Upgrade',
      contactSales: 'Contact Sales',
      current: 'Current',
    },
    // Billing
    billing: {
      title: 'Billing & Subscription',
      subtitle: 'Manage your subscription plan and property limits',
      freePlan: 'Free',
      starterPlan: 'Starter',
      proPlan: 'Pro',
      enterprisePlan: 'Enterprise',
      perMonth: '/month',
      customPricing: 'Custom pricing',
      properties: 'properties',
      upTo: 'Up to',
      manageUpTo: 'Manage up to',
      scaleUpTo: 'Scale to',
      fullClientTracking: 'Full client tracking & communication',
      prioritySupport: 'Priority support',
      advancedWorkflows: 'Advanced workflow templates',
      teamCollaboration: 'Team collaboration',
      customWorkflows: 'Custom workflows',
      dedicatedManager: 'Dedicated account manager',
      apiAccess: 'API access & integrations',
      approachingLimit: 'Approaching property limit',
      paymentFailed: 'Payment failed',
      updatePayment: 'Update Payment',
    },
    // Feed
    feed: {
      title: 'Activity Feed',
      subtitle: 'Communication with your clients',
      newPost: 'New Post',
      message: 'Message',
      image: 'Image',
      file: 'File',
      statusUpdate: 'Status Update',
      selectProject: 'Select Project',
      selectRecipients: 'Select Recipients',
      allClients: 'All Clients',
      typeMessage: 'Type your message...',
      post: 'Post',
      reply: 'Reply',
      replies: 'replies',
      showReplies: 'Show replies',
      hideReplies: 'Hide replies',
      writeReply: 'Write a reply...',
    },
    // Team
    team: {
      title: 'Team Directory',
      subtitle: 'Manage project team contacts',
      addMember: 'Add Team Member',
      name: 'Name',
      role: 'Role',
      email: 'Email',
      phone: 'Phone',
      website: 'Website',
      notes: 'Notes',
      selectProject: 'Select a project to manage its team',
    },
    // Workflow/Timeline
    workflow: {
      title: 'Construction Timeline',
      subtitle: 'Track project progress and milestones',
      selectProject: 'Select a project',
      noTimeline: 'No timeline configured',
      createTimeline: 'Create Timeline',
      applyTemplate: 'Apply Template',
      stage: 'Stage',
      startDate: 'Start Date',
      endDate: 'End Date',
      status: 'Status',
      documents: 'Documents',
      notes: 'Notes',
      progress: 'Progress',
      complete: 'Complete',
    },
    // Buyer
    buyer: {
      welcome: 'Welcome',
      yourProperty: 'Your Property',
      updates: 'Updates',
      constructionProgress: 'Construction Progress',
      viewDetails: 'View Details',
      whatsIncluded: "What's included",
      actionRequired: 'Action Required',
      awaitingResponse: 'Awaiting Response',
      payWithQr: 'Pay with QR',
      ivePaid: "I've Paid",
      askQuestion: 'Ask',
    },
    // Landing page
    landing: {
      heroTitle: 'Real Estate Upgrade Management,',
      heroHighlight: 'Simplified',
      heroSubtitle: 'The all-in-one platform for property developers and agents to manage client upgrades, track construction progress, and streamline communication.',
      getStarted: 'Get Started',
      tryDemo: 'Try Demo',
      requestDemo: 'Request Demo',
      login: 'Login',
      contactSales: 'Contact Sales',
      builtFor: 'Built for Swiss Property Professionals',
      builtForSubtitle: 'Whether you manage 2 properties or 200, Evohome scales with your business.',
      forAgents: 'For Agents',
      forBuyers: 'For Buyers',
      features: 'Everything You Need',
      featuresSubtitle: 'Powerful features designed for real estate workflows.',
      pricing: 'Simple, Transparent Pricing',
      pricingSubtitle: 'Start free, upgrade when you need more.',
      mostPopular: 'Most Popular',
      startFree: 'Start Free',
      contactUs: 'Contact Us',
      cta: 'Ready to Streamline Your Property Management?',
      ctaSubtitle: 'Join agents across Switzerland who trust Evohome for their upgrade management.',
      startFreeTrial: 'Start Free Trial',
      madeIn: 'Made in Switzerland',
    },
    // Auth
    auth: {
      welcome: 'Welcome',
      selectRole: 'Select your role to sign in',
      imBuyer: "I'm a Buyer",
      imAgent: "I'm an Agent",
      continueWithGoogle: 'Continue with Google',
      continueWithEmail: 'Continue with Email',
      tryDemo: 'Try Demo',
      createAccount: 'Create Account',
      signIn: 'Sign In',
      fullName: 'Full Name',
      email: 'Email',
      password: 'Password',
      alreadyHaveAccount: 'Already have an account?',
      dontHaveAccount: "Don't have an account?",
      createOne: 'Create one',
      forgotPassword: 'Forgot password?',
    },
  },
  fr: {
    common: {
      save: 'Enregistrer',
      cancel: 'Annuler',
      delete: 'Supprimer',
      edit: 'Modifier',
      create: 'Créer',
      loading: 'Chargement...',
      search: 'Rechercher',
      noResults: 'Aucun résultat trouvé',
      viewAll: 'Voir tout',
      back: 'Retour',
      next: 'Suivant',
      submit: 'Soumettre',
      confirm: 'Confirmer',
      close: 'Fermer',
      yes: 'Oui',
      no: 'Non',
      or: 'ou',
      and: 'et',
      required: 'Requis',
      optional: 'Optionnel',
    },
    nav: {
      dashboard: 'Tableau de bord',
      projects: 'Projets',
      clients: 'Clients',
      workflow: 'Workflow',
      timeline: 'Chronologie',
      feed: 'Fil',
      team: 'Équipe',
      quotes: 'Devis',
      invoices: 'Factures',
      analytics: 'Analytique',
      settings: 'Paramètres',
      billing: 'Facturation',
      logout: 'Déconnexion',
    },
    dashboard: {
      title: 'Tableau de bord',
      welcome: 'Bon retour',
      totalProjects: 'Projets totaux',
      activeClients: 'Clients actifs',
      pendingQuotes: 'Devis en attente',
      pendingInvoices: 'Factures en attente',
      recentActivity: 'Activité récente',
      quickActions: 'Actions rapides',
      newQuote: 'Nouveau devis',
      newInvoice: 'Nouvelle facture',
      viewProjects: 'Voir les projets',
    },
    projects: {
      title: 'Projets',
      subtitle: 'Gérez vos développements immobiliers',
      newProject: 'Nouveau projet',
      projectName: 'Nom du projet',
      address: 'Adresse',
      description: 'Description',
      totalUnits: 'Unités totales',
      constructionStart: 'Début de construction',
      estimatedCompletion: 'Achèvement estimé',
      clients: 'clients',
      units: 'unités',
      propertyUsage: 'Utilisation des projets',
      upgradeRequired: 'Mise à niveau requise',
      limitReached: 'Limite de projets atteinte',
      upgradePlan: 'Mettre à niveau',
    },
    clients: {
      title: 'Clients',
      subtitle: 'Gérez vos relations clients',
      newClient: 'Nouveau client',
      clientName: 'Nom du client',
      email: 'Email',
      phone: 'Téléphone',
      unit: 'Unité',
      project: 'Projet',
      view: 'Voir',
      viewAsClient: 'Voir comme client',
      total: 'clients au total',
      inProject: 'clients dans le projet',
    },
    documents: {
      quotes: 'Devis',
      invoices: 'Factures',
      quotesAndInvoices: 'Devis & Factures',
      newQuote: 'Nouveau devis',
      newInvoice: 'Nouvelle facture',
      uploadPdf: 'Télécharger PDF',
      dragDrop: 'Glisser-déposer ou cliquer pour télécharger',
      extracting: 'Extraction des données...',
      amount: 'Montant',
      status: 'Statut',
      dueDate: "Date d'échéance",
      supplier: 'Fournisseur',
      description: 'Description',
      lineItems: 'Lignes',
      total: 'Total',
      send: 'Envoyer',
      approve: 'Approuver',
      reject: 'Rejeter',
      requestChange: 'Demander modification',
      markPaid: 'Marquer comme payé',
      download: 'Télécharger',
      viewPdf: 'Voir PDF',
    },
    status: {
      draft: 'Brouillon',
      sent: 'Envoyé',
      approved: 'Approuvé',
      rejected: 'Rejeté',
      changeRequested: 'Modification demandée',
      paid: 'Payé',
      pending: 'En attente',
      active: 'Actif',
      inactive: 'Inactif',
      completed: 'Terminé',
      inProgress: 'En cours',
      notStarted: 'Non commencé',
    },
    settings: {
      title: 'Paramètres',
      subtitle: 'Gérez vos préférences de compte et facturation',
      account: 'Compte',
      preferences: 'Préférences',
      billing: 'Facturation',
      companyBranding: "Image de marque de l'entreprise",
      companyName: "Nom de l'entreprise",
      companyLogo: "Logo de l'entreprise",
      uploadLogo: 'Cliquez pour télécharger le logo',
      logoRequiresPro: 'Passez à Pro pour télécharger le logo',
      changeLogo: 'Changer',
      removeLogo: 'Supprimer',
      proFeature: 'Fonction Pro',
      regionalSettings: 'Paramètres régionaux',
      language: 'Langue',
      currency: 'Devise par défaut',
      saveChanges: 'Enregistrer les modifications',
      currentPlan: 'Plan actuel',
      projectUsage: 'Utilisation des projets',
      projectsRemaining: 'projets restants',
      unlimited: 'Illimité',
      manageSubscription: "Gérer l'abonnement",
      availablePlans: 'Plans disponibles',
      upgrade: 'Mettre à niveau',
      contactSales: 'Contacter les ventes',
      current: 'Actuel',
    },
    billing: {
      title: 'Facturation & Abonnement',
      subtitle: 'Gérez votre plan et vos limites de projets',
      freePlan: 'Gratuit',
      starterPlan: 'Starter',
      proPlan: 'Pro',
      enterprisePlan: 'Entreprise',
      perMonth: '/mois',
      customPricing: 'Prix personnalisé',
      properties: 'projets',
      upTo: "Jusqu'à",
      manageUpTo: "Gérez jusqu'à",
      scaleUpTo: "Montez jusqu'à",
      fullClientTracking: 'Suivi client complet & communication',
      prioritySupport: 'Support prioritaire',
      advancedWorkflows: 'Modèles de workflow avancés',
      teamCollaboration: "Collaboration d'équipe",
      customWorkflows: 'Workflows personnalisés',
      dedicatedManager: 'Gestionnaire de compte dédié',
      apiAccess: 'Accès API & intégrations',
      approachingLimit: 'Limite de projets approchée',
      paymentFailed: 'Paiement échoué',
      updatePayment: 'Mettre à jour le paiement',
    },
    feed: {
      title: "Fil d'activité",
      subtitle: 'Communication avec vos clients',
      newPost: 'Nouvelle publication',
      message: 'Message',
      image: 'Image',
      file: 'Fichier',
      statusUpdate: 'Mise à jour de statut',
      selectProject: 'Sélectionner un projet',
      selectRecipients: 'Sélectionner les destinataires',
      allClients: 'Tous les clients',
      typeMessage: 'Tapez votre message...',
      post: 'Publier',
      reply: 'Répondre',
      replies: 'réponses',
      showReplies: 'Afficher les réponses',
      hideReplies: 'Masquer les réponses',
      writeReply: 'Écrire une réponse...',
    },
    team: {
      title: "Annuaire de l'équipe",
      subtitle: "Gérer les contacts de l'équipe projet",
      addMember: "Ajouter un membre de l'équipe",
      name: 'Nom',
      role: 'Rôle',
      email: 'Email',
      phone: 'Téléphone',
      website: 'Site web',
      notes: 'Notes',
      selectProject: 'Sélectionnez un projet',
    },
    workflow: {
      title: 'Calendrier de construction',
      subtitle: "Suivre l'avancement du projet et les jalons",
      selectProject: 'Sélectionner un projet',
      noTimeline: 'Aucun calendrier configuré',
      createTimeline: 'Créer un calendrier',
      applyTemplate: 'Appliquer un modèle',
      stage: 'Étape',
      startDate: 'Date de début',
      endDate: 'Date de fin',
      status: 'Statut',
      documents: 'Documents',
      notes: 'Notes',
      progress: 'Progression',
      complete: 'Terminé',
    },
    buyer: {
      welcome: 'Bienvenue',
      yourProperty: 'Votre propriété',
      updates: 'Mises à jour',
      constructionProgress: 'Avancement de la construction',
      viewDetails: 'Voir les détails',
      whatsIncluded: 'Ce qui est inclus',
      actionRequired: 'Action requise',
      awaitingResponse: 'En attente de réponse',
      payWithQr: 'Payer avec QR',
      ivePaid: "J'ai payé",
      askQuestion: 'Demander',
    },
    landing: {
      heroTitle: "Gestion des mises à niveau immobilières,",
      heroHighlight: 'simplifiée',
      heroSubtitle: "La plateforme tout-en-un pour les promoteurs et agents immobiliers pour gérer les mises à niveau clients, suivre l'avancement de la construction et rationaliser la communication.",
      getStarted: 'Commencer',
      tryDemo: 'Essayer la démo',
      requestDemo: 'Demander une démo',
      login: 'Connexion',
      contactSales: 'Contacter les ventes',
      builtFor: 'Conçu pour les professionnels immobiliers suisses',
      builtForSubtitle: 'Que vous gériez 2 ou 200 propriétés, Evohome évolue avec votre entreprise.',
      forAgents: 'Pour les agents',
      forBuyers: 'Pour les acheteurs',
      features: 'Tout ce dont vous avez besoin',
      featuresSubtitle: 'Des fonctionnalités puissantes conçues pour les workflows immobiliers.',
      pricing: 'Tarification simple et transparente',
      pricingSubtitle: 'Commencez gratuitement, passez à la version supérieure quand vous en avez besoin.',
      mostPopular: 'Plus populaire',
      startFree: 'Commencer gratuitement',
      contactUs: 'Contactez-nous',
      cta: 'Prêt à rationaliser votre gestion immobilière?',
      ctaSubtitle: 'Rejoignez les agents à travers la Suisse qui font confiance à Evohome pour leur gestion des mises à niveau.',
      startFreeTrial: "Commencer l'essai gratuit",
      madeIn: 'Fabriqué en Suisse',
    },
    auth: {
      welcome: 'Bienvenue',
      selectRole: 'Sélectionnez votre rôle pour vous connecter',
      imBuyer: 'Je suis acheteur',
      imAgent: 'Je suis agent',
      continueWithGoogle: 'Continuer avec Google',
      continueWithEmail: 'Continuer avec Email',
      tryDemo: 'Essayer la démo',
      createAccount: 'Créer un compte',
      signIn: 'Se connecter',
      fullName: 'Nom complet',
      email: 'Email',
      password: 'Mot de passe',
      alreadyHaveAccount: 'Vous avez déjà un compte?',
      dontHaveAccount: "Vous n'avez pas de compte?",
      createOne: 'Créer un',
      forgotPassword: 'Mot de passe oublié?',
    },
  },
};

// Currency configurations
const currencyConfig = {
  CHF: { symbol: 'CHF', locale: 'de-CH', position: 'prefix' },
  EUR: { symbol: '€', locale: 'de-DE', position: 'suffix' },
  USD: { symbol: '$', locale: 'en-US', position: 'prefix' },
};

const SettingsContext = createContext(null);

export const useSettings = () => {
  const context = useContext(SettingsContext);
  if (!context) {
    throw new Error('useSettings must be used within SettingsProvider');
  }
  return context;
};

export const SettingsProvider = ({ children }) => {
  const { user } = useAuth();
  const [settings, setSettings] = useState({
    language: 'fr',
    currency: 'CHF',
    company_name: '',
    company_logo_url: null,
  });
  const [loading, setLoading] = useState(true);
  const [agentBranding, setAgentBranding] = useState(null); // For buyer view

  // Fetch settings on mount and when user changes
  useEffect(() => {
    if (user?.role === 'agent') {
      fetchSettings();
    } else if (user?.role === 'buyer') {
      fetchAgentBranding();
    } else {
      setLoading(false);
    }
  }, [user]);

  const fetchSettings = async () => {
    try {
      const res = await fetch(`${API}/settings`, { credentials: 'include' });
      if (res.ok) {
        const data = await res.json();
        const savedLang = localStorage.getItem('evohome_language');
        const preferredLang = (savedLang === 'en' || savedLang === 'fr')
          ? savedLang
          : (data.language || 'fr');
        setSettings(prev => ({ ...prev, ...data, language: preferredLang }));
      }
    } catch (error) {
      console.error('Failed to fetch settings:', error);
    } finally {
      setLoading(false);
    }
  };

  const fetchAgentBranding = async () => {
    try {
      // For buyers, fetch the agent's branding
      const res = await fetch(`${API}/branding`, { credentials: 'include' });
      if (res.ok) {
        const data = await res.json();
        setAgentBranding(data);
        // Use agent's language preference for buyer interface
        const savedLang = localStorage.getItem('evohome_language');
        const preferredLang = (savedLang === 'en' || savedLang === 'fr')
          ? savedLang
          : (data.language || 'fr');
        setSettings(prev => ({ ...prev, language: preferredLang, currency: data.currency || 'CHF' }));
      }
    } catch (error) {
      console.error('Failed to fetch agent branding:', error);
    } finally {
      setLoading(false);
    }
  };

  const updateSettings = async (newSettings) => {
    try {
      const res = await fetch(`${API}/settings`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
        body: JSON.stringify(newSettings),
      });
      
      if (res.ok) {
        setSettings(prev => ({ ...prev, ...newSettings }));
        return true;
      }
      return false;
    } catch (error) {
      console.error('Failed to update settings:', error);
      return false;
    }
  };

  // Translation function
  const t = useCallback((key) => {
    const keys = key.split('.');
    let value = translations[settings.language] || translations.en;
    
    for (const k of keys) {
      if (value && typeof value === 'object' && k in value) {
        value = value[k];
      } else {
        // Fallback to English
        value = translations.en;
        for (const fallbackK of keys) {
          if (value && typeof value === 'object' && fallbackK in value) {
            value = value[fallbackK];
          } else {
            return key; // Return key if translation not found
          }
        }
        break;
      }
    }
    
    return typeof value === 'string' ? value : key;
  }, [settings.language]);

  // Currency formatting function
  const formatCurrency = useCallback((amount, currencyOverride = null) => {
    const curr = currencyOverride || settings.currency;
    const config = currencyConfig[curr] || currencyConfig.CHF;
    
    const formatted = new Intl.NumberFormat(config.locale, {
      minimumFractionDigits: 2,
      maximumFractionDigits: 2,
    }).format(amount);
    
    return config.position === 'prefix' 
      ? `${config.symbol} ${formatted}`
      : `${formatted} ${config.symbol}`;
  }, [settings.currency]);

  // Get the logo to display (agent's own or agent branding for buyers)
  const getLogo = useCallback(() => {
    const baseUrl = process.env.REACT_APP_BACKEND_URL;
    if (agentBranding?.company_logo_url) {
      const url = agentBranding.company_logo_url;
      return url.startsWith('http') ? url : `${baseUrl}${url}`;
    }
    if (settings.company_logo_url) {
      const url = settings.company_logo_url;
      return url.startsWith('http') ? url : `${baseUrl}${url}`;
    }
    return null;
  }, [settings.company_logo_url, agentBranding]);

  const getCompanyName = useCallback(() => {
    return agentBranding?.company_name || settings.company_name || 'Evohome';
  }, [settings.company_name, agentBranding]);

  // Quick language change function for the toggle
  const changeLanguage = useCallback(async (lang) => {
    if (lang !== 'en' && lang !== 'fr') return; // Only allow en/fr
    setSettings(prev => ({ ...prev, language: lang }));
    // Persist to localStorage for immediate effect
    localStorage.setItem('evohome_language', lang);
    // Also update on server if user is logged in
    try {
      await fetch(`${API}/settings`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
        body: JSON.stringify({ language: lang }),
      });
    } catch (error) {
      // Silently fail - local storage will keep the preference
    }
  }, []);

  // Load language from localStorage on mount
  useEffect(() => {
    const savedLang = localStorage.getItem('evohome_language');
    if (savedLang && (savedLang === 'en' || savedLang === 'fr')) {
      setSettings(prev => ({ ...prev, language: savedLang }));
    } else {
      localStorage.setItem('evohome_language', 'fr');
      setSettings(prev => ({ ...prev, language: 'fr' }));
    }
  }, []);

  const value = {
    settings,
    loading,
    updateSettings,
    t,
    formatCurrency,
    getLogo,
    getCompanyName,
    agentBranding,
    language: settings.language,
    currency: settings.currency,
    changeLanguage,
  };

  return (
    <SettingsContext.Provider value={value}>
      {children}
    </SettingsContext.Provider>
  );
};
