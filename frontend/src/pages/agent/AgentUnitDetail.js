import { useEffect, useMemo, useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import { AgentLayout } from '../../components/AgentLayout';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '../../components/ui/card';
import { Button } from '../../components/ui/button';
import { Label } from '../../components/ui/label';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../../components/ui/select';
import { Badge } from '../../components/ui/badge';
import { toast } from 'sonner';
import { ArrowLeft, Home, UserPlus, Unlink2, Loader2, Users, Building2 } from 'lucide-react';

const API = process.env.REACT_APP_BACKEND_URL + '/api';

const getAuthHeaders = () => {
  const token = localStorage.getItem('auth_token');
  return token ? { Authorization: `Bearer ${token}` } : {};
};

export const AgentUnitDetail = () => {
  const { unitId } = useParams();
  const navigate = useNavigate();
  const [loading, setLoading] = useState(true);
  const [attaching, setAttaching] = useState(false);
  const [unit, setUnit] = useState(null);
  const [project, setProject] = useState(null);
  const [unitClients, setUnitClients] = useState([]);
  const [projectClients, setProjectClients] = useState([]);
  const [selectedClientId, setSelectedClientId] = useState('');

  const fetchData = async () => {
    setLoading(true);
    try {
      const unitRes = await fetch(`${API}/units/${unitId}`, { credentials: 'include', headers: getAuthHeaders() });
      if (!unitRes.ok) {
        throw new Error('Unit not found');
      }
      const unitData = await unitRes.json();
      setUnit(unitData);

      const [projectRes, assignedRes, clientsRes] = await Promise.all([
        fetch(`${API}/projects/${unitData.project_id}`, { credentials: 'include', headers: getAuthHeaders() }),
        fetch(`${API}/units/${unitId}/clients`, { credentials: 'include', headers: getAuthHeaders() }),
        fetch(`${API}/clients?project_id=${unitData.project_id}`, { credentials: 'include', headers: getAuthHeaders() }),
      ]);

      if (projectRes.ok) setProject(await projectRes.json());
      if (assignedRes.ok) setUnitClients(await assignedRes.json());
      if (clientsRes.ok) setProjectClients(await clientsRes.json());
    } catch (error) {
      toast.error(error.message || 'Failed to load unit');
      navigate('/agent/projects');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
  }, [unitId]);

  const candidateClients = useMemo(
    () => projectClients.filter((c) => c.client_id !== undefined && c.unit_id !== unitId),
    [projectClients, unitId]
  );

  const handleAttach = async () => {
    if (!selectedClientId) return;
    setAttaching(true);
    try {
      const response = await fetch(`${API}/units/${unitId}/clients/${selectedClientId}`, {
        method: 'POST',
        credentials: 'include',
        headers: getAuthHeaders(),
      });
      if (!response.ok) {
        const error = await response.json();
        throw new Error(error.detail || 'Failed to attach client');
      }
      setSelectedClientId('');
      toast.success('Client attached to unit');
      fetchData();
    } catch (error) {
      toast.error(error.message);
    } finally {
      setAttaching(false);
    }
  };

  const handleDetach = async (clientId) => {
    if (!window.confirm('Detach this client from the unit?')) return;
    try {
      const response = await fetch(`${API}/units/${unitId}/clients/${clientId}`, {
        method: 'DELETE',
        credentials: 'include',
        headers: getAuthHeaders(),
      });
      if (!response.ok) {
        const error = await response.json();
        throw new Error(error.detail || 'Failed to detach client');
      }
      toast.success('Client detached');
      fetchData();
    } catch (error) {
      toast.error(error.message);
    }
  };

  if (loading) {
    return (
      <AgentLayout>
        <div className="flex items-center justify-center py-20">
          <Loader2 className="w-6 h-6 animate-spin text-muted-foreground" />
        </div>
      </AgentLayout>
    );
  }

  return (
    <AgentLayout>
      <div className="max-w-4xl space-y-6">
        <Link to="/agent/projects" className="inline-flex items-center text-sm text-muted-foreground hover:text-primary">
          <ArrowLeft className="w-4 h-4 mr-2" />
          Back to Projects
        </Link>

        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Home className="w-5 h-5" />
              Unit {unit?.unit_reference}
            </CardTitle>
            <CardDescription className="flex items-center gap-4">
              <span className="inline-flex items-center gap-1"><Building2 className="w-4 h-4" />{project?.name || unit?.project_id}</span>
              <span className="inline-flex items-center gap-1"><Users className="w-4 h-4" />{unitClients.length} client{unitClients.length !== 1 ? 's' : ''}</span>
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="grid gap-3 md:grid-cols-[1fr_auto]">
              <div className="space-y-2">
                <Label>Attach Client To This Unit</Label>
                <Select value={selectedClientId} onValueChange={setSelectedClientId}>
                  <SelectTrigger>
                    <SelectValue placeholder="Select a client from this project" />
                  </SelectTrigger>
                  <SelectContent>
                    {candidateClients.map((c) => (
                      <SelectItem key={c.client_id} value={c.client_id}>
                        {c.name}{c.unit_reference ? ` (currently ${c.unit_reference})` : ''}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              <div className="flex items-end">
                <Button onClick={handleAttach} disabled={!selectedClientId || attaching}>
                  {attaching ? <Loader2 className="w-4 h-4 animate-spin mr-2" /> : <UserPlus className="w-4 h-4 mr-2" />}
                  Attach
                </Button>
              </div>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Clients In This Unit</CardTitle>
            <CardDescription>Manage all clients currently linked to this unit.</CardDescription>
          </CardHeader>
          <CardContent>
            {unitClients.length === 0 ? (
              <p className="text-sm text-muted-foreground">No clients assigned yet.</p>
            ) : (
              <div className="space-y-3">
                {unitClients.map((client) => (
                  <div key={client.client_id} className="flex items-center justify-between border rounded-lg p-3">
                    <div>
                      <p className="font-medium">{client.name}</p>
                      <p className="text-sm text-muted-foreground">{client.email}</p>
                    </div>
                    <div className="flex items-center gap-2">
                      <Badge variant="outline">{client.unit_reference || 'Unit linked'}</Badge>
                      <Link to={`/agent/clients/${client.client_id}`}>
                        <Button variant="outline" size="sm">Open</Button>
                      </Link>
                      <Button variant="ghost" size="sm" onClick={() => handleDetach(client.client_id)}>
                        <Unlink2 className="w-4 h-4 mr-1" />
                        Detach
                      </Button>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </CardContent>
        </Card>
      </div>
    </AgentLayout>
  );
};
