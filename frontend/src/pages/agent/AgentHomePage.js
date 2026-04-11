import { useState, useEffect, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { useDataContext } from '../../context/DataContext';
import { AgentLayout } from '../../components/AgentLayout';
import { Card, CardContent } from '../../components/ui/card';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../../components/ui/select';
import { Home, Building2, User } from 'lucide-react';

// Decomposed dashboard components
import { ControlTower } from '../../components/dashboard/ControlTower';
import { CommandBar } from '../../components/dashboard/CommandBar';
import { ActionPreviewDrawer } from '../../components/dashboard/ActionPreviewDrawer';
import { WorkflowDialog } from '../../components/dashboard/WorkflowDialog';
import { RecentActivity } from '../../components/dashboard/RecentActivity';
import { API, getAuthHeaders } from '../../components/dashboard/utils';

export const AgentHomePage = () => {
  const navigate = useNavigate();
  const { projects, selectedProjectId, setSelectedProjectId, refreshProjects } = useDataContext();

  // Context-dependent state
  const [selectedClient, setSelectedClient] = useState('');
  const [selectedUnit, setSelectedUnit] = useState('');
  const [clients, setClients] = useState([]);
  const [units, setUnits] = useState([]);
  const [recentWork, setRecentWork] = useState([]);

  // Preview drawer state — shared between CommandBar and ActionPreviewDrawer
  const [previewOpen, setPreviewOpen] = useState(false);
  const [previewData, setPreviewData] = useState(null);
  const uploadedFileRef = useRef(null);

  // Workflow dialog state
  const [workflowTemplates, setWorkflowTemplates] = useState([]);
  const [workflowDialogOpen, setWorkflowDialogOpen] = useState(false);
  const [selectedWorkflow, setSelectedWorkflow] = useState(null);

  // Refs
  const commandBarRef = useRef(null);
  const lastContextProjectRef = useRef(null);
  const currentProjectFetchRef = useRef(null);
  const fetchingContextRef = useRef(false);

  // ── Init ──
  useEffect(() => {
    fetchRecentWork();
    fetchWorkflowTemplates();
  }, []);

  // ── Project context sync ──
  useEffect(() => {
    if (fetchingContextRef.current) return;
    if (lastContextProjectRef.current === selectedProjectId) return;

    const fetchId = Date.now();
    currentProjectFetchRef.current = fetchId;

    if (lastContextProjectRef.current !== null && lastContextProjectRef.current !== selectedProjectId) {
      setClients([]);
      setUnits([]);
      setSelectedClient('');
      setSelectedUnit('');
    }
    lastContextProjectRef.current = selectedProjectId;

    if (selectedProjectId) {
      fetchingContextRef.current = true;
      fetchProjectContext(selectedProjectId, fetchId).finally(() => {
        fetchingContextRef.current = false;
      });
    }
  }, [selectedProjectId]);

  // ── Data fetching ──
  const fetchRecentWork = async () => {
    try {
      const res = await fetch(`${API}/command/recent-work`, { credentials: 'include', headers: getAuthHeaders() });
      if (res.ok) {
        const data = await res.json();
        setRecentWork(data.items || []);
      }
    } catch (error) {
      console.error('Failed to fetch recent work:', error);
    }
  };

  const fetchProjectContext = async (projectId, fetchId) => {
    if (!projectId) { setClients([]); setUnits([]); return; }
    try {
      const res = await fetch(`${API}/projects/${projectId}/context`, { credentials: 'include', headers: getAuthHeaders() });
      if (currentProjectFetchRef.current !== fetchId) return;
      if (res.ok) {
        const data = await res.json();
        setClients(data.clients || []);
        setUnits(data.units || []);
      }
    } catch (error) {
      console.error('Failed to fetch project context:', error);
    }
  };

  const fetchWorkflowTemplates = async () => {
    try {
      const res = await fetch(`${API}/workflows/templates`, { credentials: 'include', headers: getAuthHeaders() });
      if (res.ok) {
        const data = await res.json();
        setWorkflowTemplates(data.templates || []);
      }
    } catch (error) {
      console.error('Failed to fetch workflow templates:', error);
    }
  };

  // ── Callbacks ──
  const handlePreviewReady = (data, fileRef) => {
    setPreviewData(data);
    if (fileRef?.current) uploadedFileRef.current = fileRef.current;
    setPreviewOpen(true);
  };

  const handleRefresh = () => {
    fetchRecentWork();
    refreshProjects();
  };

  const handleExecuted = () => {
    fetchRecentWork();
    refreshProjects();
    if (commandBarRef.current?.clear) commandBarRef.current.clear();
  };

  const selectedProject = projects.find((p) => p.project_id === selectedProjectId);
  const context = {
    projectId: selectedProjectId,
    clientId: selectedClient,
    unitId: selectedUnit,
    projectName: selectedProject?.name,
  };

  return (
    <AgentLayout>
      <div className="space-y-6" data-testid="agent-home-page">
        {/* Control Tower — Stats, Action Cards, KPI Strip */}
        <ControlTower projectCount={projects.length} onRefresh={handleRefresh} />

        {/* Context Selector */}
        <Card className="border-border">
          <CardContent className="py-4">
            <div className="flex flex-wrap items-center gap-4">
              <div className="flex items-center gap-2 text-sm text-muted-foreground">
                <Home className="w-4 h-4" />
                <span>Working Context:</span>
              </div>

              <Select value={selectedProjectId} onValueChange={setSelectedProjectId}>
                <SelectTrigger className="w-[200px]" data-testid="context-project-select">
                  <SelectValue placeholder="Select Project" />
                </SelectTrigger>
                <SelectContent>
                  {projects.map((p) => (
                    <SelectItem key={p.project_id} value={p.project_id}>
                      <span className="flex items-center gap-2"><Building2 className="w-4 h-4" />{p.name}</span>
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>

              <Select value={selectedClient || 'all'} onValueChange={(val) => setSelectedClient(val === 'all' ? '' : val)}>
                <SelectTrigger className="w-[200px]" data-testid="context-client-select">
                  <SelectValue placeholder="Select Client" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">All Clients</SelectItem>
                  {clients.map((c) => (
                    <SelectItem key={c.client_id} value={c.client_id}>
                      <span className="flex items-center gap-2"><User className="w-4 h-4" />{c.name}</span>
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>

              {units.length > 0 && (
                <Select value={selectedUnit || 'all'} onValueChange={(val) => setSelectedUnit(val === 'all' ? '' : val)}>
                  <SelectTrigger className="w-[150px]" data-testid="context-unit-select">
                    <SelectValue placeholder="Select Unit" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="all">All Units</SelectItem>
                    {units.map((u) => (
                      <SelectItem key={u.unit_id} value={u.unit_id}>{u.unit_reference || u.name}</SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              )}
            </div>
          </CardContent>
        </Card>

        {/* Command Bar — text, voice, file input */}
        <CommandBar ref={commandBarRef} context={context} onPreviewReady={handlePreviewReady} />

        {/* Recent Activity */}
        <RecentActivity items={recentWork} onFocusCommand={() => commandBarRef.current?.focus()} />
      </div>

      {/* Action Preview Drawer */}
      <ActionPreviewDrawer
        open={previewOpen}
        onOpenChange={setPreviewOpen}
        previewData={previewData}
        setPreviewData={setPreviewData}
        context={context}
        uploadedFileRef={uploadedFileRef}
        onExecuted={handleExecuted}
      />

      {/* Workflow Dialog */}
      <WorkflowDialog
        open={workflowDialogOpen}
        onOpenChange={setWorkflowDialogOpen}
        template={selectedWorkflow}
        projectContext={context}
        onExecuted={handleExecuted}
      />
    </AgentLayout>
  );
};

export default AgentHomePage;
