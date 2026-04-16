import { useState, useEffect } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { AgentLayout } from '../../components/AgentLayout';
import { Card, CardContent, CardHeader, CardTitle } from '../../components/ui/card';
import { Button } from '../../components/ui/button';
import { Input } from '../../components/ui/input';
import { Label } from '../../components/ui/label';
import { Textarea } from '../../components/ui/textarea';
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
import { useDataContext } from '../../context/DataContext';
import { 
  Building2, 
  Plus, 
  Edit2, 
  Trash2, 
  FileText,
  MapPin,
  Calendar,
  Users,
  Loader2,
  Home,
  ChevronRight,
  X,
  Zap,
  AlertTriangle
} from 'lucide-react';

const API = process.env.REACT_APP_BACKEND_URL + '/api';

const getAuthHeaders = () => {
  const token = localStorage.getItem('auth_token');
  return token ? { 'Authorization': `Bearer ${token}` } : {};
};

export const AgentProjects = () => {
  const { t } = useSettings();
  const navigate = useNavigate();
  
  // SINGLE SOURCE OF TRUTH: DataContext for projects
  const { projects, refreshProjects, loading: projectsLoading } = useDataContext();
  
  const [loading, setLoading] = useState(false);
  const [showDialog, setShowDialog] = useState(false);
  const [editingProject, setEditingProject] = useState(null);
  const [saving, setSaving] = useState(false);
  const [subscriptionStatus, setSubscriptionStatus] = useState(null);
  const [showLimitModal, setShowLimitModal] = useState(false);
  const [formData, setFormData] = useState({
    name: '',
    address: '',
    description: '',
    total_units: '',
    construction_start: '',
    estimated_completion: ''
  });
  
  // Units management
  const [showUnitsDialog, setShowUnitsDialog] = useState(false);
  const [unitsProject, setUnitsProject] = useState(null);
  const [units, setUnits] = useState([]);
  const [newUnit, setNewUnit] = useState('');
  const [loadingUnits, setLoadingUnits] = useState(false);

  // Project delete impact & confirmation
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);
  const [deleteImpact, setDeleteImpact] = useState(null);
  const [deleteProject, setDeleteProject] = useState(null);
  const [deleteLoading, setDeleteLoading] = useState(false);
  const [deleteError, setDeleteError] = useState('');

  useEffect(() => {
    fetchSubscriptionStatus();
  }, []);

  const fetchSubscriptionStatus = async () => {
    try {
      const res = await fetch(`${API}/billing/status`, { credentials: 'include', headers: getAuthHeaders() });
      if (res.ok) {
        setSubscriptionStatus(await res.json());
      }
    } catch (error) {
      console.error('Failed to fetch subscription status:', error);
    }
  };

  const handleOpenDialog = (project = null) => {
    if (project) {
      setEditingProject(project);
      setFormData({
        name: project.name || '',
        address: project.address || '',
        description: project.description || '',
        total_units: project.total_units?.toString() || '',
        construction_start: project.construction_start || '',
        estimated_completion: project.estimated_completion || ''
      });
    } else {
      setEditingProject(null);
      setFormData({
        name: '',
        address: '',
        description: '',
        total_units: '',
        construction_start: '',
        estimated_completion: ''
      });
    }
    setShowDialog(true);
  };

  const handleSave = async () => {
    if (!formData.name.trim()) {
      toast.error('Project name is required');
      return;
    }

    // Check subscription limit before creating (frontend validation)
    if (!editingProject && subscriptionStatus && !subscriptionStatus.can_create_unit) {
      setShowDialog(false);
      setShowLimitModal(true);
      return;
    }

    setSaving(true);
    try {
      const url = editingProject 
        ? `${API}/projects/${editingProject.project_id}`
        : `${API}/projects`;
      
      const res = await fetch(url, {
        method: editingProject ? 'PUT' : 'POST',
        headers: { 'Content-Type': 'application/json', ...getAuthHeaders() },
        credentials: 'include',
        body: JSON.stringify({
          ...formData,
          total_units: formData.total_units ? parseInt(formData.total_units) : null
        })
      });

      if (res.ok) {
        toast.success(editingProject ? 'Project updated' : 'Project created');
        setShowDialog(false);
        refreshProjects();
        fetchSubscriptionStatus(); // Refresh usage count
      } else {
        const error = await res.json();
        // Check if it's a property limit error
        if (res.status === 403 && error.detail?.includes('Property limit')) {
          setShowDialog(false);
          setShowLimitModal(true);
          fetchSubscriptionStatus(); // Refresh to get latest status
          return;
        }
        throw new Error(error.detail || 'Failed to save project');
      }
    } catch (error) {
      toast.error(error.message);
    } finally {
      setSaving(false);
    }
  };

  const openDeleteDialog = async (e, project) => {
    e.stopPropagation();
    setDeleteProject(project);
    setDeleteImpact(null);
    setDeleteError('');
    setDeleteDialogOpen(true);
    setDeleteLoading(true);

    try {
      const res = await fetch(`${API}/projects/${project.project_id}/delete-impact`, {
        credentials: 'include',
        headers: getAuthHeaders(),
      });
      if (res.ok) {
        setDeleteImpact(await res.json());
      } else {
        const error = await res.json();
        setDeleteError(error.message || error.detail || 'Failed to load delete impact');
      }
    } catch (error) {
      console.error('Failed to load delete impact:', error);
      setDeleteError('Failed to load delete impact');
    } finally {
      setDeleteLoading(false);
    }
  };

  const handleImpactNavigate = (type, projectId) => {
    switch (type) {
      case 'clients':
        navigate(`/agent/clients?project=${projectId}`);
        break;
      case 'units':
        navigate(`/agent/clients?project=${projectId}`);
        break;
      case 'documents':
        navigate('/agent/documents');
        break;
      case 'timeline':
        navigate('/agent/timeline');
        break;
      case 'vault':
        navigate('/agent/vault');
        break;
      case 'decisions':
        navigate('/agent/decisions');
        break;
      default:
        break;
    }
  };

  const handleConfirmDelete = async () => {
    if (!deleteProject) return;
    setDeleteLoading(true);
    setDeleteError('');

    try {
      const res = await fetch(`${API}/projects/${deleteProject.project_id}?force=true`, {
        method: 'DELETE',
        credentials: 'include',
        headers: getAuthHeaders(),
      });

      if (res.ok) {
        toast.success('Project and linked data deleted');
        setDeleteDialogOpen(false);
        setDeleteImpact(null);
        setDeleteProject(null);
        refreshProjects();
      } else {
        const error = await res.json();
        const message = error.message || error.detail || 'Failed to delete project';
        setDeleteError(message);
        toast.error(message);
      }
    } catch (error) {
      console.error('Delete project failed:', error);
      const message = error.message || 'Failed to delete project';
      setDeleteError(message);
      toast.error(message);
    } finally {
      setDeleteLoading(false);
    }
  };

  const handleProjectClick = (project) => {
    // Navigate to clients page filtered by this project
    navigate(`/agent/clients?project=${project.project_id}`);
  };

  const handleOpenUnits = async (e, project) => {
    e.stopPropagation();
    setUnitsProject(project);
    setShowUnitsDialog(true);
    setLoadingUnits(true);
    
    try {
      const res = await fetch(`${API}/projects/${project.project_id}/units`, { credentials: 'include', headers: getAuthHeaders() });
      if (res.ok) {
        setUnits(await res.json());
      }
    } catch (error) {
      console.error('Failed to fetch units:', error);
    } finally {
      setLoadingUnits(false);
    }
  };

  const handleAddUnit = async () => {
    if (!newUnit.trim() || !unitsProject) return;
    
    try {
      const res = await fetch(`${API}/projects/${unitsProject.project_id}/units`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', ...getAuthHeaders() },
        credentials: 'include',
        body: JSON.stringify({ unit_reference: newUnit.trim() })
      });

      if (res.ok) {
        const unit = await res.json();
        setUnits(prev => [...prev, unit]);
        setNewUnit('');
        toast.success('Unit added');
        refreshProjects(); // Update unit_count on project cards
      } else {
        const error = await res.json();
        throw new Error(error.detail || 'Failed to add unit');
      }
    } catch (error) {
      toast.error(error.message);
    }
  };

  const handleDeleteUnit = async (unitId) => {
    try {
      const res = await fetch(`${API}/units/${unitId}`, {
        method: 'DELETE',
        headers: getAuthHeaders(),
        credentials: 'include'
      });

      if (res.ok) {
        setUnits(prev => prev.filter(u => u.unit_id !== unitId));
        toast.success('Unit removed');
        refreshProjects(); // Update unit_count on project cards
      } else {
        const error = await res.json();
        throw new Error(error.detail || 'Failed to remove unit');
      }
    } catch (error) {
      toast.error(error.message);
    }
  };

  if (loading) {
    return (
      <AgentLayout>
        <div className="animate-pulse space-y-6">
          <div className="h-8 w-48 bg-muted rounded" />
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            {[1, 2, 3].map(i => (
              <div key={i} className="h-48 bg-muted rounded-lg" />
            ))}
          </div>
        </div>
      </AgentLayout>
    );
  }

  return (
    <AgentLayout>
      <div className="space-y-8" data-testid="agent-projects">
        {/* Header */}
        <div className="flex flex-col sm:flex-row sm:items-start sm:justify-between gap-4">
          <div>
            <h1 className="text-2xl sm:text-3xl font-outfit font-semibold text-foreground tracking-tight">
              {t('projects.title')}
            </h1>
            <p className="text-muted-foreground mt-1">{t('projects.subtitle')}</p>
          </div>
          {subscriptionStatus && !subscriptionStatus.can_create_unit ? (
            <Link to="/agent/billing">
              <Button className="rounded-lg bg-gradient-to-r from-amber-500 to-orange-500 hover:from-amber-600 hover:to-orange-600" data-testid="upgrade-plan-btn">
                <Zap className="w-4 h-4 mr-2" />
                {t('projects.upgradePlan')}
              </Button>
            </Link>
          ) : (
            <Button 
              className="rounded-lg"
              onClick={() => handleOpenDialog()}
              data-testid="create-project-btn"
            >
              <Plus className="w-4 h-4 mr-2" />
              {t('projects.newProject')}
            </Button>
          )}
        </div>

        {/* 80% Usage Warning (soft warning) */}
        {subscriptionStatus && subscriptionStatus.property_limit && 
         subscriptionStatus.unit_usage >= subscriptionStatus.property_limit * 0.8 && 
         subscriptionStatus.can_create_unit && (
          <Card className="border-amber-500/30 bg-amber-500/5 rounded-lg">
            <CardContent className="py-3 px-5 flex items-center justify-between gap-4">
              <div className="flex items-center gap-3">
                <AlertTriangle className="w-5 h-5 text-amber-500" />
                <p className="text-sm text-muted-foreground">
                  You're approaching your property limit ({subscriptionStatus.unit_usage} / {subscriptionStatus.property_limit} used)
                </p>
              </div>
              <Link to="/agent/billing">
                <Button variant="ghost" size="sm" className="text-amber-600 hover:text-amber-700 hover:bg-amber-500/10">
                  <Zap className="w-3 h-3 mr-1" />
                  Upgrade
                </Button>
              </Link>
            </CardContent>
          </Card>
        )}

        {/* Property Limit Warning Banner (hard limit) */}
        {subscriptionStatus && !subscriptionStatus.can_create_unit && (
          <Card className="border-amber-500/50 bg-amber-500/5 rounded-lg">
            <CardContent className="py-4 px-5 flex items-center justify-between gap-4">
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 bg-amber-500/10 rounded-lg flex items-center justify-center">
                  <AlertTriangle className="w-5 h-5 text-amber-500" />
                </div>
                <div>
                  <p className="font-medium text-foreground">Property limit reached</p>
                  <p className="text-sm text-muted-foreground">
                    Your {subscriptionStatus.plan_name} plan allows {subscriptionStatus.property_limit} properties. 
                    Upgrade to add more.
                  </p>
                </div>
              </div>
              <Link to="/agent/billing">
                <Button variant="outline" className="rounded-lg border-amber-500/50 text-amber-600 hover:bg-amber-500/10" data-testid="upgrade-cta-btn">
                  <Zap className="w-4 h-4 mr-2" />
                  View Plans
                </Button>
              </Link>
            </CardContent>
          </Card>
        )}

        {/* Property Usage Indicator */}
        {subscriptionStatus && subscriptionStatus.property_limit && (
          <div className="flex items-center gap-4 text-sm">
            <span className="text-muted-foreground">Property usage:</span>
            <div className="flex items-center gap-2 flex-1 max-w-xs">
              <Progress 
                value={(subscriptionStatus.unit_usage / subscriptionStatus.property_limit) * 100} 
                className="h-2 flex-1" 
              />
              <span className="font-medium text-foreground">
                {subscriptionStatus.unit_usage} / {subscriptionStatus.property_limit}
              </span>
            </div>
          </div>
        )}

        {/* Projects Grid */}
        {projects.length === 0 ? (
          <Card className="border-border rounded-lg">
            <CardContent className="py-12 text-center">
              <Building2 className="w-12 h-12 text-muted-foreground/30 mx-auto mb-4" />
              <p className="text-muted-foreground">No projects yet</p>
              <p className="text-sm text-muted-foreground mt-1">Create your first project to start managing clients</p>
              <Button 
                className="mt-4 rounded-lg"
                onClick={() => handleOpenDialog()}
              >
                <Plus className="w-4 h-4 mr-2" />
                Create Project
              </Button>
            </CardContent>
          </Card>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            {projects.map(project => (
              <Card 
                key={project.project_id} 
                className="border-border rounded-lg hover:border-primary/30 hover:shadow-md transition-all cursor-pointer group"
                onClick={() => handleProjectClick(project)}
                data-testid={`project-card-${project.project_id}`}
              >
                <CardHeader className="pb-2">
                  <div className="flex items-start justify-between">
                    <div className="w-10 h-10 bg-primary/10 rounded-lg flex items-center justify-center">
                      <Building2 className="w-5 h-5 text-primary" />
                    </div>
                    <div className="flex gap-1" onClick={e => e.stopPropagation()}>
                      <Button
                        variant="ghost"
                        size="icon"
                        className="h-8 w-8"
                        onClick={(e) => { e.stopPropagation(); handleOpenDialog(project); }}
                        data-testid={`edit-project-${project.project_id}`}
                      >
                        <Edit2 className="w-4 h-4" />
                      </Button>
                      <Button
                        variant="ghost"
                        size="icon"
                        className="h-8 w-8 text-muted-foreground hover:text-destructive"
                        onClick={(e) => openDeleteDialog(e, project)}
                        data-testid={`delete-project-${project.project_id}`}
                      >
                        <Trash2 className="w-4 h-4" />
                      </Button>
                    </div>
                  </div>
                  <CardTitle className="text-lg font-outfit mt-3 flex items-center justify-between">
                    <span>{project.name}</span>
                    <ChevronRight className="w-4 h-4 text-muted-foreground opacity-0 group-hover:opacity-100 transition-opacity" />
                  </CardTitle>
                </CardHeader>
                <CardContent className="space-y-3">
                  {project.address && (
                    <div className="flex items-center gap-2 text-sm text-muted-foreground">
                      <MapPin className="w-4 h-4 flex-shrink-0" />
                      <span className="truncate">{project.address}</span>
                    </div>
                  )}
                  {project.estimated_completion && (
                    <div className="flex items-center gap-2 text-sm text-muted-foreground">
                      <Calendar className="w-4 h-4 flex-shrink-0" />
                      <span>Est. completion: {project.estimated_completion}</span>
                    </div>
                  )}
                  {project.description && (
                    <p className="text-sm text-muted-foreground line-clamp-2 pt-2 border-t border-border">
                      {project.description}
                    </p>
                  )}
                  <div className="pt-3 border-t border-border flex items-center justify-between">
                    <div className="flex items-center gap-4">
                      <div className="flex items-center gap-1.5 text-xs text-muted-foreground">
                        <Users className="w-3.5 h-3.5" />
                        <span>{project.client_count || 0} client{(project.client_count || 0) !== 1 ? 's' : ''}</span>
                      </div>
                      <div className="flex items-center gap-1.5 text-xs text-muted-foreground">
                        <Home className="w-3.5 h-3.5" />
                        <span>{project.unit_count || 0} unit{(project.unit_count || 0) !== 1 ? 's' : ''}</span>
                      </div>
                    </div>
                    <Button
                      variant="outline"
                      size="sm"
                      className="h-7 text-xs"
                      onClick={(e) => handleOpenUnits(e, project)}
                      data-testid={`manage-units-${project.project_id}`}
                    >
                      <Home className="w-3 h-3 mr-1" />
                      Units
                    </Button>
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>
        )}
      </div>

      {/* Create/Edit Project Dialog */}
      <Dialog open={showDialog} onOpenChange={setShowDialog}>
        <DialogContent className="max-w-md">
          <DialogHeader>
            <DialogTitle>{editingProject ? 'Edit Project' : 'New Project'}</DialogTitle>
            <DialogDescription>
              {editingProject 
                ? 'Update the project details. Changes will affect linked clients.'
                : 'Create a new real estate development project.'}
            </DialogDescription>
          </DialogHeader>
          
          <div className="space-y-4 py-4">
            <div className="space-y-2">
              <Label htmlFor="name">Project Name *</Label>
              <Input
                id="name"
                value={formData.name}
                onChange={(e) => setFormData(prev => ({ ...prev, name: e.target.value }))}
                placeholder="e.g., Résidence du Lac"
                data-testid="project-name-input"
              />
            </div>
            
            <div className="space-y-2">
              <Label htmlFor="address">Address</Label>
              <Input
                id="address"
                value={formData.address}
                onChange={(e) => setFormData(prev => ({ ...prev, address: e.target.value }))}
                placeholder="e.g., Chemin du Lac 15, 1095 Lutry"
              />
            </div>
            
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label htmlFor="total_units">Total Units</Label>
                <Input
                  id="total_units"
                  type="number"
                  value={formData.total_units}
                  onChange={(e) => setFormData(prev => ({ ...prev, total_units: e.target.value }))}
                  placeholder="e.g., 24"
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="estimated_completion">Est. Completion</Label>
                <Input
                  id="estimated_completion"
                  value={formData.estimated_completion}
                  onChange={(e) => setFormData(prev => ({ ...prev, estimated_completion: e.target.value }))}
                  placeholder="e.g., Q4 2026"
                />
              </div>
            </div>
            
            <div className="space-y-2">
              <Label htmlFor="description">Description</Label>
              <Textarea
                id="description"
                value={formData.description}
                onChange={(e) => setFormData(prev => ({ ...prev, description: e.target.value }))}
                placeholder="Brief description of the project..."
                rows={3}
              />
            </div>
          </div>
          
          <DialogFooter>
            <Button variant="outline" onClick={() => setShowDialog(false)}>
              Cancel
            </Button>
            <Button onClick={handleSave} disabled={saving} data-testid="save-project-btn">
              {saving ? (
                <Loader2 className="w-4 h-4 animate-spin mr-2" />
              ) : null}
              {editingProject ? 'Save Changes' : 'Create Project'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Delete Project Impact & Confirmation Dialog */}
      <Dialog open={deleteDialogOpen} onOpenChange={setDeleteDialogOpen}>
        <DialogContent className="max-w-lg">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2 text-destructive">
              <AlertTriangle className="w-5 h-5" />
              Delete project & linked data
            </DialogTitle>
            <DialogDescription>
              This will permanently delete the project
              {deleteProject ? ` "${deleteProject.name}"` : ''} and all linked records listed below.
              Review each dependency before proceeding.
            </DialogDescription>
          </DialogHeader>

          <div className="py-4 space-y-4">
            {deleteLoading && (
              <div className="flex items-center gap-2 text-sm text-muted-foreground">
                <Loader2 className="w-4 h-4 animate-spin" />
                Loading linked data…
              </div>
            )}

            {deleteError && (
              <div className="text-sm text-red-600 bg-red-50 border border-red-200 rounded-md px-3 py-2">
                {deleteError}
              </div>
            )}

            {deleteImpact && (
              <div className="space-y-3 max-h-64 overflow-y-auto border border-border rounded-lg p-3">
                <div className="text-xs text-muted-foreground mb-1">
                  Click any item to inspect the impacted data before deletion.
                </div>
                <div className="space-y-2">
                  <button
                    type="button"
                    className="w-full flex items-center justify-between px-3 py-2 rounded-md hover:bg-muted text-left text-sm"
                    onClick={() => handleImpactNavigate('clients', deleteImpact.project_id)}
                  >
                    <span className="flex items-center gap-2">
                      <Users className="w-4 h-4 text-muted-foreground" />
                      <span>Clients</span>
                    </span>
                    <span className="font-medium">{deleteImpact.clients}</span>
                  </button>

                  <button
                    type="button"
                    className="w-full flex items-center justify-between px-3 py-2 rounded-md hover:bg-muted text-left text-sm"
                    onClick={() => handleImpactNavigate('units', deleteImpact.project_id)}
                  >
                    <span className="flex items-center gap-2">
                      <Home className="w-4 h-4 text-muted-foreground" />
                      <span>Units</span>
                    </span>
                    <span className="font-medium">{deleteImpact.units}</span>
                  </button>

                  <button
                    type="button"
                    className="w-full flex items-center justify-between px-3 py-2 rounded-md hover:bg-muted text-left text-sm"
                    onClick={() => handleImpactNavigate('documents', deleteImpact.project_id)}
                  >
                    <span className="flex items-center gap-2">
                      <FileText className="w-4 h-4 text-muted-foreground" />
                      <span>Documents (total / non-draft)</span>
                    </span>
                    <span className="font-medium">
                      {deleteImpact.documents_total} / {deleteImpact.documents_non_draft}
                    </span>
                  </button>

                  <button
                    type="button"
                    className="w-full flex items-center justify-between px-3 py-2 rounded-md hover:bg-muted text-left text-sm"
                    onClick={() => handleImpactNavigate('timeline', deleteImpact.project_id)}
                  >
                    <span className="flex items-center gap-2">
                      <Calendar className="w-4 h-4 text-muted-foreground" />
                      <span>Timelines & steps</span>
                    </span>
                    <span className="font-medium">
                      {deleteImpact.timelines} / {deleteImpact.timeline_steps}
                    </span>
                  </button>

                  <button
                    type="button"
                    className="w-full flex items-center justify-between px-3 py-2 rounded-md hover:bg-muted text-left text-sm"
                    onClick={() => handleImpactNavigate('vault', deleteImpact.project_id)}
                  >
                    <span className="flex items-center gap-2">
                      <FileText className="w-4 h-4 text-muted-foreground" />
                      <span>Vault documents</span>
                    </span>
                    <span className="font-medium">{deleteImpact.vault_documents}</span>
                  </button>

                  <button
                    type="button"
                    className="w-full flex items-center justify-between px-3 py-2 rounded-md hover:bg-muted text-left text-sm"
                    onClick={() => handleImpactNavigate('decisions', deleteImpact.project_id)}
                  >
                    <span className="flex items-center gap-2">
                      <AlertTriangle className="w-4 h-4 text-muted-foreground" />
                      <span>Decisions & change requests</span>
                    </span>
                    <span className="font-medium">
                      {deleteImpact.decisions} / {deleteImpact.change_requests}
                    </span>
                  </button>

                  <div className="text-xs text-muted-foreground pt-1 border-t border-border mt-2">
                    Team members: <span className="font-medium text-foreground">{deleteImpact.team_members}</span> •
                    Activities: <span className="font-medium text-foreground">{deleteImpact.activities}</span>
                  </div>
                </div>
              </div>
            )}

            <div className="text-xs text-muted-foreground">
              Issued financial documents (Sent/Approved/Paid, etc.) prevent deletion. In that case, archive the project instead.
            </div>
          </div>

          <DialogFooter>
            <Button
              variant="outline"
              onClick={() => setDeleteDialogOpen(false)}
              disabled={deleteLoading}
            >
              Cancel
            </Button>
            <Button
              variant="destructive"
              onClick={handleConfirmDelete}
              disabled={deleteLoading || !!deleteError}
              data-testid="confirm-delete-project-btn"
            >
              {deleteLoading ? (
                <>
                  <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                  Deleting…
                </>
              ) : (
                'Delete project & data'
              )}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Units Management Dialog */}
      <Dialog open={showUnitsDialog} onOpenChange={setShowUnitsDialog}>
        <DialogContent className="max-w-lg">
          <DialogHeader>
            <DialogTitle>Manage Units - {unitsProject?.name}</DialogTitle>
            <DialogDescription>
              Add units to your project. Units can be assigned to clients later.
            </DialogDescription>
          </DialogHeader>
          
          <div className="py-4">
            {/* Add new unit */}
            <div className="flex flex-col sm:flex-row gap-2 mb-4">
              <Input
                value={newUnit}
                onChange={(e) => setNewUnit(e.target.value)}
                placeholder="Enter unit reference (e.g., A-301, B-502)"
                onKeyDown={(e) => e.key === 'Enter' && handleAddUnit()}
                data-testid="new-unit-input"
              />
              <Button onClick={handleAddUnit} disabled={!newUnit.trim()}>
                <Plus className="w-4 h-4 mr-1" />
                Add
              </Button>
            </div>
            
            {/* Units list */}
            <div className="border border-border rounded-lg max-h-64 overflow-y-auto">
              {loadingUnits ? (
                <div className="p-8 text-center">
                  <Loader2 className="w-6 h-6 animate-spin mx-auto text-muted-foreground" />
                </div>
              ) : units.length === 0 ? (
                <div className="p-8 text-center text-muted-foreground">
                  <Home className="w-8 h-8 mx-auto mb-2 opacity-30" />
                  <p className="text-sm">No units added yet</p>
                  <p className="text-xs mt-1">Add units like A-301, B-502, etc.</p>
                </div>
              ) : (
                <div className="divide-y divide-border">
                  {units.map(unit => (
                    <div 
                      key={unit.unit_id} 
                      className="flex items-center justify-between px-4 py-3 hover:bg-muted/50"
                    >
                      <div className="flex items-center gap-3">
                        <div className="w-8 h-8 bg-primary/10 rounded-lg flex items-center justify-center">
                          <Home className="w-4 h-4 text-primary" />
                        </div>
                        <div>
                          <p className="font-medium text-sm">{unit.unit_reference}</p>
                          {(unit.assigned_clients_count || 0) > 0 ? (
                            <p className="text-xs text-muted-foreground">
                              {(unit.assigned_clients_count || 0)} client{(unit.assigned_clients_count || 0) !== 1 ? 's' : ''} assigned
                            </p>
                          ) : (
                            <p className="text-xs text-amber-600">Available</p>
                          )}
                        </div>
                      </div>
                      <div className="flex items-center gap-1">
                        <Button
                          variant="outline"
                          size="sm"
                          onClick={() => {
                            setShowUnitsDialog(false);
                            navigate(`/agent/units/${unit.unit_id}`);
                          }}
                        >
                          Manage
                        </Button>
                        {(unit.assigned_clients_count || 0) === 0 && (
                          <Button
                            variant="ghost"
                            size="icon"
                            className="h-8 w-8 text-muted-foreground hover:text-destructive"
                            onClick={() => handleDeleteUnit(unit.unit_id)}
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
            
            <p className="text-xs text-muted-foreground mt-3">
              {units.length} unit{units.length !== 1 ? 's' : ''} • {units.filter(u => (u.assigned_clients_count || 0) === 0).length} available
            </p>
          </div>
          
          <DialogFooter>
            <Button variant="outline" onClick={() => setShowUnitsDialog(false)}>
              Done
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Limit Reached Modal */}
      <Dialog open={showLimitModal} onOpenChange={setShowLimitModal}>
        <DialogContent className="max-w-md">
          <DialogHeader>
            <div className="w-12 h-12 bg-amber-500/10 rounded-xl flex items-center justify-center mx-auto mb-2">
              <AlertTriangle className="w-6 h-6 text-amber-500" />
            </div>
            <DialogTitle className="text-center">Property Limit Reached</DialogTitle>
            <DialogDescription className="text-center">
              Your {subscriptionStatus?.plan_name} plan allows up to {subscriptionStatus?.property_limit} properties.
            </DialogDescription>
          </DialogHeader>
          
          <div className="py-4">
            <div className="bg-muted/50 rounded-lg p-4 space-y-3">
              <div className="flex items-center justify-between">
                <span className="text-sm text-muted-foreground">Current usage</span>
                <span className="font-semibold">
                  {subscriptionStatus?.unit_usage} / {subscriptionStatus?.property_limit}
                </span>
              </div>
              <Progress 
                value={100} 
                className="h-2 bg-amber-200" 
              />
            </div>
            <p className="text-sm text-muted-foreground text-center mt-4">
              Upgrade your plan to create more properties and grow your business.
            </p>
          </div>
          
          <DialogFooter className="flex-col sm:flex-row gap-2">
            <Button variant="outline" onClick={() => setShowLimitModal(false)} className="sm:flex-1">
              Maybe Later
            </Button>
            <Link to="/agent/billing" className="sm:flex-1">
              <Button className="w-full bg-gradient-to-r from-amber-500 to-orange-500 hover:from-amber-600 hover:to-orange-600">
                <Zap className="w-4 h-4 mr-2" />
                View Upgrade Options
              </Button>
            </Link>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </AgentLayout>
  );
};
