import { useState, useEffect } from 'react';
import { useParams, useNavigate, Link } from 'react-router-dom';
import { AgentLayout } from '../../components/AgentLayout';
import { useSettings } from '../../context/SettingsContext';
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
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from '../../components/ui/alert-dialog';
import { toast } from 'sonner';
import { 
  ArrowLeft, 
  Save, 
  Building2, 
  Home, 
  User, 
  Mail, 
  Phone,
  AlertTriangle,
  Loader2
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
  const [units, setUnits] = useState([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [formData, setFormData] = useState({
    name: '',
    email: '',
    phone: '',
    unit_id: '',
    force_unit_reassign: false
  });
  
  // Confirmation dialog state for reassigning units
  const [showReassignConfirm, setShowReassignConfirm] = useState(false);
  const [pendingUnitChange, setPendingUnitChange] = useState(null);
  const [conflictingClient, setConflictingClient] = useState(null);

  useEffect(() => {
    fetchClient();
  }, [clientId]);

  const fetchClient = async () => {
    try {
      const response = await fetch(`${API}/clients/${clientId}`, { credentials: 'include', headers: getAuthHeaders() });
      if (response.ok) {
        const data = await response.json();
        setClient(data);
        setFormData({
          name: data.name,
          email: data.email,
          phone: data.phone || '',
          unit_id: data.unit_id || '',
          force_unit_reassign: false
        });
        
        // Fetch project and units
        if (data.project_id) {
          fetchProjectAndUnits(data.project_id);
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
    // Check if unit is assigned to another client
    const selectedUnit = units.find(u => u.unit_id === newUnitId);
    
    if (selectedUnit && !selectedUnit.is_available && selectedUnit.assigned_client_id !== clientId) {
      // Unit is assigned to someone else - show confirmation
      setConflictingClient(selectedUnit.assigned_client_name);
      setPendingUnitChange(newUnitId);
      setShowReassignConfirm(true);
    } else {
      // Unit is available or already assigned to this client
      setFormData({ ...formData, unit_id: newUnitId });
    }
  };

  const confirmUnitReassign = () => {
    setFormData({ ...formData, unit_id: pendingUnitChange, force_unit_reassign: true });
    setShowReassignConfirm(false);
    setPendingUnitChange(null);
    setConflictingClient(null);
  };

  const cancelUnitReassign = () => {
    setShowReassignConfirm(false);
    setPendingUnitChange(null);
    setConflictingClient(null);
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
          unit_id: formData.unit_id || null,
          force_unit_reassign: formData.force_unit_reassign
        })
      });

      if (response.ok) {
        toast.success('Client updated successfully');
        // Reset force flag and refresh client data
        setFormData(prev => ({ ...prev, force_unit_reassign: false }));
        fetchClient();
      } else {
        const error = await response.json();
        if (response.status === 409) {
          // Unit conflict - show error with client name
          toast.error(error.detail);
        } else {
          toast.error(error.detail || 'Failed to update client');
        }
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
  const availableUnits = units.filter(u => u.is_available || u.unit_id === client?.unit_id);

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
                    {project.name}
                    {client?.unit_reference && client.unit_reference !== 'General' && (
                      <>
                        <span className="mx-1">•</span>
                        <Home className="w-4 h-4" />
                        {client.unit_reference}
                      </>
                    )}
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
                <div className="flex items-center gap-3 p-3 bg-muted/50 rounded-lg">
                  <div className="w-10 h-10 bg-primary/10 rounded-lg flex items-center justify-center">
                    <Building2 className="w-5 h-5 text-primary" />
                  </div>
                  <div>
                    <p className="font-medium">{project?.name || client?.project_id}</p>
                    <p className="text-sm text-muted-foreground">{project?.address || 'No address'}</p>
                  </div>
                </div>
              </div>

              {/* Unit Selection */}
              <div className="space-y-2">
                <Label htmlFor="unit" className="flex items-center gap-2">
                  <Home className="w-4 h-4 text-muted-foreground" />
                  Assigned Unit
                </Label>
                
                {units.length === 0 ? (
                  <div className="p-4 bg-amber-50 dark:bg-amber-900/20 border border-amber-200 dark:border-amber-800 rounded-lg">
                    <p className="text-sm text-amber-800 dark:text-amber-200">
                      No units defined for this project yet. 
                      <Link 
                        to={`/agent/projects/${client?.project_id}`}
                        className="underline ml-1 hover:text-amber-900 dark:hover:text-amber-100"
                      >
                        Add units to the project
                      </Link>
                    </p>
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
                              {currentUnit?.unit_reference || currentUnit?.name || 'Unit'}
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
                          const isAssignedToOther = !unit.is_available && !isCurrentClientUnit;
                          
                          return (
                            <SelectItem 
                              key={unit.unit_id} 
                              value={unit.unit_id}
                              className={cn(isAssignedToOther && "text-muted-foreground")}
                            >
                              <div className="flex items-center justify-between w-full gap-4">
                                <span className="flex items-center gap-2">
                                  <Home className={cn(
                                    "w-4 h-4",
                                    isAssignedToOther ? "text-muted-foreground" : "text-primary"
                                  )} />
                                  {unit.unit_reference || unit.name}
                                </span>
                                {isCurrentClientUnit ? (
                                  <Badge variant="secondary" className="text-xs">Current</Badge>
                                ) : isAssignedToOther ? (
                                  <Badge variant="outline" className="text-xs text-amber-600 border-amber-300">
                                    {unit.assigned_client_name}
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

      {/* Reassignment Confirmation Dialog */}
      <AlertDialog open={showReassignConfirm} onOpenChange={setShowReassignConfirm}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle className="flex items-center gap-2">
              <AlertTriangle className="w-5 h-5 text-amber-500" />
              Unit Already Assigned
            </AlertDialogTitle>
            <AlertDialogDescription>
              This unit is currently assigned to <strong>{conflictingClient}</strong>. 
              Reassigning it to {client?.name} will remove it from the other client.
              <br /><br />
              Do you want to proceed with the reassignment?
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel onClick={cancelUnitReassign}>Cancel</AlertDialogCancel>
            <AlertDialogAction onClick={confirmUnitReassign} className="bg-amber-600 hover:bg-amber-700">
              Reassign Unit
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </AgentLayout>
  );
};
