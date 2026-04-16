import { useState, useEffect, useRef } from 'react';
import { useSearchParams } from 'react-router-dom';
import { AgentLayout } from '../../components/AgentLayout';
import { Card, CardContent, CardHeader, CardTitle } from '../../components/ui/card';
import { Button } from '../../components/ui/button';
import { Input } from '../../components/ui/input';
import { Label } from '../../components/ui/label';
import { Textarea } from '../../components/ui/textarea';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../../components/ui/select';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from '../../components/ui/dialog';
import { TeamContactImport } from '../../components/TeamContactImport';
import { useDataContext } from '../../context/DataContext';
import { toast } from 'sonner';
import { 
  Plus, 
  Search, 
  Users,
  User,
  Mail,
  Phone,
  Globe,
  Building2,
  Pencil,
  Trash2,
  Loader2,
  FileUp,
  MapPin,
  Sparkles
} from 'lucide-react';

const API = process.env.REACT_APP_BACKEND_URL + '/api';

const getAuthHeaders = () => {
  const token = localStorage.getItem('auth_token');
  return token ? { 'Authorization': `Bearer ${token}` } : {};
};

const ROLE_SUGGESTIONS = [
  'Plumber',
  'Electrician',
  'Architect',
  'Interior Designer',
  'Carpenter',
  'HVAC Technician',
  'General Contractor',
  'Project Manager',
  'Landscaper',
  'Painter'
];

export const AgentTeam = () => {
  const [searchParams] = useSearchParams();
  const projectFilter = searchParams.get('project');
  
  // SINGLE SOURCE OF TRUTH: DataContext for projects
  const { 
    projects, 
    selectedProjectId, 
    setSelectedProjectId,
    selectedProject,
    loading: projectsLoading 
  } = useDataContext();
  
  // Track current fetch to ignore stale responses
  const currentFetchRef = useRef(null);
  const abortControllerRef = useRef(null);
  
  const [teamMembers, setTeamMembers] = useState([]);
  const [loading, setLoading] = useState(true);
  const [searchQuery, setSearchQuery] = useState('');
  
  const [dialogOpen, setDialogOpen] = useState(false);
  const [editingMember, setEditingMember] = useState(null);
  const [formLoading, setFormLoading] = useState(false);
  
  const [form, setForm] = useState({
    company_name: '',
    contact_name: '',
    role: '',
    email: '',
    phone: '',
    website: '',
    address: '',
    notes: ''
  });
  
  const [importDialogOpen, setImportDialogOpen] = useState(false);

  // Handle URL filter on mount - set selected project if provided
  // Only run once when projects are loaded
  useEffect(() => {
    if (projectFilter && projects.length > 0 && projectFilter !== selectedProjectId) {
      const projectExists = projects.some(p => p.project_id === projectFilter);
      if (projectExists) {
        setSelectedProjectId(projectFilter);
      } else {
        setSearchParams((prev) => {
          const next = new URLSearchParams(prev);
          next.delete('project');
          return next;
        }, { replace: true });
      }
    }
  }, [projectFilter, projects.length, selectedProjectId, setSearchParams]); // Only depend on length, not full array

  const fetchTeamMembers = async (projectId) => {
    if (!projectId) {
      setTeamMembers([]);
      setLoading(false);
      return;
    }
    
    // Create new abort controller for this request
    abortControllerRef.current = new AbortController();
    const fetchId = Date.now();
    currentFetchRef.current = fetchId;
    
    setLoading(true);
    
    try {
      const res = await fetch(`${API}/projects/${projectId}/team`, { 
        credentials: 'include',
        signal: abortControllerRef.current.signal
      });
      
      // CRITICAL: Ignore response if project changed during fetch
      if (currentFetchRef.current !== fetchId) {
        console.log('Ignoring stale team response for project:', projectId);
        return;
      }
      
      if (res.ok) {
        const data = await res.json();
        if (currentFetchRef.current === fetchId) {
          setTeamMembers(data);
        }
      }
    } catch (error) {
      if (error.name === 'AbortError') return;
      console.error('Failed to fetch team:', error);
    } finally {
      if (currentFetchRef.current === fetchId) {
        setLoading(false);
      }
    }
  };

  // Track current project to avoid unnecessary clears
  const lastProjectRef = useRef(null);
  const fetchingRef = useRef(false);

  // CRITICAL: On project change, cancel pending requests
  useEffect(() => {
    // Skip if already fetching
    if (fetchingRef.current) return;
    
    // Skip if project hasn't actually changed AND we've loaded before
    if (lastProjectRef.current === selectedProjectId && lastProjectRef.current !== null) {
      setLoading(false);
      return;
    }
    
    // Cancel any pending fetch
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
    }
    
    // Only clear state if switching to a DIFFERENT project (not initial load)
    if (lastProjectRef.current !== null && lastProjectRef.current !== selectedProjectId) {
      setTeamMembers([]);
    }
    
    lastProjectRef.current = selectedProjectId;
    
    if (selectedProjectId) {
      fetchingRef.current = true;
      fetchTeamMembers(selectedProjectId).finally(() => {
        fetchingRef.current = false;
      });
    } else {
      setTeamMembers([]);
      setLoading(false);
    }
    
    return () => {
      if (abortControllerRef.current) {
        abortControllerRef.current.abort();
      }
    };
  }, [selectedProjectId]);

  const handleOpenDialog = (member = null) => {
    if (member) {
      setEditingMember(member);
      setForm({
        company_name: member.company_name || member.name || '',
        contact_name: member.contact_name || '',
        role: member.role,
        email: member.email || '',
        phone: member.phone || '',
        website: member.website || '',
        address: member.address || '',
        notes: member.notes || ''
      });
    } else {
      setEditingMember(null);
      setForm({ company_name: '', contact_name: '', role: '', email: '', phone: '', website: '', address: '', notes: '' });
    }
    setDialogOpen(true);
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!selectedProjectId) {
      toast.error('Please select a project first');
      return;
    }
    
    setFormLoading(true);
    try {
      const url = editingMember
        ? `${API}/projects/${selectedProjectId}/team/${editingMember.member_id}`
        : `${API}/projects/${selectedProjectId}/team`;
      
      const res = await fetch(url, {
        method: editingMember ? 'PUT' : 'POST',
        headers: { 'Content-Type': 'application/json', ...getAuthHeaders() },
        credentials: 'include',
        body: JSON.stringify(form)
      });

      if (res.ok) {
        toast.success(editingMember ? 'Team member updated' : 'Team member added');
        setDialogOpen(false);
        fetchTeamMembers();
      } else {
        const error = await res.json();
        throw new Error(error.detail || 'Failed to save');
      }
    } catch (error) {
      toast.error(error.message);
    } finally {
      setFormLoading(false);
    }
  };

  const handleDelete = async (memberId) => {
    if (!confirm('Are you sure you want to remove this team member?')) return;
    
    try {
      const res = await fetch(`${API}/projects/${selectedProjectId}/team/${memberId}`, {
        method: 'DELETE',
        credentials: 'include'
      });

      if (res.ok) {
        toast.success('Team member removed');
        fetchTeamMembers();
      } else {
        throw new Error('Failed to delete');
      }
    } catch (error) {
      toast.error(error.message);
    }
  };

  const filteredMembers = teamMembers.filter(member => {
    const companyName = (member.company_name || member.name || '').toLowerCase();
    const contactName = (member.contact_name || '').toLowerCase();
    const role = (member.role || '').toLowerCase();
    const query = searchQuery.toLowerCase();
    return companyName.includes(query) || contactName.includes(query) || role.includes(query);
  });

  // Use selectedProject object from DataContext
  const selectedProjectData = selectedProject;

  return (
    <AgentLayout>
      <div className="space-y-6">
        {/* Header */}
        <div className="flex items-start justify-between">
          <div>
            <h1 className="text-3xl font-outfit font-semibold text-foreground tracking-tight">
              Team Directory
            </h1>
            <p className="text-muted-foreground mt-1">
              Manage project team contacts for your clients
            </p>
          </div>
          <div className="flex gap-2">
            <Button 
              variant="outline"
              className="rounded-lg"
              onClick={() => setImportDialogOpen(true)}
              disabled={!selectedProjectId}
              data-testid="import-contacts-btn"
            >
              <Sparkles className="w-4 h-4 mr-2" />
              Import from Document
            </Button>
            <Button 
              className="rounded-lg"
              onClick={() => handleOpenDialog()}
              disabled={!selectedProjectId}
              data-testid="add-team-member-btn"
            >
              <Plus className="w-4 h-4 mr-2" />
              Add Member
            </Button>
          </div>
        </div>

        {/* Project Selector */}
        <Card className="border-border">
          <CardContent className="py-4">
            <div className="flex items-center gap-4">
              <Building2 className="w-5 h-5 text-muted-foreground" />
              <Select value={selectedProjectId} onValueChange={setSelectedProjectId}>
                <SelectTrigger className="w-64" data-testid="project-selector">
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
              {selectedProjectData && (
                <span className="text-sm text-muted-foreground">
                  {teamMembers.length} team member{teamMembers.length !== 1 ? 's' : ''}
                </span>
              )}
            </div>
          </CardContent>
        </Card>

        {/* Search */}
        {teamMembers.length > 0 && (
          <div className="relative max-w-sm">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
            <Input
              placeholder="Search team members..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="pl-9 rounded-lg"
              data-testid="search-team"
            />
          </div>
        )}

        {/* Team List */}
        {!selectedProjectId ? (
          <Card>
            <CardContent className="py-12 text-center">
              <Building2 className="w-12 h-12 text-muted-foreground/30 mx-auto mb-4" />
              <p className="text-muted-foreground">Select a project to view team members</p>
            </CardContent>
          </Card>
        ) : loading ? (
          <div className="space-y-3">
            {[1, 2, 3].map(i => (
              <div key={i} className="h-24 bg-muted rounded-lg animate-pulse" />
            ))}
          </div>
        ) : filteredMembers.length === 0 ? (
          <Card>
            <CardContent className="py-12 text-center">
              <Users className="w-12 h-12 text-muted-foreground/30 mx-auto mb-4" />
              <p className="text-muted-foreground">
                {searchQuery ? 'No team members found' : 'No team members yet'}
              </p>
              {!searchQuery && (
                <Button 
                  className="mt-4 rounded-lg"
                  onClick={() => handleOpenDialog()}
                >
                  <Plus className="w-4 h-4 mr-2" />
                  Add First Team Member
                </Button>
              )}
            </CardContent>
          </Card>
        ) : (
          <div className="grid gap-3">
            {filteredMembers.map(member => (
              <Card key={member.member_id} className="border-border hover:shadow-md transition-shadow" data-testid={`team-member-${member.member_id}`}>
                <CardContent className="py-4">
                  <div className="flex items-start justify-between">
                    <div className="flex items-start gap-4">
                      <div className="w-12 h-12 rounded-full bg-primary/10 flex items-center justify-center flex-shrink-0">
                        <User className="w-6 h-6 text-primary" />
                      </div>
                      <div className="min-w-0">
                        <h3 className="font-semibold text-foreground">{member.company_name || member.name}</h3>
                        {member.contact_name && (
                          <p className="text-sm text-muted-foreground">{member.contact_name}</p>
                        )}
                        <p className="text-sm text-primary font-medium">{member.role}</p>
                        <div className="flex items-center gap-4 mt-2 flex-wrap">
                          {member.email && (
                            <a 
                              href={`mailto:${member.email}`}
                              className="flex items-center gap-1.5 text-sm text-muted-foreground hover:text-foreground transition-colors"
                            >
                              <Mail className="w-3.5 h-3.5" />
                              <span className="truncate max-w-[200px]">{member.email}</span>
                            </a>
                          )}
                          {member.phone && (
                            <a 
                              href={`tel:${member.phone}`}
                              className="flex items-center gap-1.5 text-sm text-muted-foreground hover:text-foreground transition-colors"
                            >
                              <Phone className="w-3.5 h-3.5" />
                              <span>{member.phone}</span>
                            </a>
                          )}
                          {member.website && (
                            <a 
                              href={member.website}
                              target="_blank"
                              rel="noopener noreferrer"
                              className="flex items-center gap-1.5 text-sm text-muted-foreground hover:text-foreground transition-colors"
                            >
                              <Globe className="w-3.5 h-3.5" />
                              <span>Website</span>
                            </a>
                          )}
                          {member.address && (
                            <span className="flex items-center gap-1.5 text-sm text-muted-foreground">
                              <MapPin className="w-3.5 h-3.5" />
                              <span className="truncate max-w-[200px]">{member.address}</span>
                            </span>
                          )}
                        </div>
                        {member.notes && (
                          <p className="text-sm text-muted-foreground mt-2 line-clamp-2">
                            {member.notes}
                          </p>
                        )}
                      </div>
                    </div>
                    <div className="flex items-center gap-1">
                      <Button
                        variant="ghost"
                        size="icon"
                        className="h-8 w-8"
                        onClick={() => handleOpenDialog(member)}
                        data-testid={`edit-member-${member.member_id}`}
                      >
                        <Pencil className="w-4 h-4" />
                      </Button>
                      <Button
                        variant="ghost"
                        size="icon"
                        className="h-8 w-8 text-muted-foreground hover:text-destructive"
                        onClick={() => handleDelete(member.member_id)}
                        data-testid={`delete-member-${member.member_id}`}
                      >
                        <Trash2 className="w-4 h-4" />
                      </Button>
                    </div>
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>
        )}
      </div>

      {/* Add/Edit Dialog */}
      <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
        <DialogContent className="max-w-md">
          <DialogHeader>
            <DialogTitle className="font-outfit">
              {editingMember ? 'Edit Team Member' : 'Add Team Member'}
            </DialogTitle>
          </DialogHeader>
          <form onSubmit={handleSubmit}>
            <div className="space-y-4 py-4">
              <div className="space-y-2">
                <Label htmlFor="company_name">Company Name *</Label>
                <Input
                  id="company_name"
                  value={form.company_name}
                  onChange={(e) => setForm({ ...form, company_name: e.target.value })}
                  placeholder="SaniTech SA"
                  required
                  data-testid="member-company-name-input"
                />
              </div>
              
              <div className="space-y-2">
                <Label htmlFor="contact_name">Contact Name *</Label>
                <Input
                  id="contact_name"
                  value={form.contact_name}
                  onChange={(e) => setForm({ ...form, contact_name: e.target.value })}
                  placeholder="Pierre Dupont"
                  required
                  data-testid="member-contact-name-input"
                />
              </div>
              
              <div className="space-y-2">
                <Label htmlFor="role">Role *</Label>
                <Input
                  id="role"
                  value={form.role}
                  onChange={(e) => setForm({ ...form, role: e.target.value })}
                  placeholder="Plumber"
                  required
                  list="role-suggestions"
                  data-testid="member-role-input"
                />
                <datalist id="role-suggestions">
                  {ROLE_SUGGESTIONS.map(role => (
                    <option key={role} value={role} />
                  ))}
                </datalist>
              </div>
              
              <div className="space-y-2">
                <Label htmlFor="email">Email</Label>
                <Input
                  id="email"
                  type="email"
                  value={form.email}
                  onChange={(e) => setForm({ ...form, email: e.target.value })}
                  placeholder="pierre@sanitech.ch"
                  data-testid="member-email-input"
                />
              </div>
              
              <div className="space-y-2">
                <Label htmlFor="phone">Phone</Label>
                <Input
                  id="phone"
                  value={form.phone}
                  onChange={(e) => setForm({ ...form, phone: e.target.value })}
                  placeholder="+41 76 555 0101"
                  data-testid="member-phone-input"
                />
              </div>
              
              <div className="space-y-2">
                <Label htmlFor="website">Website</Label>
                <Input
                  id="website"
                  type="url"
                  value={form.website}
                  onChange={(e) => setForm({ ...form, website: e.target.value })}
                  placeholder="https://sanitech.ch"
                  data-testid="member-website-input"
                />
              </div>
              
              <div className="space-y-2">
                <Label htmlFor="address">Address</Label>
                <Input
                  id="address"
                  value={form.address}
                  onChange={(e) => setForm({ ...form, address: e.target.value })}
                  placeholder="Rue du Lac 15, 1200 Genève"
                  data-testid="member-address-input"
                />
              </div>
              
              <div className="space-y-2">
                <Label htmlFor="notes">Notes</Label>
                <Textarea
                  id="notes"
                  value={form.notes}
                  onChange={(e) => setForm({ ...form, notes: e.target.value })}
                  placeholder="Additional information..."
                  rows={2}
                  data-testid="member-notes-input"
                />
              </div>
            </div>
            
            <DialogFooter>
              <Button type="button" variant="outline" onClick={() => setDialogOpen(false)}>
                Cancel
              </Button>
              <Button type="submit" disabled={formLoading} data-testid="save-member-btn">
                {formLoading && <Loader2 className="w-4 h-4 animate-spin mr-2" />}
                {editingMember ? 'Save Changes' : 'Add Member'}
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>

      {/* Import Contacts Dialog */}
      <TeamContactImport
        open={importDialogOpen}
        onOpenChange={setImportDialogOpen}
        projectId={selectedProjectId}
        onImportComplete={() => fetchTeamMembers(selectedProjectId)}
      />
    </AgentLayout>
  );
};

export default AgentTeam;
