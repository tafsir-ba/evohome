import { useState, useEffect, useRef } from 'react';
import { useSearchParams } from 'react-router-dom';
import { AgentLayout } from '../../components/AgentLayout';
import { Card, CardContent, CardHeader, CardTitle } from '../../components/ui/card';
import { Button } from '../../components/ui/button';
import { Input } from '../../components/ui/input';
import { Label } from '../../components/ui/label';
import { Textarea } from '../../components/ui/textarea';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../../components/ui/select';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter, DialogDescription } from '../../components/ui/dialog';
import { toast } from 'sonner';
import { useDataContext } from '../../context/DataContext';
import { parseApiError } from '../../lib/api';
import { 
  Plus, 
  CheckCircle2,
  Circle,
  Clock,
  Shield,
  ChevronRight,
  Pencil,
  Trash2,
  FileText,
  MessageSquare,
  Link2,
  Unlink,
  Building2,
  Loader2,
  Calendar,
  LayoutTemplate,
  GripVertical,
  Sparkles,
  Upload,
  X,
  ChevronUp,
  ChevronDown
} from 'lucide-react';
import { cn } from '../../lib/utils';

const API = process.env.REACT_APP_BACKEND_URL + '/api';

const getAuthHeaders = () => {
  const token = localStorage.getItem('auth_token');
  return token ? { 'Authorization': `Bearer ${token}` } : {};
};

const STATUS_CONFIG = {
  pending: { icon: Circle, color: 'text-muted-foreground', bg: 'bg-muted', label: 'Pending' },
  in_progress: { icon: Clock, color: 'text-blue-500', bg: 'bg-blue-500/10', label: 'In Progress' },
  completed: { icon: CheckCircle2, color: 'text-emerald-500', bg: 'bg-emerald-500/10', label: 'Completed' },
  approved: { icon: Shield, color: 'text-purple-500', bg: 'bg-purple-500/10', label: 'Approved' }
};

const NEXT_STATUS = {
  pending: 'in_progress',
  in_progress: 'completed',
  completed: 'approved',
  approved: null
};

export const AgentWorkflow = () => {
  const [searchParams, setSearchParams] = useSearchParams();
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
  
  const [timeline, setTimeline] = useState(null);
  const [steps, setSteps] = useState([]);
  const [templates, setTemplates] = useState([]);
  const [activities, setActivities] = useState([]);
  const [loading, setLoading] = useState(true);
  
  // Dialog states
  const [templateDialog, setTemplateDialog] = useState(false);
  const [stepDialog, setStepDialog] = useState({ open: false, step: null });
  const [linkDialog, setLinkDialog] = useState({ open: false, step: null });
  const [noteDialog, setNoteDialog] = useState({ open: false, step: null });
  
  // AI Extraction state - separate from published timeline
  const [aiExtractDialog, setAiExtractDialog] = useState(false);
  const [extractFile, setExtractFile] = useState(null);
  const [extracting, setExtracting] = useState(false);
  const [extractedTimeline, setExtractedTimeline] = useState(null);
  const [editingPhases, setEditingPhases] = useState([]);
  
  // Manual Timeline state
  const [manualTimelineDialog, setManualTimelineDialog] = useState(false);
  const [manualSteps, setManualSteps] = useState([
    { name: '', description: '', planned_date: '' }
  ]);
  
  const [formLoading, setFormLoading] = useState(false);
  
  // Add step dialog
  const [addStepDialog, setAddStepDialog] = useState(false);
  const [newStep, setNewStep] = useState({ title: '', description: '', planned_date: '' });

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

  // Single canonical fetch for workflow data
  // Backend is source of truth. No fallbacks.
  const fetchWorkflow = async (projectId) => {
    if (!projectId) {
      setTimeline(null);
      setSteps([]);
      setActivities([]);
      setLoading(false);
      return;
    }
    
    // Create new abort controller for this request
    abortControllerRef.current = new AbortController();
    const fetchId = Date.now();
    currentFetchRef.current = fetchId;
    
    setLoading(true);
    
    try {
      const res = await fetch(`${API}/projects/${projectId}/workflow/full`, { 
        credentials: 'include',
        signal: abortControllerRef.current.signal
      });
      
      // Ignore response if project changed during fetch
      if (currentFetchRef.current !== fetchId) {
        return;
      }
      
      if (res.ok) {
        const data = await res.json();
        if (currentFetchRef.current === fetchId) {
          // Map backend response to local state
          setTimeline(data.timeline_id ? { timeline_id: data.timeline_id } : null);
          setSteps(data.steps || []);
          setActivities(data.activities || []);
          setTemplates(data.templates || []);
        }
      }
    } catch (error) {
      if (error.name === 'AbortError') return;
      console.error('Failed to fetch workflow:', error);
    } finally {
      if (currentFetchRef.current === fetchId) {
        setLoading(false);
      }
    }
  };

  // Track current project to avoid unnecessary clears
  const lastProjectRef = useRef(null);
  const fetchingRef = useRef(false);

  // On project change, fetch workflow from canonical endpoint
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
      setTimeline(null);
      setSteps([]);
      setActivities([]);
      setExtractedTimeline(null);
      setEditingPhases([]);
    }
    
    lastProjectRef.current = selectedProjectId;
    
    if (selectedProjectId) {
      fetchingRef.current = true;
      fetchWorkflow(selectedProjectId).finally(() => {
        fetchingRef.current = false;
      });
    } else {
      setTimeline(null);
      setSteps([]);
      setLoading(false);
    }
    
    return () => {
      if (abortControllerRef.current) {
        abortControllerRef.current.abort();
      }
    };
  }, [selectedProjectId]);

  const handleApplyTemplate = async (templateId) => {
    setFormLoading(true);
    try {
      const res = await fetch(`${API}/timeline/templates/${templateId}/apply?project_id=${selectedProjectId}`, {
        method: 'POST',
        credentials: 'include'
      });
      
      if (res.ok) {
        toast.success('Timeline created from template');
        fetchWorkflow(selectedProjectId);
        setTemplateDialog(false);
      } else {
        const error = await parseApiError(res);
        throw new Error(error.message || 'Failed to apply template');
      }
    } catch (error) {
      toast.error(error.message);
    } finally {
      setFormLoading(false);
    }
  };

  const handleDeleteTimeline = async () => {
    if (!timeline || !confirm('Delete this timeline? This cannot be undone.')) return;
    
    // Use canonical timeline_id
    const timelineId = timeline.timeline_id;
    if (!timelineId) {
      toast.error('Invalid timeline ID');
      return;
    }
    
    try {
      const res = await fetch(`${API}/timeline/${timelineId}`, {
        method: 'DELETE',
        credentials: 'include'
      });
      
      if (res.ok) {
        toast.success('Timeline deleted');
        setTimeline(null);
        setSteps([]);
      } else {
        throw new Error('Failed to delete');
      }
    } catch (error) {
      toast.error(error.message);
    }
  };

  // Change step status via dropdown
  const handleStatusChange = async (stepId, newStatus) => {
    try {
      const res = await fetch(`${API}/timeline/steps/${stepId}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json', ...getAuthHeaders() },
        credentials: 'include',
        body: JSON.stringify({ status: newStatus })
      });
      
      if (res.ok) {
        fetchWorkflow(selectedProjectId);
      } else {
        throw new Error('Failed to update status');
      }
    } catch (error) {
      toast.error(error.message);
    }
  };

  // Reorder steps
  const handleMoveStep = async (stepId, direction) => {
    const currentIndex = steps.findIndex(s => s.step_id === stepId);
    if (currentIndex === -1) return;
    
    const newIndex = direction === 'up' ? currentIndex - 1 : currentIndex + 1;
    if (newIndex < 0 || newIndex >= steps.length) return;
    
    // Swap order_index values
    const currentStep = steps[currentIndex];
    const targetStep = steps[newIndex];
    
    try {
      // Update both steps
      await Promise.all([
        fetch(`${API}/timeline/steps/${currentStep.step_id}`, {
          method: 'PATCH',
          headers: { 'Content-Type': 'application/json', ...getAuthHeaders() },
          credentials: 'include',
          body: JSON.stringify({ order_index: targetStep.order_index })
        }),
        fetch(`${API}/timeline/steps/${targetStep.step_id}`, {
          method: 'PATCH',
          headers: { 'Content-Type': 'application/json', ...getAuthHeaders() },
          credentials: 'include',
          body: JSON.stringify({ order_index: currentStep.order_index })
        })
      ]);
      
      fetchWorkflow(selectedProjectId);
    } catch (error) {
      toast.error('Failed to reorder steps');
    }
  };

  const handleUpdateStep = async (stepId, updates) => {
    try {
      const res = await fetch(`${API}/timeline/steps/${stepId}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json', ...getAuthHeaders() },
        credentials: 'include',
        body: JSON.stringify(updates)
      });
      
      if (res.ok) {
        toast.success('Step updated');
        fetchWorkflow(selectedProjectId);
        setStepDialog({ open: false, step: null });
      } else {
        const error = await parseApiError(res);
        throw new Error(error.message || 'Failed to update');
      }
    } catch (error) {
      toast.error(error.message);
    }
  };

  const handleAdvanceStatus = async (step) => {
    const nextStatus = NEXT_STATUS[step.status];
    if (!nextStatus) return;
    
    await handleUpdateStep(step.step_id, { status: nextStatus });
  };

  const handleAddStep = async () => {
    if (!timeline || !newStep.title.trim()) {
      toast.error('Please enter a step title');
      return;
    }
    
    setFormLoading(true);
    const timelineId = timeline.timeline_id;
    
    try {
      const res = await fetch(`${API}/timeline/${timelineId}/steps`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', ...getAuthHeaders() },
        credentials: 'include',
        body: JSON.stringify({
          title: newStep.title,
          description: newStep.description,
          planned_date: newStep.planned_date || null
        })
      });
      
      if (res.ok) {
        toast.success('Step added');
        setAddStepDialog(false);
        setNewStep({ title: '', description: '', planned_date: '' });
        fetchWorkflow(selectedProjectId);
      } else {
        const error = await parseApiError(res);
        throw new Error(error.message || 'Failed to add step');
      }
    } catch (error) {
      toast.error(error.message);
    } finally {
      setFormLoading(false);
    }
  };

  const handleDeleteStep = async (stepId, stepTitle) => {
    if (!confirm(`Delete step "${stepTitle}"? This cannot be undone.`)) return;
    
    try {
      const res = await fetch(`${API}/timeline/steps/${stepId}`, {
        method: 'DELETE',
        credentials: 'include'
      });
      
      if (res.ok) {
        toast.success('Step deleted');
        fetchWorkflow(selectedProjectId);
      } else {
        const error = await parseApiError(res);
        throw new Error(error.message || 'Failed to delete step');
      }
    } catch (error) {
      toast.error(error.message);
    }
  };

  const handleCreateManualTimeline = async () => {
    if (!selectedProjectId) {
      toast.error('Please select a project first');
      return;
    }
    
    // Filter out empty steps
    const validSteps = manualSteps.filter(s => s.name.trim());
    if (validSteps.length === 0) {
      toast.error('Please add at least one step');
      return;
    }
    
    setFormLoading(true);
    try {
      const res = await fetch(`${API}/timeline/create`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', ...getAuthHeaders() },
        credentials: 'include',
        body: JSON.stringify({
          project_id: selectedProjectId,
          name: 'Project Timeline',
          steps: validSteps.map((step, index) => ({
            title: step.name,
            description: step.description,
            planned_date: step.planned_date || null,
            order: index + 1,
            status: 'pending'
          }))
        })
      });
      
      if (res.ok) {
        toast.success('Timeline created successfully');
        setManualTimelineDialog(false);
        setManualSteps([{ name: '', description: '', planned_date: '' }]);
        fetchWorkflow(selectedProjectId);
      } else {
        const error = await parseApiError(res);
        throw new Error(error.message || 'Failed to create timeline');
      }
    } catch (error) {
      toast.error(error.message);
    } finally {
      setFormLoading(false);
    }
  };

  const addManualStep = () => {
    setManualSteps([...manualSteps, { name: '', description: '', planned_date: '' }]);
  };

  const removeManualStep = (index) => {
    if (manualSteps.length > 1) {
      setManualSteps(manualSteps.filter((_, i) => i !== index));
    }
  };

  const updateManualStep = (index, field, value) => {
    const updated = [...manualSteps];
    updated[index][field] = value;
    setManualSteps(updated);
  };

  const handleLinkDocument = async (stepId, activityId) => {
    setFormLoading(true);
    try {
      const res = await fetch(`${API}/timeline/steps/${stepId}/documents`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', ...getAuthHeaders() },
        credentials: 'include',
        body: JSON.stringify({ activity_id: activityId })
      });
      
      if (res.ok) {
        toast.success('Document linked');
        fetchWorkflow(selectedProjectId);
        setLinkDialog({ open: false, step: null });
      } else {
        const error = await parseApiError(res);
        throw new Error(error.message || 'Failed to link');
      }
    } catch (error) {
      toast.error(error.message);
    } finally {
      setFormLoading(false);
    }
  };

  const handleUnlinkDocument = async (stepId, activityId) => {
    try {
      const res = await fetch(`${API}/timeline/steps/${stepId}/documents/${activityId}`, {
        method: 'DELETE',
        credentials: 'include'
      });
      
      if (res.ok) {
        toast.success('Document unlinked');
        fetchWorkflow(selectedProjectId);
      } else {
        throw new Error('Failed to unlink');
      }
    } catch (error) {
      toast.error(error.message);
    }
  };

  const handleAddNote = async (stepId, content) => {
    setFormLoading(true);
    try {
      const res = await fetch(`${API}/timeline/steps/${stepId}/notes`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', ...getAuthHeaders() },
        credentials: 'include',
        body: JSON.stringify({ content })
      });
      
      if (res.ok) {
        toast.success('Note added');
        fetchWorkflow(selectedProjectId);
        setNoteDialog({ open: false, step: null });
      } else {
        throw new Error('Failed to add note');
      }
    } catch (error) {
      toast.error(error.message);
    } finally {
      setFormLoading(false);
    }
  };

  // AI Timeline Extraction
  const handleExtractTimeline = async () => {
    if (!extractFile) {
      toast.error('Please select a file');
      return;
    }
    
    setExtracting(true);
    try {
      const formData = new FormData();
      formData.append('file', extractFile);
      formData.append('project_id', selectedProjectId);
      
      const res = await fetch(`${API}/timeline/extract`, {
        method: 'POST',
        credentials: 'include',
        headers: getAuthHeaders(),
        body: formData
      });
      
      if (res.ok) {
        const data = await res.json();
        setExtractedTimeline(data);
        setEditingPhases(data.extracted_data.phases || []);
        toast.success('Timeline extracted! Review and approve below.');
      } else {
        const error = await parseApiError(res);
        throw new Error(error.message || 'Extraction failed');
      }
    } catch (error) {
      toast.error(error.message);
    } finally {
      setExtracting(false);
    }
  };

  const handleApproveTimeline = async () => {
    if (!extractedTimeline || editingPhases.length === 0) {
      toast.error('No timeline to approve');
      return;
    }
    
    setFormLoading(true);
    try {
      const formData = new FormData();
      formData.append('project_id', selectedProjectId);
      formData.append('phases', JSON.stringify(editingPhases));
      
      const res = await fetch(`${API}/timeline/extractions/${extractedTimeline.extraction_id}/approve`, {
        method: 'POST',
        credentials: 'include',
        headers: getAuthHeaders(),
        body: formData
      });
      
      if (res.ok) {
        toast.success('Timeline approved and applied to project!');
        setAiExtractDialog(false);
        setExtractedTimeline(null);
        setEditingPhases([]);
        setExtractFile(null);
        fetchWorkflow(selectedProjectId);
      } else {
        const error = await parseApiError(res);
        throw new Error(error.message || 'Failed to approve');
      }
    } catch (error) {
      toast.error(error.message);
    } finally {
      setFormLoading(false);
    }
  };

  const updatePhase = (index, field, value) => {
    setEditingPhases(prev => prev.map((p, i) => 
      i === index ? { ...p, [field]: value } : p
    ));
  };

  const removePhase = (index) => {
    setEditingPhases(prev => prev.filter((_, i) => i !== index));
  };

  const addPhase = () => {
    setEditingPhases(prev => [...prev, {
      name: 'New Phase',
      order: prev.length + 1,
      planned_date: '',
      description: ''
    }]);
  };

  // Use selectedProject object from DataContext
  const selectedProjectData = selectedProject;

  // Calculate progress
  const completedSteps = steps.filter(s => s.status === 'completed' || s.status === 'approved').length;
  const progressPercent = steps.length > 0 ? Math.round((completedSteps / steps.length) * 100) : 0;

  return (
    <AgentLayout>
      <div className="space-y-6">
        {/* Header */}
        <div className="flex items-start justify-between">
          <div>
            <h1 className="text-3xl font-outfit font-semibold text-foreground tracking-tight">
              Construction Timeline
            </h1>
            <p className="text-muted-foreground mt-1">
              Manage project stages and track progress
            </p>
          </div>
        </div>

        {/* Project Selector */}
        <Card className="border-border">
          <CardContent className="py-4">
            <div className="flex flex-col gap-3 sm:flex-row sm:items-center">
              <Building2 className="w-5 h-5 text-muted-foreground" />
              <Select value={selectedProjectId} onValueChange={setSelectedProjectId}>
                <SelectTrigger className="w-full sm:w-64 max-w-full" data-testid="project-selector">
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
              {selectedProjectData && timeline && (
                <div className="flex w-full flex-col gap-2 sm:ml-auto sm:w-auto sm:flex-row sm:items-center sm:justify-end">
                  <div className="text-sm">
                    <span className="text-muted-foreground">Progress: </span>
                    <span className="font-semibold text-primary">{progressPercent}%</span>
                  </div>
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={handleDeleteTimeline}
                    className="w-full text-destructive hover:text-destructive sm:w-auto"
                  >
                    <Trash2 className="w-4 h-4 mr-1" />
                    Delete Timeline
                  </Button>
                </div>
              )}
            </div>
          </CardContent>
        </Card>

        {/* Main Content */}
        {!selectedProjectId ? (
          <Card>
            <CardContent className="py-12 text-center">
              <Building2 className="w-12 h-12 text-muted-foreground/30 mx-auto mb-4" />
              <p className="text-muted-foreground">Select a project to manage its timeline</p>
            </CardContent>
          </Card>
        ) : loading ? (
          <div className="space-y-3">
            {[1, 2, 3, 4, 5].map(i => (
              <div key={i} className="h-20 bg-muted rounded-lg animate-pulse" />
            ))}
          </div>
        ) : !timeline ? (
          <Card>
            <CardContent className="py-12 text-center">
              <LayoutTemplate className="w-12 h-12 text-muted-foreground/30 mx-auto mb-4" />
              <p className="text-muted-foreground mb-4">No timeline created for this project</p>
              <div className="flex items-center justify-center gap-3 flex-wrap">
                <Button onClick={() => setManualTimelineDialog(true)} data-testid="create-manual-btn">
                  <Plus className="w-4 h-4 mr-2" />
                  Create Timeline
                </Button>
                <Button variant="outline" onClick={() => setTemplateDialog(true)} data-testid="apply-template-btn">
                  <LayoutTemplate className="w-4 h-4 mr-2" />
                  From Template
                </Button>
                <Button variant="outline" onClick={() => setAiExtractDialog(true)} data-testid="ai-extract-btn">
                  <Sparkles className="w-4 h-4 mr-2" />
                  Extract with AI
                </Button>
              </div>
            </CardContent>
          </Card>
        ) : (
          <div className="space-y-2">
            {/* Progress bar */}
            <div className="h-2 bg-muted rounded-full overflow-hidden mb-6">
              <div 
                className="h-full bg-primary transition-all duration-500"
                style={{ width: `${progressPercent}%` }}
              />
            </div>

            {/* Steps */}
            {steps.map((step, index) => {
              const config = STATUS_CONFIG[step.status];
              const StatusIcon = config.icon;
              const isCurrentStep = step.status === 'in_progress';
              const isFirst = index === 0;
              const isLast = index === steps.length - 1;
              
              return (
                <Card 
                  key={step.step_id} 
                  className={cn(
                    "border-border transition-all",
                    isCurrentStep && "ring-2 ring-primary/30"
                  )}
                  data-testid={`step-${step.step_id}`}
                >
                  <CardContent className="py-4">
                    <div className="flex flex-col gap-3 sm:flex-row sm:items-start">
                      {/* Reorder controls */}
                      <div className="flex flex-row items-center gap-1 flex-shrink-0 pt-0 sm:flex-col sm:gap-0.5 sm:pt-1">
                        <Button
                          variant="ghost"
                          size="icon"
                          className="h-8 w-8"
                          disabled={isFirst}
                          onClick={() => handleMoveStep(step.step_id, 'up')}
                        >
                          <ChevronUp className="w-4 h-4" />
                        </Button>
                        <GripVertical className="w-4 h-4 text-muted-foreground/50" />
                        <Button
                          variant="ghost"
                          size="icon"
                          className="h-8 w-8"
                          disabled={isLast}
                          onClick={() => handleMoveStep(step.step_id, 'down')}
                        >
                          <ChevronDown className="w-4 h-4" />
                        </Button>
                      </div>

                      {/* Status indicator */}
                      <div className={cn(
                        "w-10 h-10 rounded-full flex items-center justify-center flex-shrink-0",
                        config.bg
                      )}>
                        <StatusIcon className={cn("w-5 h-5", config.color)} />
                      </div>
                      
                      {/* Content */}
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2 flex-wrap">
                          <span className="text-xs font-medium text-muted-foreground">
                            STEP {index + 1}
                          </span>
                          {/* Status Dropdown */}
                          <Select
                            value={step.status}
                            onValueChange={(value) => handleStatusChange(step.step_id, value)}
                          >
                            <SelectTrigger className={cn(
                              "h-6 w-auto text-[10px] font-semibold uppercase tracking-wider px-2 py-0.5 rounded-full border-0",
                              config.bg, config.color
                            )}>
                              <SelectValue />
                            </SelectTrigger>
                            <SelectContent>
                              <SelectItem value="pending">Pending</SelectItem>
                              <SelectItem value="in_progress">In Progress</SelectItem>
                              <SelectItem value="completed">Completed</SelectItem>
                              <SelectItem value="approved">Approved</SelectItem>
                            </SelectContent>
                          </Select>
                          {isCurrentStep && (
                            <span className="text-[10px] font-semibold uppercase tracking-wider px-2 py-0.5 rounded-full bg-primary text-primary-foreground animate-pulse">
                              Current
                            </span>
                          )}
                        </div>
                        <h3 className="font-semibold text-foreground mt-1">{step.title}</h3>
                        {step.description && (
                          <p className="text-sm text-muted-foreground mt-1">{step.description}</p>
                        )}
                        
                        {/* Dates */}
                        <div className="mt-2 flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-muted-foreground">
                          {step.planned_date && (
                            <span className="flex items-center gap-1">
                              <Calendar className="w-3 h-3" />
                              Planned: {step.planned_date}
                            </span>
                          )}
                          {step.completed_at && (
                            <span className="flex items-center gap-1 text-emerald-600">
                              <CheckCircle2 className="w-3 h-3" />
                              Completed: {new Date(step.completed_at).toLocaleDateString('en-GB', { day: 'numeric', month: 'short' })}
                            </span>
                          )}
                        </div>
                        
                        {/* Linked documents */}
                        {step.documents && step.documents.length > 0 && (
                          <div className="mt-3 flex flex-wrap gap-2">
                            {step.documents.map(doc => (
                              <div 
                                key={doc.activity_id}
                                className="flex items-center gap-2 px-2 py-1 bg-muted rounded text-xs"
                              >
                                <FileText className="w-3 h-3 text-muted-foreground" />
                                <span className="truncate max-w-[150px]">{doc.title || doc.file_name}</span>
                                <button
                                  onClick={() => handleUnlinkDocument(step.step_id, doc.activity_id)}
                                  className="text-muted-foreground hover:text-destructive"
                                >
                                  <Unlink className="w-3 h-3" />
                                </button>
                              </div>
                            ))}
                          </div>
                        )}
                        
                        {/* Internal notes */}
                        {step.internal_notes && step.internal_notes.length > 0 && (
                          <div className="mt-3 p-2 bg-amber-500/5 border border-amber-500/20 rounded">
                            <p className="text-[10px] font-medium text-amber-600 uppercase tracking-wider mb-1">
                              Internal Notes
                            </p>
                            {step.internal_notes.map(note => (
                              <p key={note.note_id} className="text-sm text-amber-700">
                                {note.content}
                                <span className="text-xs text-amber-500 ml-2">
                                  — {note.author_name}
                                </span>
                              </p>
                            ))}
                          </div>
                        )}
                      </div>
                      
                      {/* Actions */}
                      <div className="flex w-full items-center justify-end gap-1 border-t border-border/50 pt-2 sm:w-auto sm:flex-shrink-0 sm:border-0 sm:pt-0">
                        <Button
                          variant="ghost"
                          size="icon"
                          className="h-8 w-8"
                          onClick={() => setStepDialog({ open: true, step })}
                          data-testid={`edit-step-${step.step_id}`}
                        >
                          <Pencil className="w-4 h-4" />
                        </Button>
                        <Button
                          variant="ghost"
                          size="icon"
                          className="h-8 w-8"
                          onClick={() => setLinkDialog({ open: true, step })}
                        >
                          <Link2 className="w-4 h-4" />
                        </Button>
                        <Button
                          variant="ghost"
                          size="icon"
                          className="h-8 w-8"
                          onClick={() => setNoteDialog({ open: true, step })}
                        >
                          <MessageSquare className="w-4 h-4" />
                        </Button>
                        <Button
                          variant="ghost"
                          size="icon"
                          className="h-8 w-8 text-muted-foreground hover:text-destructive"
                          onClick={() => handleDeleteStep(step.step_id, step.title)}
                          data-testid={`delete-step-${step.step_id}`}
                        >
                          <Trash2 className="w-4 h-4" />
                        </Button>
                      </div>
                    </div>
                  </CardContent>
                </Card>
              );
            })}
            
            {/* Add Step Button */}
            <Button
              variant="outline"
              className="w-full mt-4 border-dashed"
              onClick={() => setAddStepDialog(true)}
              data-testid="add-step-to-timeline-btn"
            >
              <Plus className="w-4 h-4 mr-2" />
              Add Step
            </Button>
          </div>
        )}
      </div>

      {/* Apply Template Dialog */}
      <Dialog open={templateDialog} onOpenChange={setTemplateDialog}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Apply Timeline Template</DialogTitle>
            <DialogDescription>
              Choose a template to create the project timeline. This will create construction stages based on the template.
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-3 py-4">
            {templates.length === 0 ? (
              <p className="text-sm text-muted-foreground text-center py-4">No templates available</p>
            ) : (
              templates.map(template => (
                <Card 
                  key={template.template_id} 
                  className="border-border cursor-pointer hover:border-primary/50 transition-colors"
                  onClick={() => handleApplyTemplate(template.template_id)}
                >
                  <CardContent className="py-3">
                    <div className="flex items-center justify-between">
                      <div>
                        <h4 className="font-medium">{template.name}</h4>
                        <p className="text-sm text-muted-foreground">
                          {template.steps?.length || 0} stages
                        </p>
                      </div>
                      <ChevronRight className="w-5 h-5 text-muted-foreground" />
                    </div>
                  </CardContent>
                </Card>
              ))
            )}
          </div>
        </DialogContent>
      </Dialog>

      {/* Edit Step Dialog */}
      <StepEditDialog 
        open={stepDialog.open}
        step={stepDialog.step}
        onClose={() => setStepDialog({ open: false, step: null })}
        onSave={handleUpdateStep}
      />

      {/* Link Document Dialog */}
      <LinkDocumentDialog
        open={linkDialog.open}
        step={linkDialog.step}
        activities={activities}
        loading={formLoading}
        onClose={() => setLinkDialog({ open: false, step: null })}
        onLink={handleLinkDocument}
      />

      {/* Add Note Dialog */}
      <AddNoteDialog
        open={noteDialog.open}
        step={noteDialog.step}
        loading={formLoading}
        onClose={() => setNoteDialog({ open: false, step: null })}
        onAdd={handleAddNote}
      />

      {/* Add Step to Existing Timeline Dialog */}
      <Dialog open={addStepDialog} onOpenChange={(open) => {
        setAddStepDialog(open);
        if (!open) setNewStep({ title: '', description: '', planned_date: '' });
      }}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Add New Step</DialogTitle>
            <DialogDescription>
              Add a new step to the timeline. It will be added at the end.
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4 py-4">
            <div className="space-y-2">
              <Label htmlFor="new-step-title">Step Title *</Label>
              <Input
                id="new-step-title"
                placeholder="e.g., Interior Painting, Final Inspection"
                value={newStep.title}
                onChange={(e) => setNewStep({ ...newStep, title: e.target.value })}
                data-testid="new-step-title-input"
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="new-step-description">Description</Label>
              <Textarea
                id="new-step-description"
                placeholder="Optional description..."
                value={newStep.description}
                onChange={(e) => setNewStep({ ...newStep, description: e.target.value })}
                rows={2}
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="new-step-date">Target Date</Label>
              <Input
                id="new-step-date"
                placeholder="e.g., March 2026, Q2 2026"
                value={newStep.planned_date}
                onChange={(e) => setNewStep({ ...newStep, planned_date: e.target.value })}
              />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setAddStepDialog(false)}>
              Cancel
            </Button>
            <Button 
              onClick={handleAddStep} 
              disabled={formLoading || !newStep.title.trim()}
              data-testid="confirm-add-step-btn"
            >
              {formLoading && <Loader2 className="w-4 h-4 animate-spin mr-2" />}
              Add Step
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Manual Timeline Creation Dialog */}
      <Dialog open={manualTimelineDialog} onOpenChange={setManualTimelineDialog}>
        <DialogContent className="sm:max-w-xl max-h-[80vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle>Create Timeline</DialogTitle>
            <DialogDescription>
              Add steps to create a custom project timeline.
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4 py-4">
            {manualSteps.map((step, index) => (
              <div key={step.id || `step-${index}`} className="p-4 border border-border rounded-lg space-y-3">
                <div className="flex items-center justify-between">
                  <span className="text-sm font-medium text-muted-foreground">Step {index + 1}</span>
                  {manualSteps.length > 1 && (
                    <Button 
                      variant="ghost" 
                      size="sm" 
                      onClick={() => removeManualStep(index)}
                      className="h-8 w-8 p-0 text-destructive hover:text-destructive"
                    >
                      <Trash2 className="w-4 h-4" />
                    </Button>
                  )}
                </div>
                <Input
                  placeholder="Step name (e.g., Foundation, Framing, Electrical)"
                  value={step.name}
                  onChange={(e) => updateManualStep(index, 'name', e.target.value)}
                  data-testid={`manual-step-name-${index}`}
                />
                <Textarea
                  placeholder="Description (optional)"
                  value={step.description}
                  onChange={(e) => updateManualStep(index, 'description', e.target.value)}
                  rows={2}
                />
                <Input
                  placeholder="Target date (e.g., March 2026, Q2 2026)"
                  value={step.planned_date}
                  onChange={(e) => updateManualStep(index, 'planned_date', e.target.value)}
                />
              </div>
            ))}
            <Button 
              variant="outline" 
              onClick={addManualStep} 
              className="w-full"
              data-testid="add-step-btn"
            >
              <Plus className="w-4 h-4 mr-2" />
              Add Step
            </Button>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setManualTimelineDialog(false)}>
              Cancel
            </Button>
            <Button 
              onClick={handleCreateManualTimeline} 
              disabled={formLoading || !manualSteps.some(s => s.name.trim())}
              data-testid="create-timeline-btn"
            >
              {formLoading && <Loader2 className="w-4 h-4 animate-spin mr-2" />}
              Create Timeline
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* AI Timeline Extraction Dialog */}
      <Dialog open={aiExtractDialog} onOpenChange={(open) => {
        if (!open) {
          setAiExtractDialog(false);
          setExtractedTimeline(null);
          setEditingPhases([]);
          setExtractFile(null);
        }
      }}>
        <DialogContent className="sm:max-w-2xl max-h-[80vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <Sparkles className="w-5 h-5 text-primary" />
              AI Timeline Extraction
            </DialogTitle>
            <DialogDescription>
              Upload a planning document (PDF, Excel, or image) and AI will extract the project timeline.
            </DialogDescription>
          </DialogHeader>

          {!extractedTimeline ? (
            <div className="space-y-4 py-4">
              {/* File Upload with actual drag & drop */}
              <div 
                className="border-2 border-dashed border-muted-foreground/25 rounded-lg p-6 text-center hover:border-primary/50 transition-colors cursor-pointer"
                onClick={() => document.getElementById('timeline-file-input').click()}
                onDragOver={(e) => {
                  e.preventDefault();
                  e.stopPropagation();
                  e.currentTarget.classList.add('border-primary', 'bg-primary/5');
                }}
                onDragLeave={(e) => {
                  e.preventDefault();
                  e.stopPropagation();
                  e.currentTarget.classList.remove('border-primary', 'bg-primary/5');
                }}
                onDrop={(e) => {
                  e.preventDefault();
                  e.stopPropagation();
                  e.currentTarget.classList.remove('border-primary', 'bg-primary/5');
                  const file = e.dataTransfer.files?.[0];
                  if (file) {
                    const validTypes = ['application/pdf', 'image/png', 'image/jpeg', 'image/jpg', 
                      'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet', 'application/vnd.ms-excel'];
                    if (validTypes.includes(file.type) || file.name.match(/\.(pdf|png|jpg|jpeg|xlsx|xls)$/i)) {
                      setExtractFile(file);
                    } else {
                      toast.error('Please upload a PDF, Excel, or image file');
                    }
                  }
                }}
              >
                <input
                  id="timeline-file-input"
                  type="file"
                  accept=".pdf,.xlsx,.xls,.png,.jpg,.jpeg"
                  className="hidden"
                  onChange={(e) => setExtractFile(e.target.files?.[0] || null)}
                />
                {extractFile ? (
                  <div className="flex items-center justify-center gap-2">
                    <FileText className="w-8 h-8 text-primary" />
                    <div className="text-left">
                      <p className="font-medium">{extractFile.name}</p>
                      <p className="text-xs text-muted-foreground">
                        {(extractFile.size / 1024 / 1024).toFixed(2)} MB
                      </p>
                    </div>
                    <Button 
                      variant="ghost" 
                      size="icon"
                      onClick={(e) => { e.stopPropagation(); setExtractFile(null); }}
                    >
                      <X className="w-4 h-4" />
                    </Button>
                  </div>
                ) : (
                  <>
                    <Upload className="w-10 h-10 text-muted-foreground mx-auto mb-2" />
                    <p className="text-sm text-muted-foreground">
                      Drag & drop or click to upload
                    </p>
                    <p className="text-xs text-muted-foreground mt-1">
                      PDF, Excel, PNG, JPG (max 20MB)
                    </p>
                  </>
                )}
              </div>
              
              <DialogFooter>
                <Button variant="outline" onClick={() => setAiExtractDialog(false)}>
                  Cancel
                </Button>
                <Button onClick={handleExtractTimeline} disabled={!extractFile || extracting}>
                  {extracting ? (
                    <>
                      <Loader2 className="w-4 h-4 animate-spin mr-2" />
                      Extracting...
                    </>
                  ) : (
                    <>
                      <Sparkles className="w-4 h-4 mr-2" />
                      Extract Timeline
                    </>
                  )}
                </Button>
              </DialogFooter>
            </div>
          ) : (
            <div className="space-y-4 py-4">
              {/* Extraction Result */}
              <div className="bg-muted/50 rounded-lg p-4 space-y-2">
                <div className="flex items-center justify-between">
                  <span className="text-sm font-medium">Extraction Confidence:</span>
                  <span className={cn(
                    "text-xs font-semibold px-2 py-1 rounded",
                    extractedTimeline.extracted_data.confidence === 'high' ? 'bg-emerald-100 text-emerald-700' :
                    extractedTimeline.extracted_data.confidence === 'medium' ? 'bg-amber-100 text-amber-700' :
                    'bg-red-100 text-red-700'
                  )}>
                    {extractedTimeline.extracted_data.confidence?.toUpperCase()}
                  </span>
                </div>
                {extractedTimeline.extracted_data.project_duration && (
                  <p className="text-sm text-muted-foreground">
                    Est. Duration: {extractedTimeline.extracted_data.project_duration}
                  </p>
                )}
                {extractedTimeline.extracted_data.notes && (
                  <p className="text-sm text-muted-foreground">
                    {extractedTimeline.extracted_data.notes}
                  </p>
                )}
              </div>

              {/* Editable Phases */}
              <div className="space-y-3">
                <div className="flex items-center justify-between">
                  <Label className="text-base font-medium">Extracted Phases ({editingPhases.length})</Label>
                  <Button variant="outline" size="sm" onClick={addPhase}>
                    <Plus className="w-4 h-4 mr-1" />
                    Add Phase
                  </Button>
                </div>
                
                {editingPhases.map((phase, idx) => (
                  <Card key={phase.name || `phase-${idx}`} className="border-border">
                    <CardContent className="p-3 space-y-2">
                      <div className="flex items-start gap-2">
                        <div className="flex-1 space-y-2">
                          <Input
                            value={phase.name}
                            onChange={(e) => updatePhase(idx, 'name', e.target.value)}
                            placeholder="Phase name"
                            className="font-medium"
                          />
                          <Input
                            value={phase.description || ''}
                            onChange={(e) => updatePhase(idx, 'description', e.target.value)}
                            placeholder="Description"
                            className="text-sm"
                          />
                          <div className="flex flex-col gap-1 sm:flex-row sm:items-center sm:gap-2">
                            <Label className="text-xs text-muted-foreground shrink-0">Date:</Label>
                            <Input
                              value={phase.planned_date || ''}
                              onChange={(e) => updatePhase(idx, 'planned_date', e.target.value)}
                              placeholder="e.g., March 2026, Q2 2027"
                              className="flex-1"
                            />
                          </div>
                        </div>
                        <Button 
                          variant="ghost" 
                          size="icon"
                          onClick={() => removePhase(idx)}
                          className="text-destructive hover:text-destructive"
                        >
                          <Trash2 className="w-4 h-4" />
                        </Button>
                      </div>
                    </CardContent>
                  </Card>
                ))}
              </div>

              <DialogFooter>
                <Button variant="outline" onClick={() => {
                  setExtractedTimeline(null);
                  setEditingPhases([]);
                }}>
                  Back
                </Button>
                <Button onClick={handleApproveTimeline} disabled={formLoading || editingPhases.length === 0}>
                  {formLoading ? (
                    <>
                      <Loader2 className="w-4 h-4 animate-spin mr-2" />
                      Applying...
                    </>
                  ) : (
                    <>
                      <CheckCircle2 className="w-4 h-4 mr-2" />
                      Approve & Apply
                    </>
                  )}
                </Button>
              </DialogFooter>
            </div>
          )}
        </DialogContent>
      </Dialog>
    </AgentLayout>
  );
};

// Step Edit Dialog Component
const StepEditDialog = ({ open, step, onClose, onSave }) => {
  const [title, setTitle] = useState('');
  const [description, setDescription] = useState('');
  const [plannedDate, setPlannedDate] = useState('');
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (step) {
      setTitle(step.title || '');
      setDescription(step.description || '');
      setPlannedDate(step.planned_date || '');
    }
  }, [step]);

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!step) return;
    
    setSaving(true);
    await onSave(step.step_id, { title, description, planned_date: plannedDate || null });
    setSaving(false);
  };

  return (
    <Dialog open={open} onOpenChange={onClose}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Edit Step</DialogTitle>
        </DialogHeader>
        <form onSubmit={handleSubmit}>
          <div className="space-y-4 py-4">
            <div className="space-y-2">
              <Label htmlFor="title">Title</Label>
              <Input
                id="title"
                value={title}
                onChange={(e) => setTitle(e.target.value)}
                required
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="description">Description</Label>
              <Textarea
                id="description"
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                rows={3}
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="plannedDate">Planned Date</Label>
              <Input
                id="plannedDate"
                value={plannedDate}
                onChange={(e) => setPlannedDate(e.target.value)}
                placeholder="e.g., March 2026, Q2 2027, Week 12"
              />
              <p className="text-xs text-muted-foreground">Enter the date as you want it displayed to buyers</p>
            </div>
          </div>
          <DialogFooter>
            <Button type="button" variant="outline" onClick={onClose}>Cancel</Button>
            <Button type="submit" disabled={saving}>
              {saving && <Loader2 className="w-4 h-4 animate-spin mr-2" />}
              Save
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
};

// Link Document Dialog Component
const LinkDocumentDialog = ({ open, step, activities, loading, onClose, onLink }) => {
  const linkedIds = step?.documents?.map(d => d.activity_id) || [];
  const availableActivities = activities.filter(a => !linkedIds.includes(a.activity_id));

  return (
    <Dialog open={open} onOpenChange={onClose}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Link Document</DialogTitle>
          <DialogDescription>
            Select an activity to link to "{step?.title}"
          </DialogDescription>
        </DialogHeader>
        <div className="max-h-64 overflow-y-auto space-y-2 py-4">
          {availableActivities.length === 0 ? (
            <p className="text-sm text-muted-foreground text-center py-4">
              No activities available to link
            </p>
          ) : (
            availableActivities.map(activity => (
              <Card 
                key={activity.activity_id}
                className="border-border cursor-pointer hover:border-primary/50 transition-colors"
                onClick={() => !loading && onLink(step.step_id, activity.activity_id)}
              >
                <CardContent className="py-3">
                  <div className="flex items-center gap-3">
                    <FileText className="w-4 h-4 text-muted-foreground" />
                    <div className="flex-1 min-w-0">
                      <p className="font-medium truncate">{activity.title || activity.file_name || 'Activity'}</p>
                      <p className="text-xs text-muted-foreground">
                        {activity.type} · {new Date(activity.created_at).toLocaleDateString('en-GB', { day: 'numeric', month: 'short' })}
                      </p>
                    </div>
                  </div>
                </CardContent>
              </Card>
            ))
          )}
        </div>
      </DialogContent>
    </Dialog>
  );
};

// Add Note Dialog Component
const AddNoteDialog = ({ open, step, loading, onClose, onAdd }) => {
  const [content, setContent] = useState('');

  const handleSubmit = (e) => {
    e.preventDefault();
    if (!content.trim() || !step) return;
    onAdd(step.step_id, content);
    setContent('');
  };

  return (
    <Dialog open={open} onOpenChange={onClose}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Add Internal Note</DialogTitle>
          <DialogDescription>
            Add an internal note to "{step?.title}". This is only visible to agents.
          </DialogDescription>
        </DialogHeader>
        <form onSubmit={handleSubmit}>
          <div className="py-4">
            <Textarea
              value={content}
              onChange={(e) => setContent(e.target.value)}
              placeholder="Enter your note..."
              rows={4}
              required
            />
          </div>
          <DialogFooter>
            <Button type="button" variant="outline" onClick={onClose}>Cancel</Button>
            <Button type="submit" disabled={loading || !content.trim()}>
              {loading && <Loader2 className="w-4 h-4 animate-spin mr-2" />}
              Add Note
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
};

export default AgentWorkflow;
