import { useState, useEffect } from 'react';
import { useParams, useNavigate, Link } from 'react-router-dom';
import { AgentLayout } from '../../components/AgentLayout';
import { useSettings } from '../../context/SettingsContext';
import { formatContextSubtitle } from '../../lib/utils';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '../../components/ui/card';
import { Button } from '../../components/ui/button';
import { Input } from '../../components/ui/input';
import { Label } from '../../components/ui/label';
import { Badge } from '../../components/ui/badge';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '../../components/ui/select';
import { toast } from 'sonner';
import { 
  ArrowLeft, 
  Save, 
  Building2, 
  Home, 
  User, 
  Mail, 
  Phone,
  Loader2,
  Plus
} from 'lucide-react';
import { cn } from '../../lib/utils';

const API = process.env.REACT_APP_BACKEND_URL + '/api';

const getAuthHeaders = () => {
  const token = localStorage.getItem('auth_token');
  return token ? { 'Authorization': `Bearer ${token}` } : {};
};

export const AgentClientDetail = () => {
  const { clientId } = useParams();
  const navigate = useNavigate();
  const { t } = useSettings();
  const [client, setClient] = useState(null);
  const [project, setProject] = useState(null);
  const [projects, setProjects] = useState([]);
  const [units, setUnits] = useState([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [newUnitReference, setNewUnitReference] = useState('');
  const [creatingUnit, setCreatingUnit] = useState(false);
  const [formData, setFormData] = useState({
    name: '',
    email: '',
    phone: '',
    project_id: '',
    unit_id: ''
  });

  useEffect(() => {
    fetchProjects();
  }, [clientId]);

  useEffect(() => {
    fetchClient();
  }, [clientId, projects.length]);

  const fetchProjects = async () => {
    try {
      const res = await fetch(`${API}/projects`, { credentials: 'include', headers: getAuthHeaders() });
      if (res.ok) {
        setProjects(await res.json());
      }
    } catch (error) {
      console.error('Failed to fetch projects:', error);
    }
  };

  const fetchClient = async () => {
    try {
      const response = await fetch(`${API}/clients/${clientId}`, { credentials: 'include', headers: getAuthHeaders() });
      if (response.ok) {
        const data = await response.json();
        if (data.project_id && projects.length > 0 && !projects.some((p) => p.project_id === data.project_id)) {
          toast.error('This client is outside your project access');
          navigate('/agent/clients');
          return;
        }
        setClient(data);
        setFormData({
          name: data.name,
          email: data.email,
          phone: data.phone || '',
          project_id: data.project_id || '',
          unit_id: data.unit_id || ''
        });
        
        // Fetch project and units
        if (data.project_id) {
          fetchProjectAndUnits(data.project_id);
        } else {
          setProject(null);
          setUnits([]);
        }
      } else {
        toast.error('Client not found');
        navigate('/agent/clients');
      }
    } catch (error) {
      console.error('Failed to fetch client:', error);
      toast.error('Failed to load client');
    } finally {
      setLoading(false);
    }
  };

  const fetchProjectAndUnits = async (projectId) => {
    try {
      const [projectRes, unitsRes] = await Promise.all([
        fetch(`${API}/projects/${projectId}`, { credentials: 'include', headers: getAuthHeaders() }),
        fetch(`${API}/projects/${projectId}/units`, { credentials: 'include', headers: getAuthHeaders() })
      ]);
      
      if (projectRes.ok) {
        setProject(await projectRes.json());
      }
      if (unitsRes.ok) {
        setUnits(await unitsRes.json());
      }
    } catch (error) {
      console.error('Failed to fetch project data:', error);
    }
  };

  const handleUnitChange = (newUnitId) => {
    setFormData({ ...formData, unit_id: newUnitId });
  };

  const handleProjectChange = async (projectId) => {
    setFormData((prev) => ({ ...prev, project_id: projectId, unit_id: '' }));
    if (projectId) {
      await fetchProjectAndUnits(projectId);
    } else {
      setProject(null);
      setUnits([]);
    }
  };

  const handleCreateUnitInline = async () => {
    if (!formData.project_id) {
      toast.error('Select a project first');
      return;
    }
    if (!newUnitReference.trim()) {
      toast.error('Enter a unit reference');
      return;
    }
    setCreatingUnit(true);
    try {
      const res = await fetch(`${API}/projects/${formData.project_id}/units`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', ...getAuthHeaders() },
        credentials: 'include',
        body: JSON.stringify({ unit_reference: newUnitReference.trim() }),
      });
      if (!res.ok) {
        const error = await res.json();
        throw new Error(error.detail || 'Failed to create unit');
      }
      const created = await res.json();
      setNewUnitReference('');
      toast.success('Unit created');
      await fetchProjectAndUnits(formData.project_id);
      setFormData((prev) => ({ ...prev, unit_id: created.unit_id }));
    } catch (error) {
      toast.error(error.message);
    } finally {
      setCreatingUnit(false);
    }
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setSaving(true);

    try {
      const response = await fetch(`${API}/clients/${clientId}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json', ...getAuthHeaders() },
        credentials: 'include',
        body: JSON.stringify({
          name: formData.name,
          email: formData.email,
          phone: formData.phone,
          project_id: formData.project_id || null,
          unit_id: formData.unit_id || null
        })
      });

      if (response.ok) {
        toast.success('Client updated successfully');
        fetchClient();
      } else {
        const error = await response.json();
        toast.error(error.detail || 'Failed to update client');
      }
    } catch (error) {
      toast.error('Failed to update client');
    } finally {
      setSaving(false);
    }
  };

  if (loading) {
    return (
      <AgentLayout>
        <div className="animate-pulse space-y-6">
          <div className="h-8 w-48 bg-muted rounded" />
          <div className="h-64 bg-muted rounded-lg" />
        </div>
      </AgentLayout>
    );
  }

  const currentUnit = units.find(u => u.unit_id === formData.unit_id);
  return (
    <AgentLayout>
      <div className="max-w-3xl space-y-6" data-testid="agent-client-detail">
        {/* Header */}
        <div>
          <Link 
            to="/agent/clients" 
            className="inline-flex items-center text-sm text-muted-foreground hover:text-primary mb-4 transition-colors"
            data-testid="back-link"
          >
            <ArrowLeft className="w-4 h-4 mr-2" />
            {t('common.back')} to {t('nav.clients')}
          </Link>
          <div className="flex items-center gap-4">
            <div className="w-14 h-14 bg-primary/10 rounded-xl flex items-center justify-center">
              <User className="w-7 h-7 text-primary" />
            </div>
            <div>
              <h1 className="text-3xl font-outfit font-semibold text-foreground tracking-tight">
                {client?.name || 'Edit Client'}
              </h1>
              <p className="text-muted-foreground mt-0.5">
                {project?.name && (
                  <span className="flex items-center gap-1">
                    <Building2 className="w-4 h-4" />
                    {formatContextSubtitle({ project_name: project.name, unit_reference: client?.unit_reference !== 'General' ? client?.unit_reference : undefined })}
                  </span>
                )}
              </p>
            </div>
          </div>
        </div>

        <form onSubmit={handleSubmit} className="space-y-6">
          {/* Contact Information Card */}
          <Card className="border-border rounded-lg">
            <CardHeader className="pb-4">
              <CardTitle className="text-lg font-outfit flex items-center gap-2">
                <User className="w-5 h-5" />
                Contact Information
              </CardTitle>
              <CardDescription>Client's personal and contact details</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="grid gap-4 sm:grid-cols-2">
                <div className="space-y-2">
                  <Label htmlFor="name" className="flex items-center gap-2">
                    <User className="w-4 h-4 text-muted-foreground" />
                    Full Name
                  </Label>
                  <Input
                    id="name"
                    value={formData.name}
                    onChange={(e) => setFormData({...formData, name: e.target.value})}
                    className="rounded-lg"
                    required
                    data-testid="name-input"
                  />
                </div>

                <div className="space-y-2">
                  <Label htmlFor="email" className="flex items-center gap-2">
                    <Mail className="w-4 h-4 text-muted-foreground" />
                    Email
                  </Label>
                  <Input
                    id="email"
                    type="email"
                    value={formData.email}
                    onChange={(e) => setFormData({...formData, email: e.target.value})}
                    className="rounded-lg"
                    required
                    data-testid="email-input"
                  />
                </div>
              </div>

              <div className="space-y-2 max-w-sm">
                <Label htmlFor="phone" className="flex items-center gap-2">
                  <Phone className="w-4 h-4 text-muted-foreground" />
                  Phone
                </Label>
                <Input
                  id="phone"
                  value={formData.phone}
                  onChange={(e) => setFormData({...formData, phone: e.target.value})}
                  className="rounded-lg"
                  placeholder="+41 XX XXX XX XX"
                  data-testid="phone-input"
                />
              </div>
            </CardContent>
          </Card>

          {/* Property / Unit Assignment Card */}
          <Card className="border-border rounded-lg">
            <CardHeader className="pb-4">
              <CardTitle className="text-lg font-outfit flex items-center gap-2">
                <Home className="w-5 h-5" />
                Property / Unit Assignment
              </CardTitle>
              <CardDescription>
                Assign this client to a specific unit in {project?.name || 'the project'}
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              {/* Project Info (read-only) */}
              <div className="space-y-2">
                <Label className="text-muted-foreground flex items-center gap-2">
                  <Building2 className="w-4 h-4" />
                  Project
                </Label>
                <Select value={formData.project_id || 'none'} onValueChange={(value) => handleProjectChange(value === 'none' ? '' : value)}>
                  <SelectTrigger className="rounded-lg">
                    <SelectValue placeholder="Select project" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="none">No project selected</SelectItem>
                    {projects.map((p) => (
                      <SelectItem key={p.project_id} value={p.project_id}>
                        {p.name}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
                {project && (
                  <div className="flex items-center gap-3 p-3 bg-muted/50 rounded-lg">
                    <div className="w-10 h-10 bg-primary/10 rounded-lg flex items-center justify-center">
                      <Building2 className="w-5 h-5 text-primary" />
                    </div>
                    <div>
                      <p className="font-medium">{project?.name}</p>
                      <p className="text-sm text-muted-foreground">{project?.address || 'No address'}</p>
                    </div>
                  </div>
                )}
              </div>

              {/* Unit Selection */}
              <div className="space-y-2">
                <Label htmlFor="unit" className="flex items-center gap-2">
                  <Home className="w-4 h-4 text-muted-foreground" />
                  Assigned Unit
                </Label>
                
                {!formData.project_id ? (
                  <div className="p-4 bg-amber-50 dark:bg-amber-900/20 border border-amber-200 dark:border-amber-800 rounded-lg">
                    <p className="text-sm text-amber-800 dark:text-amber-200">
                      Select a project first to manage unit assignment.
                    </p>
                  </div>
                ) : units.length === 0 ? (
                  <div className="p-4 bg-amber-50 dark:bg-amber-900/20 border border-amber-200 dark:border-amber-800 rounded-lg">
                    <p className="text-sm text-amber-800 dark:text-amber-200">
                      No units defined for this project yet. 
                      <Link 
                        to="/agent/projects"
                        className="underline ml-1 hover:text-amber-900 dark:hover:text-amber-100"
                      >
                        Add units to the project
                      </Link>
                    </p>
                    <div className="mt-3 flex gap-2">
                      <Input
                        placeholder="New unit reference (e.g. A-301)"
                        value={newUnitReference}
                        onChange={(e) => setNewUnitReference(e.target.value)}
                        className="bg-background"
                      />
                      <Button onClick={handleCreateUnitInline} disabled={creatingUnit || !newUnitReference.trim()}>
                        {creatingUnit ? <Loader2 className="w-4 h-4 animate-spin" /> : <Plus className="w-4 h-4" />}
                      </Button>
                    </div>
                  </div>
                ) : (
                  <>
                    <Select
                      value={formData.unit_id || "none"}
                      onValueChange={(value) => handleUnitChange(value === "none" ? "" : value)}
                      data-testid="unit-select"
                    >
                      <SelectTrigger className="rounded-lg" id="unit">
                        <SelectValue placeholder="Select a unit">
                          {formData.unit_id ? (
                            <span className="flex items-center gap-2">
                              <Home className="w-4 h-4" />
                              {currentUnit?.unit_reference || currentUnit?.name}
                            </span>
                          ) : (
                            <span className="text-muted-foreground">No unit assigned</span>
                          )}
                        </SelectValue>
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="none">
                          <span className="text-muted-foreground">No unit assigned (General)</span>
                        </SelectItem>
                        {units.map(unit => {
                          const isCurrentClientUnit = unit.unit_id === client?.unit_id;
                          const assignedCount = Number(unit.assigned_clients_count || 0);
                          const hasOtherAssignees = assignedCount > (isCurrentClientUnit ? 1 : 0);
                          
                          return (
                            <SelectItem 
                              key={unit.unit_id} 
                              value={unit.unit_id}
                            >
                              <div className="flex items-center justify-between w-full gap-4">
                                <span className="flex items-center gap-2">
                                  <Home className="w-4 h-4 text-primary" />
                                  {unit.unit_reference || unit.name}
                                </span>
                                {isCurrentClientUnit ? (
                                  <Badge variant="secondary" className="text-xs">Current</Badge>
                                ) : hasOtherAssignees ? (
                                  <Badge variant="outline" className="text-xs">
                                    {assignedCount} clients
                                  </Badge>
                                ) : (
                                  <Badge variant="outline" className="text-xs text-green-600 border-green-300">
                                    Available
                                  </Badge>
                                )}
                              </div>
                            </SelectItem>
                          );
                        })}
                      </SelectContent>
                    </Select>
                    
                    {/* Unit status indicator */}
                    {formData.unit_id && currentUnit && (
                      <div className={cn(
                        "p-3 rounded-lg flex items-center gap-3",
                        currentUnit.unit_id === client?.unit_id 
                          ? "bg-green-50 dark:bg-green-900/20 border border-green-200 dark:border-green-800"
                          : "bg-blue-50 dark:bg-blue-900/20 border border-blue-200 dark:border-blue-800"
                      )}>
                        <div className={cn(
                          "w-10 h-10 rounded-lg flex items-center justify-center",
                          currentUnit.unit_id === client?.unit_id 
                            ? "bg-green-100 dark:bg-green-800"
                            : "bg-blue-100 dark:bg-blue-800"
                        )}>
                          <Home className={cn(
                            "w-5 h-5",
                            currentUnit.unit_id === client?.unit_id 
                              ? "text-green-700 dark:text-green-300"
                              : "text-blue-700 dark:text-blue-300"
                          )} />
                        </div>
                        <div>
                          <p className={cn(
                            "font-medium text-sm",
                            currentUnit.unit_id === client?.unit_id 
                              ? "text-green-800 dark:text-green-200"
                              : "text-blue-800 dark:text-blue-200"
                          )}>
                            {currentUnit.unit_reference || currentUnit.name}
                          </p>
                          <p className={cn(
                            "text-xs",
                            currentUnit.unit_id === client?.unit_id 
                              ? "text-green-600 dark:text-green-400"
                              : "text-blue-600 dark:text-blue-400"
                          )}>
                            {currentUnit.unit_id === client?.unit_id 
                              ? 'Currently assigned to this client'
                              : 'Will be assigned after saving'}
                          </p>
                          {currentUnit.unit_id === client?.unit_id && (
                            <Link to={`/agent/units/${currentUnit.unit_id}`}>
                              <Button variant="link" className="h-auto p-0 text-xs">
                                Manage this unit
                              </Button>
                            </Link>
                          )}
                        </div>
                      </div>
                    )}
                    
                    {!formData.unit_id && (
                      <p className="text-sm text-muted-foreground">
                        Select a unit to assign this client to a specific property.
                      </p>
                    )}
                  </>
                )}
              </div>
            </CardContent>
          </Card>

          {/* Action Buttons */}
          <div className="flex gap-3 pt-2">
            <Button
              type="button"
              variant="outline"
              className="rounded-lg"
              onClick={() => navigate('/agent/clients')}
            >
              {t('common.cancel')}
            </Button>
            <Button
              type="submit"
              className="rounded-lg"
              disabled={saving}
              data-testid="save-btn"
            >
              {saving ? (
                <Loader2 className="w-4 h-4 mr-2 animate-spin" />
              ) : (
                <Save className="w-4 h-4 mr-2" />
              )}
              {saving ? 'Saving...' : t('common.save')}
            </Button>
          </div>
        </form>
      </div>

    </AgentLayout>
  );
};
