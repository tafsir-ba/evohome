import { useState, useEffect } from 'react';
import { Link, useSearchParams } from 'react-router-dom';
import { AgentLayout } from '../../components/AgentLayout';
import { Card, CardContent, CardHeader, CardTitle } from '../../components/ui/card';
import { Button } from '../../components/ui/button';
import { Input } from '../../components/ui/input';
import { Label } from '../../components/ui/label';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../../components/ui/select';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from '../../components/ui/dialog';
import { toast } from 'sonner';
import { useSettings } from '../../context/SettingsContext';
import { useDataContext } from '../../context/DataContext';
import { 
  Plus, 
  Search, 
  Users,
  Mail,
  Phone,
  Building2,
  ArrowRight,
  Pencil,
  Trash2,
  X,
  Eye
} from 'lucide-react';

const API = process.env.REACT_APP_BACKEND_URL + '/api';

const getAuthHeaders = () => {
  const token = localStorage.getItem('auth_token');
  return token ? { 'Authorization': `Bearer ${token}` } : {};
};

export const AgentClients = () => {
  const { t } = useSettings();
  const [searchParams, setSearchParams] = useSearchParams();
  const projectFilter = searchParams.get('project');
  
  // SINGLE SOURCE OF TRUTH: DataContext for projects
  const { projects, refreshProjects } = useDataContext();
  
  const [clients, setClients] = useState([]);
  const [loading, setLoading] = useState(true);
  const [searchQuery, setSearchQuery] = useState('');
  const [createDialogOpen, setCreateDialogOpen] = useState(false);
  const [projectDialogOpen, setProjectDialogOpen] = useState(false);
  const [formLoading, setFormLoading] = useState(false);
  const [filterProject, setFilterProject] = useState(null);
  
  const [clientForm, setClientForm] = useState({
    name: '',
    email: '',
    phone: '',
    project_id: '',
    unit_id: ''
  });
  
  const [projectUnits, setProjectUnits] = useState([]);
  
  const [projectForm, setProjectForm] = useState({
    name: '',
    address: '',
    description: ''
  });

  useEffect(() => {
    fetchClients();
  }, [projectFilter]);

  // Update filter project when projects change
  useEffect(() => {
    if (projectFilter && projects.length > 0) {
      const proj = projects.find(p => p.project_id === projectFilter);
      setFilterProject(proj || null);
    }
  }, [projectFilter, projects]);

  const fetchClients = async () => {
    setLoading(true);
    try {
      const clientsUrl = projectFilter 
        ? `${API}/clients?project_id=${projectFilter}`
        : `${API}/clients`;
      
      const clientsRes = await fetch(clientsUrl, { credentials: 'include' });
      
      if (clientsRes.ok) setClients(await clientsRes.json());
    } catch (error) {
      console.error('Failed to fetch clients:', error);
      toast.error('Failed to load data');
    } finally {
      setLoading(false);
    }
  };

  const fetchProjectUnits = async (projectId) => {
    if (!projectId) {
      setProjectUnits([]);
      return;
    }
    try {
      const res = await fetch(`${API}/projects/${projectId}/units`, { credentials: 'include', headers: getAuthHeaders() });
      if (res.ok) {
        setProjectUnits(await res.json());
      }
    } catch (error) {
      console.error('Failed to fetch units:', error);
    }
  };

  const handleProjectChange = (value) => {
    setClientForm({...clientForm, project_id: value, unit_id: ''});
    fetchProjectUnits(value);
  };

  const handleCreateClient = async (e) => {
    e.preventDefault();
    setFormLoading(true);
    
    try {
      const response = await fetch(`${API}/clients`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', ...getAuthHeaders() },
        credentials: 'include',
        body: JSON.stringify(clientForm)
      });
      
      if (response.ok) {
        toast.success('Client created successfully');
        setCreateDialogOpen(false);
        setClientForm({ name: '', email: '', phone: '', project_id: '', unit_id: '' });
        setProjectUnits([]);
        fetchClients();
        refreshProjects(); // Update client_count on project cards
      } else {
        const error = await response.json();
        toast.error(error.detail);
      }
    } catch (error) {
      toast.error('Failed to create client');
    } finally {
      setFormLoading(false);
    }
  };

  const handleCreateProject = async (e) => {
    e.preventDefault();
    setFormLoading(true);
    
    try {
      const response = await fetch(`${API}/projects`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', ...getAuthHeaders() },
        credentials: 'include',
        body: JSON.stringify(projectForm)
      });
      
      if (response.ok) {
        toast.success('Project created successfully');
        setProjectDialogOpen(false);
        setProjectForm({ name: '', address: '', description: '' });
        refreshProjects(); // Refresh projects in DataContext
        fetchClients();
      } else {
        const error = await response.json();
        toast.error(error.detail);
      }
    } catch (error) {
      toast.error('Failed to create project');
    } finally {
      setFormLoading(false);
    }
  };

  const handleDeleteClient = async (clientId) => {
    if (!window.confirm('Are you sure you want to delete this client?')) return;
    
    try {
      const response = await fetch(`${API}/clients/${clientId}`, {
        method: 'DELETE',
        credentials: 'include'
      });
      
      if (response.ok) {
        toast.success('Client deleted');
        fetchClients();
        refreshProjects(); // Update client_count on project cards
      } else {
        toast.error('Failed to delete client');
      }
    } catch (error) {
      toast.error('Failed to delete client');
    }
  };

  const filteredClients = clients.filter(client =>
    client.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
    client.email.toLowerCase().includes(searchQuery.toLowerCase()) ||
    (client.unit_reference || '').toLowerCase().includes(searchQuery.toLowerCase())
  );

  const getProjectName = (projectId) => {
    const project = projects.find(p => p.project_id === projectId);
    return project?.name;
  };

  if (loading) {
    return (
      <AgentLayout>
        <div className="animate-pulse space-y-6">
          <div className="h-8 w-48 bg-muted rounded" />
          <div className="space-y-4">
            {[1, 2, 3].map(i => (
              <div key={i} className="h-24 bg-muted rounded-lg" />
            ))}
          </div>
        </div>
      </AgentLayout>
    );
  }

  const clearProjectFilter = () => {
    setSearchParams({});
    setFilterProject(null);
  };

  return (
    <AgentLayout>
      <div className="space-y-6" data-testid="agent-clients">
        {/* Header */}
        <div className="flex flex-col sm:flex-row sm:items-start sm:justify-between gap-4">
          <div>
            <h1 className="text-2xl sm:text-3xl font-outfit font-semibold text-foreground tracking-tight">
              {t('clients.title')}
            </h1>
            <div className="flex items-center gap-2 mt-1">
              <p className="text-muted-foreground">{clients.length} {filterProject ? t('clients.inProject') : t('clients.total')}</p>
              {filterProject && (
                <button 
                  onClick={clearProjectFilter}
                  className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-primary/10 text-primary text-xs font-medium hover:bg-primary/20 transition-colors"
                >
                  <Building2 className="w-3 h-3" />
                  {filterProject.name}
                  <X className="w-3 h-3" />
                </button>
              )}
            </div>
          </div>
          <div className="flex gap-3">
            <Button 
              variant="outline" 
              className="rounded-lg border-border"
              onClick={() => setProjectDialogOpen(true)}
              data-testid="create-project-btn"
            >
              <Building2 className="w-4 h-4 mr-2" />
              {t('projects.newProject')}
            </Button>
            <Button 
              className="rounded-lg"
              onClick={() => setCreateDialogOpen(true)}
              data-testid="create-client-btn"
            >
              <Plus className="w-4 h-4 mr-2" />
              New Client
            </Button>
          </div>
        </div>

        {/* Search */}
        <div className="relative max-w-md">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
          <Input
            placeholder="Search clients..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="pl-10 rounded-lg border-border"
            data-testid="search-input"
          />
        </div>

        {/* Clients List */}
        <div className="space-y-4">
          {filteredClients.length > 0 ? (
            filteredClients.map((client) => (
              <Card key={client.client_id} className="border-border rounded-lg hover:border-primary/20 transition-colors">
                <CardContent className="p-6">
                  <div className="flex items-start justify-between">
                    <div className="flex items-start gap-4">
                      <div className="w-12 h-12 bg-[#2E3A45] rounded-full flex items-center justify-center text-white font-medium">
                        {client.name.charAt(0)}
                      </div>
                      <div>
                        <h3 className="font-medium text-[#1A1A1A]">{client.name}</h3>
                        <div className="flex items-center gap-4 mt-1 text-sm text-muted-foreground">
                          <span className="flex items-center gap-1">
                            <Mail className="w-3 h-3" />
                            {client.email}
                          </span>
                          {client.phone && (
                            <span className="flex items-center gap-1">
                              <Phone className="w-3 h-3" />
                              {client.phone}
                            </span>
                          )}
                        </div>
                        <div className="flex items-center gap-2 mt-2">
                          {(client.project_name || getProjectName(client.project_id)) && (
                            <span className="text-xs font-medium px-2 py-1 bg-[#F0F2F5] rounded-lg">
                              {client.project_name || getProjectName(client.project_id)}
                            </span>
                          )}
                          {client.unit_reference && (
                            <span className="text-xs font-medium px-2 py-1 bg-[#F0F2F5] rounded-lg">
                              {client.unit_reference}
                            </span>
                          )}
                        </div>
                      </div>
                    </div>
                    <div className="flex items-center gap-2">
                      <Link to={`/agent/clients/${client.client_id}/preview`}>
                        <Button variant="outline" size="sm" className="rounded-lg gap-1.5" data-testid={`view-client-${client.client_id}`}>
                          <Eye className="w-4 h-4" />
                          View
                        </Button>
                      </Link>
                      <Link to={`/agent/clients/${client.client_id}`}>
                        <Button variant="ghost" size="sm" className="rounded-lg" data-testid={`edit-client-${client.client_id}`}>
                          <Pencil className="w-4 h-4" />
                        </Button>
                      </Link>
                      <Button 
                        variant="ghost" 
                        size="sm" 
                        className="rounded-lg text-muted-foreground hover:text-destructive hover:bg-destructive/10"
                        onClick={() => handleDeleteClient(client.client_id)}
                        data-testid={`delete-client-${client.client_id}`}
                      >
                        <Trash2 className="w-4 h-4" />
                      </Button>
                    </div>
                  </div>
                </CardContent>
              </Card>
            ))
          ) : (
            <div className="text-center py-12">
              <Users className="w-12 h-12 text-muted-foreground/30 mx-auto mb-4" />
              <p className="text-muted-foreground">
                {searchQuery ? 'No clients found matching your search' : 'No clients yet'}
              </p>
              {!searchQuery && (
                <Button 
                  className="mt-4 bg-primary hover:bg-primary/90 rounded-lg"
                  onClick={() => setCreateDialogOpen(true)}
                >
                  Add your first client
                </Button>
              )}
            </div>
          )}
        </div>
      </div>

      {/* Create Client Dialog */}
      <Dialog open={createDialogOpen} onOpenChange={setCreateDialogOpen}>
        <DialogContent className="rounded-lg">
          <DialogHeader>
            <DialogTitle className="font-outfit">Create New Client</DialogTitle>
          </DialogHeader>
          <form onSubmit={handleCreateClient}>
            <div className="space-y-4 py-4">
              <div className="space-y-2">
                <Label htmlFor="client-name">Full Name</Label>
                <Input
                  id="client-name"
                  value={clientForm.name}
                  onChange={(e) => setClientForm({...clientForm, name: e.target.value})}
                  placeholder="Sophie Müller"
                  className="rounded-lg"
                  required
                  data-testid="client-name-input"
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="client-email">Email</Label>
                <Input
                  id="client-email"
                  type="email"
                  value={clientForm.email}
                  onChange={(e) => setClientForm({...clientForm, email: e.target.value})}
                  placeholder="client@example.com"
                  className="rounded-lg"
                  required
                  data-testid="client-email-input"
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="client-phone">Phone (optional)</Label>
                <Input
                  id="client-phone"
                  value={clientForm.phone}
                  onChange={(e) => setClientForm({...clientForm, phone: e.target.value})}
                  placeholder="+41 79 123 45 67"
                  className="rounded-lg"
                  data-testid="client-phone-input"
                />
              </div>
              <div className="space-y-2">
                <Label>Project</Label>
                <Select 
                  value={clientForm.project_id} 
                  onValueChange={handleProjectChange}
                  required
                >
                  <SelectTrigger className="rounded-lg" data-testid="client-project-select">
                    <SelectValue placeholder="Select a project" />
                  </SelectTrigger>
                  <SelectContent>
                    {projects.map(project => (
                      <SelectItem key={project.project_id} value={project.project_id}>
                        {project.name}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              <div className="space-y-2">
                <Label>Unit</Label>
                <Select 
                  value={clientForm.unit_id} 
                  onValueChange={(value) => setClientForm({...clientForm, unit_id: value})}
                  disabled={!clientForm.project_id || projectUnits.length === 0}
                >
                  <SelectTrigger className="rounded-lg" data-testid="client-unit-select">
                    <SelectValue placeholder={
                      !clientForm.project_id 
                        ? "Select a project first" 
                        : projectUnits.length === 0 
                        ? "No units in project" 
                        : "Select a unit (optional)"
                    } />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="general">General (No specific unit)</SelectItem>
                    {projectUnits.map(unit => (
                      <SelectItem key={unit.unit_id} value={unit.unit_id}>
                        {unit.name || unit.unit_reference}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
            </div>
            <DialogFooter>
              <Button type="button" variant="outline" className="rounded-lg" onClick={() => setCreateDialogOpen(false)}>
                Cancel
              </Button>
              <Button type="submit" className="bg-primary hover:bg-primary/90 rounded-lg" disabled={formLoading} data-testid="submit-client-btn">
                {formLoading ? 'Creating...' : 'Create Client'}
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>

      {/* Create Project Dialog */}
      <Dialog open={projectDialogOpen} onOpenChange={setProjectDialogOpen}>
        <DialogContent className="rounded-lg">
          <DialogHeader>
            <DialogTitle className="font-outfit">Create New Project</DialogTitle>
          </DialogHeader>
          <form onSubmit={handleCreateProject}>
            <div className="space-y-4 py-4">
              <div className="space-y-2">
                <Label htmlFor="project-name">Project Name</Label>
                <Input
                  id="project-name"
                  value={projectForm.name}
                  onChange={(e) => setProjectForm({...projectForm, name: e.target.value})}
                  placeholder="Residenza Lago Vista"
                  className="rounded-lg"
                  required
                  data-testid="project-name-input"
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="project-address">Address</Label>
                <Input
                  id="project-address"
                  value={projectForm.address}
                  onChange={(e) => setProjectForm({...projectForm, address: e.target.value})}
                  placeholder="Via del Sole 15, 6900 Lugano"
                  className="rounded-lg"
                  required
                  data-testid="project-address-input"
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="project-description">Description (optional)</Label>
                <Input
                  id="project-description"
                  value={projectForm.description}
                  onChange={(e) => setProjectForm({...projectForm, description: e.target.value})}
                  placeholder="Luxury lakefront apartments..."
                  className="rounded-lg"
                  data-testid="project-description-input"
                />
              </div>
            </div>
            <DialogFooter>
              <Button type="button" variant="outline" className="rounded-lg" onClick={() => setProjectDialogOpen(false)}>
                Cancel
              </Button>
              <Button type="submit" className="bg-primary hover:bg-primary/90 rounded-lg" disabled={formLoading} data-testid="submit-project-btn">
                {formLoading ? 'Creating...' : 'Create Project'}
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>
    </AgentLayout>
  );
};
