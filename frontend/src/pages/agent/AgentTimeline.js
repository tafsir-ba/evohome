import { useState, useEffect, useRef } from 'react';
import { AgentLayout } from '../../components/AgentLayout';
import { Card, CardContent, CardHeader, CardTitle } from '../../components/ui/card';
import { Button } from '../../components/ui/button';
import { Input } from '../../components/ui/input';
import { Textarea } from '../../components/ui/textarea';
import { Label } from '../../components/ui/label';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../../components/ui/select';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter, DialogDescription } from '../../components/ui/dialog';
import { toast } from 'sonner';
import { formatDate } from '../../components/StatusBadge';
import { useDataContext } from '../../context/DataContext';
import {
  HardHat,
  Plus,
  Edit2,
  Trash2,
  Calendar,
  Clock,
  CheckCircle,
  AlertCircle,
  Loader2,
  ChevronUp,
  ChevronDown,
  Building2,
  Upload,
  FileText,
  X,
  AlertTriangle
} from 'lucide-react';

const API = process.env.REACT_APP_BACKEND_URL + '/api';

const getAuthHeaders = () => {
  const token = localStorage.getItem('auth_token');
  return token ? { 'Authorization': `Bearer ${token}` } : {};
};

// Predefined stage templates (max 6-8)
const STAGE_TEMPLATES = [
  { name: 'Permits & Approvals', description: 'Building permits and regulatory approvals' },
  { name: 'Foundation', description: 'Excavation and foundation work' },
  { name: 'Structure', description: 'Structural framework and building envelope' },
  { name: 'MEP Rough-In', description: 'Mechanical, electrical, and plumbing rough-in' },
  { name: 'Interior Finishes', description: 'Drywall, flooring, painting, and trim' },
  { name: 'Final Installations', description: 'Fixtures, appliances, and final connections' },
  { name: 'Quality Inspection', description: 'Final inspections and punch list' },
  { name: 'Handover', description: 'Final walkthrough and key handover' },
];

const stageStatusStyles = {
  pending: { bg: 'bg-gray-100', text: 'text-gray-600', border: 'border-gray-300', icon: Clock },
  in_progress: { bg: 'bg-blue-100', text: 'text-blue-700', border: 'border-blue-400', icon: Loader2 },
  completed: { bg: 'bg-green-100', text: 'text-green-700', border: 'border-green-400', icon: CheckCircle },
  delayed: { bg: 'bg-amber-100', text: 'text-amber-700', border: 'border-amber-400', icon: AlertCircle },
};

const StageCard = ({ stage, onEdit, onDelete, onMove, isFirst, isLast }) => {
  const style = stageStatusStyles[stage.status] || stageStatusStyles.pending;
  const StatusIcon = style.icon;

  return (
    <Card className={`border-l-4 ${style.border} rounded-sm hover:shadow-swiss transition-shadow`} data-testid={`stage-card-${stage.step_id}`}>
      <CardContent className="p-4">
        <div className="flex items-start justify-between gap-4">
          <div className="flex items-start gap-3 flex-1 min-w-0">
            <div className={`w-10 h-10 rounded-sm flex items-center justify-center flex-shrink-0 ${style.bg}`}>
              <StatusIcon className={`w-5 h-5 ${style.text} ${stage.status === 'in_progress' ? 'animate-spin' : ''}`} />
            </div>
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-2">
                <h3 className="font-medium text-[#1A1A1A] truncate">{stage.title}</h3>
                <span className={`px-2 py-0.5 text-[10px] font-medium rounded-sm uppercase ${style.bg} ${style.text}`}>
                  {stage.status.replace('_', ' ')}
                </span>
              </div>
              {stage.description && (
                <p className="text-sm text-muted-foreground mt-1 line-clamp-1">{stage.description}</p>
              )}
              <div className="flex items-center gap-4 mt-2 text-xs text-muted-foreground">
                <span className="flex items-center gap-1">
                  <Calendar className="w-3 h-3" />
                  {formatDate(stage.planned_start)} - {formatDate(stage.planned_end)}
                </span>
                {stage.progress_percent > 0 && (
                  <span className="flex items-center gap-1">
                    Progress: {stage.progress_percent}%
                  </span>
                )}
              </div>
              {stage.notes && (
                <p className="text-xs text-muted-foreground mt-2 bg-[#F8FAFB] p-2 rounded-sm line-clamp-2">
                  {stage.notes}
                </p>
              )}
            </div>
          </div>

          <div className="flex items-center gap-1 flex-shrink-0">
            {/* Reorder Buttons */}
            <div className="flex flex-col mr-2">
              <Button
                variant="ghost"
                size="icon"
                className="h-6 w-6"
                onClick={() => onMove(stage, 'up')}
                disabled={isFirst}
                data-testid={`move-up-${stage.step_id}`}
              >
                <ChevronUp className="w-4 h-4" />
              </Button>
              <Button
                variant="ghost"
                size="icon"
                className="h-6 w-6"
                onClick={() => onMove(stage, 'down')}
                disabled={isLast}
                data-testid={`move-down-${stage.step_id}`}
              >
                <ChevronDown className="w-4 h-4" />
              </Button>
            </div>
            <Button
              variant="ghost"
              size="icon"
              className="h-8 w-8 text-[#64748B] hover:text-primary"
              onClick={() => onEdit(stage)}
              data-testid={`edit-stage-${stage.step_id}`}
            >
              <Edit2 className="w-4 h-4" />
            </Button>
            <Button
              variant="ghost"
              size="icon"
              className="h-8 w-8 text-muted-foreground hover:text-destructive"
              onClick={() => onDelete(stage)}
              data-testid={`delete-stage-${stage.step_id}`}
            >
              <Trash2 className="w-4 h-4" />
            </Button>
          </div>
        </div>
      </CardContent>
    </Card>
  );
};

export const AgentTimeline = () => {
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
  
  const [stages, setStages] = useState([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  
  // Upload/extraction state - separate from published timeline
  const fileInputRef = useRef(null);
  const [uploadDialogOpen, setUploadDialogOpen] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [extractedStages, setExtractedStages] = useState([]);
  const [uploadFile, setUploadFile] = useState(null);
  const [extractionConfidence, setExtractionConfidence] = useState(0);
  
  // Existing timeline warning
  const [existingTimelineWarning, setExistingTimelineWarning] = useState(false);

  // Dialog state
  const [dialogOpen, setDialogOpen] = useState(false);
  const [editingStage, setEditingStage] = useState(null);
  const [formData, setFormData] = useState({
    title: '',
    description: '',
    planned_start: '',
    planned_end: '',
    actual_start: '',
    actual_end: '',
    status: 'pending',
    progress_percent: 0,
    notes: '',
  });

  // Track current project to avoid unnecessary clears
  const lastProjectRef = useRef(null);
  const fetchingRef = useRef(false);

  // On project change, fetch timeline from canonical endpoint
  // selectedProjectId comes from DataContext - single source of truth
  useEffect(() => {
    // Skip if already fetching
    if (fetchingRef.current) return;
    
    // Skip if project hasn't actually changed AND we have data
    if (lastProjectRef.current === selectedProjectId && lastProjectRef.current !== null) {
      // Make sure loading is false since we're skipping fetch
      setLoading(false);
      return;
    }
    
    // Cancel any pending fetch
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
    }
    
    // Only clear state if switching to a DIFFERENT project (not initial load)
    if (lastProjectRef.current !== null && lastProjectRef.current !== selectedProjectId) {
      setStages([]);
      setExtractedStages([]);
      setExistingTimelineWarning(false);
    }
    
    lastProjectRef.current = selectedProjectId;
    
    if (selectedProjectId) {
      fetchingRef.current = true;
      fetchTimeline(selectedProjectId).finally(() => {
        fetchingRef.current = false;
      });
    } else {
      setStages([]);
      setLoading(false);
    }
    
    return () => {
      if (abortControllerRef.current) {
        abortControllerRef.current.abort();
      }
    };
  }, [selectedProjectId]);

  // Single canonical fetch for timeline data
  // Backend is source of truth. No fallbacks.
  const fetchTimeline = async (projectId) => {
    // Create new abort controller for this request
    abortControllerRef.current = new AbortController();
    const fetchId = Date.now();
    currentFetchRef.current = fetchId;
    
    setLoading(true);
    
    try {
      const res = await fetch(`${API}/projects/${projectId}/timeline/full`, { 
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
          const mappedSteps = (data.steps || []).map(step => ({
            step_id: step.step_id,
            title: step.title,
            description: step.description,
            status: step.status || 'pending',
            order_index: step.order_index,
            planned_start: step.planned_start,
            planned_end: step.planned_end,
            progress_percent: step.progress_percent || 0
          }));
          setStages(mappedSteps);
        }
      }
    } catch (error) {
      if (error.name === 'AbortError') return;
      console.error('Failed to fetch timeline:', error);
      toast.error('Failed to load timeline');
    } finally {
      if (currentFetchRef.current === fetchId) {
        setLoading(false);
      }
    }
  };

  // No longer needed — backend returns canonical statuses directly

  const handleOpenCreate = () => {
    setEditingStage(null);
    setFormData({
      title: '',
      description: '',
      planned_start: '',
      planned_end: '',
      actual_start: '',
      actual_end: '',
      status: 'pending',
      progress_percent: 0,
      notes: '',
    });
    setDialogOpen(true);
  };

  const handleOpenEdit = (stage) => {
    setEditingStage(stage);
    setFormData({
      title: stage.title,
      description: stage.description || '',
      planned_start: stage.planned_start || '',
      planned_end: stage.planned_end || '',
      actual_start: stage.actual_start || '',
      actual_end: stage.actual_end || '',
      status: stage.status,
      progress_percent: stage.progress_percent || 0,
      notes: stage.notes || '',
    });
    setDialogOpen(true);
  };

  const handleSelectTemplate = (template) => {
    setFormData(prev => ({
      ...prev,
      title: template.name,
      description: template.description,
    }));
  };

  const handleSave = async () => {
    if (!formData.title || !formData.planned_start || !formData.planned_end) {
      toast.error('Please fill in required fields');
      return;
    }

    setSaving(true);
    try {
      if (editingStage) {
        // Update
        const res = await fetch(
          `${API}/projects/${selectedProjectId}/steps/${editingStage.step_id}`,
          {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json', ...getAuthHeaders() },
            credentials: 'include',
            body: JSON.stringify(formData),
          }
        );
        if (res.ok) {
          toast.success('Stage updated');
          fetchTimeline(selectedProjectId);
        } else {
          throw new Error('Failed to update');
        }
      } else {
        // Create
        const res = await fetch(
          `${API}/projects/${selectedProjectId}/steps`,
          {
            method: 'POST',
            headers: { 'Content-Type': 'application/json', ...getAuthHeaders() },
            credentials: 'include',
            body: JSON.stringify({
              ...formData,
              order_index: stages.length + 1,
            }),
          }
        );
        if (res.ok) {
          toast.success('Stage created');
          fetchTimeline(selectedProjectId);
        } else {
          throw new Error('Failed to create');
        }
      }
      setDialogOpen(false);
    } catch (error) {
      console.error('Save error:', error);
      toast.error('Failed to save stage');
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async (stage) => {
    if (!window.confirm(`Delete "${stage.title}"?`)) return;

    try {
      const res = await fetch(
        `${API}/projects/${selectedProjectId}/steps/${stage.step_id}`,
        { method: 'DELETE', credentials: 'include' }
      );
      if (res.ok) {
        toast.success('Stage deleted');
        fetchTimeline(selectedProjectId);
      } else {
        throw new Error('Failed to delete');
      }
    } catch (error) {
      console.error('Delete error:', error);
      toast.error('Failed to delete stage');
    }
  };

  const handleMove = async (stage, direction) => {
    const currentIndex = stages.findIndex(s => s.step_id === stage.step_id);
    const newIndex = direction === 'up' ? currentIndex - 1 : currentIndex + 1;
    
    if (newIndex < 0 || newIndex >= stages.length) return;

    const otherStage = stages[newIndex];
    
    try {
      // Swap orders
      await Promise.all([
        fetch(`${API}/projects/${selectedProjectId}/steps/${stage.step_id}`, {
          method: 'PUT',
          headers: { 'Content-Type': 'application/json', ...getAuthHeaders() },
          credentials: 'include',
          body: JSON.stringify({ order_index: otherStage.order_index }),
        }),
        fetch(`${API}/projects/${selectedProjectId}/steps/${otherStage.step_id}`, {
          method: 'PUT',
          headers: { 'Content-Type': 'application/json', ...getAuthHeaders() },
          credentials: 'include',
          body: JSON.stringify({ order_index: stage.order_index }),
        }),
      ]);
      fetchTimeline(selectedProjectId);
    } catch (error) {
      console.error('Move error:', error);
      toast.error('Failed to reorder stages');
    }
  };

  // Handle timeline upload
  const handleUploadClick = () => {
    // Check if stages already exist
    if (stages.length > 0) {
      setExistingTimelineWarning(true);
      return;
    }
    fileInputRef.current?.click();
  };

  const handleFileSelect = async (e) => {
    const file = e.target.files?.[0];
    if (!file) return;
    
    if (!file.name.toLowerCase().endsWith('.pdf')) {
      toast.error('Only PDF files are supported');
      return;
    }
    
    setUploadFile(file);
    setUploading(true);
    setExtractedStages([]);
    setUploadDialogOpen(true);
    
    try {
      // Step 1: Upload and classify
      const classifyFormData = new FormData();
      classifyFormData.append('file', file);
      
      const classifyRes = await fetch(`${API}/command/classify-document`, {
        method: 'POST',
        credentials: 'include',
        headers: getAuthHeaders(),
        body: classifyFormData
      });
      
      if (!classifyRes.ok) {
        throw new Error('Failed to process document');
      }
      
      const classification = await classifyRes.json();
      
      // Step 2: Extract timeline data
      const extractFormData = new FormData();
      extractFormData.append('file_path', classification.file_path);
      extractFormData.append('document_type', 'timeline');
      extractFormData.append('context', JSON.stringify({
        project_id: selectedProjectId
      }));
      
      const extractRes = await fetch(`${API}/command/extract-document`, {
        method: 'POST',
        credentials: 'include',
        headers: getAuthHeaders(),
        body: extractFormData
      });
      
      if (!extractRes.ok) {
        throw new Error('Failed to extract timeline');
      }
      
      const extractedData = await extractRes.json();
      
      // Check if timeline already exists (backend check)
      if (extractedData.timeline_exists) {
        setUploading(false);
        setUploadDialogOpen(false);
        toast.warning(`This project already has a timeline: "${extractedData.existing_timeline?.name}"`);
        return;
      }
      
      // Parse extracted steps
      const stagesField = extractedData.fields?.find(f => f.name === 'stages');
      if (stagesField && Array.isArray(stagesField.value)) {
        // Convert extracted steps to canonical format
        const parsedStages = stagesField.value.map((stage, index) => ({
          title: stage.title || `Step ${index + 1}`,
          description: stage.description || '',
          date_text: stage.date_text || stage.date || '',
          status: 'pending',
          order_index: index + 1
        }));
        setExtractedStages(parsedStages);
        setExtractionConfidence(extractedData.confidence || 0.5);
        toast.success(`Extracted ${parsedStages.length} steps from document`);
      } else {
        setExtractedStages([]);
        toast.warning('Could not extract timeline steps. Please add them manually.');
      }
      
    } catch (error) {
      console.error('Upload error:', error);
      toast.error(error.message || 'Failed to process timeline document');
      setUploadDialogOpen(false);
    } finally {
      setUploading(false);
      if (fileInputRef.current) {
        fileInputRef.current.value = '';
      }
    }
  };

  const handleSaveExtractedStages = async () => {
    if (extractedStages.length === 0) {
      toast.error('No steps to save');
      return;
    }
    
    setSaving(true);
    try {
      // Get the current max order to continue numbering from
      const maxOrder = stages.length > 0 
        ? Math.max(...stages.map(s => s.order_index || 0)) 
        : 0;
      
      // Create each step
      for (let i = 0; i < extractedStages.length; i++) {
        const stage = extractedStages[i];
        // Parse date_text into planned_start and planned_end
        const today = new Date();
        const startDate = today.toISOString().split('T')[0];
        const endDate = new Date(today.setMonth(today.getMonth() + 1)).toISOString().split('T')[0];
        
        const res = await fetch(`${API}/projects/${selectedProjectId}/steps`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json', ...getAuthHeaders() },
          credentials: 'include',
          body: JSON.stringify({
            title: stage.title,
            description: stage.description || stage.date_text || '',
            planned_start: startDate,
            planned_end: endDate,
            status: stage.status || 'pending',
            order_index: maxOrder + i + 1,
            notes: stage.date_text ? `Original date: ${stage.date_text}` : ''
          })
        });
        
        if (!res.ok) {
          throw new Error(`Failed to create step: ${stage.title}`);
        }
      }
      
      const actionWord = stages.length > 0 ? 'Added' : 'Created';
      toast.success(`${actionWord} ${extractedStages.length} steps`);
      setUploadDialogOpen(false);
      setExtractedStages([]);
      fetchTimeline(selectedProjectId);
    } catch (error) {
      console.error('Save error:', error);
      toast.error(error.message || 'Failed to save stages');
    } finally {
      setSaving(false);
    }
  };

  const handleRemoveExtractedStage = (index) => {
    setExtractedStages(prev => prev.filter((_, i) => i !== index));
  };

  const handleEditExtractedStage = (index, field, value) => {
    setExtractedStages(prev => prev.map((stage, i) => 
      i === index ? { ...stage, [field]: value } : stage
    ));
  };

  const handleReplaceTimeline = async () => {
    // Delete all existing stages first
    setExistingTimelineWarning(false);
    setSaving(true);
    
    try {
      for (const stage of stages) {
        await fetch(`${API}/projects/${selectedProjectId}/steps/${stage.step_id}`, {
          method: 'DELETE',
          credentials: 'include'
        });
      }
      setStages([]);
      toast.success('Existing timeline cleared');
      
      // Now trigger the file upload
      fileInputRef.current?.click();
    } catch (error) {
      console.error('Delete error:', error);
      toast.error('Failed to clear existing timeline');
    } finally {
      setSaving(false);
    }
  };

  // Update mode: Keep existing stages and add new ones from the uploaded document
  const handleUpdateTimeline = () => {
    setExistingTimelineWarning(false);
    // Just trigger file upload - when saving, new stages will be added to existing ones
    fileInputRef.current?.click();
  };

  const currentProject = selectedProject;

  if (loading) {
    return (
      <AgentLayout>
        <div className="animate-pulse space-y-6">
          <div className="h-8 w-48 bg-gray-200 rounded" />
          <div className="space-y-4">
            {[1, 2, 3].map(i => (
              <div key={i} className="h-24 bg-gray-200 rounded-sm" />
            ))}
          </div>
        </div>
      </AgentLayout>
    );
  }

  return (
    <AgentLayout>
      <div className="space-y-6" data-testid="agent-timeline">
        {/* Hidden file input */}
        <input
          ref={fileInputRef}
          type="file"
          accept=".pdf,application/pdf"
          className="hidden"
          onChange={handleFileSelect}
        />
        
        {/* Header */}
        <div className="flex items-start justify-between">
          <div>
            <h1 className="text-3xl font-outfit font-semibold text-[#1A1A1A] tracking-tight">
              Project Timeline
            </h1>
            <p className="text-muted-foreground mt-1">Manage construction stages for your projects</p>
          </div>
          {selectedProjectId && (
            <div className="flex gap-2">
              <Button 
                variant="outline"
                className="rounded-sm"
                onClick={handleUploadClick}
                disabled={uploading}
                data-testid="upload-timeline-btn"
              >
                {uploading ? (
                  <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                ) : (
                  <Upload className="w-4 h-4 mr-2" />
                )}
                Upload Timeline
              </Button>
              {stages.length < 8 && (
                <Button 
                  className="bg-primary hover:bg-primary/90 rounded-sm"
                  onClick={handleOpenCreate}
                  data-testid="add-stage-btn"
                >
                  <Plus className="w-4 h-4 mr-2" />
                  Add Stage
                </Button>
              )}
            </div>
          )}
        </div>

        {/* Project Selector */}
        {projects.length > 0 ? (
          <Card className="border-[#E2E8F0] rounded-sm">
            <CardContent className="p-4">
              <div className="flex items-center gap-4">
                <Label className="text-sm font-medium whitespace-nowrap">Select Project:</Label>
                <Select value={selectedProjectId} onValueChange={setSelectedProjectId}>
                  <SelectTrigger className="w-full max-w-md" data-testid="project-selector">
                    <SelectValue placeholder="Select a project" />
                  </SelectTrigger>
                  <SelectContent>
                    {projects.map((project) => (
                      <SelectItem key={project.project_id} value={project.project_id}>
                        {project.name}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              {currentProject && (
                <p className="text-sm text-muted-foreground mt-2">{currentProject.address}</p>
              )}
            </CardContent>
          </Card>
        ) : (
          <Card className="border-[#E2E8F0] rounded-sm">
            <CardContent className="p-8 text-center">
              <Building2 className="w-12 h-12 text-muted-foreground/30 mx-auto mb-3" />
              <p className="text-muted-foreground">No projects found</p>
              <p className="text-xs text-muted-foreground mt-1">Create a project first to manage its timeline</p>
            </CardContent>
          </Card>
        )}

        {/* Stages List */}
        {selectedProjectId && (
          <div className="space-y-4">
            {stages.length > 0 ? (
              stages.map((stage, index) => (
                <StageCard
                  key={stage.step_id}
                  stage={stage}
                  onEdit={handleOpenEdit}
                  onDelete={handleDelete}
                  onMove={handleMove}
                  isFirst={index === 0}
                  isLast={index === stages.length - 1}
                />
              ))
            ) : (
              <Card className="border-[#E2E8F0] rounded-sm">
                <CardContent className="p-8 text-center">
                  <HardHat className="w-12 h-12 text-muted-foreground/30 mx-auto mb-3" />
                  <p className="text-muted-foreground">No stages defined yet</p>
                  <p className="text-xs text-muted-foreground mt-1">Add construction stages to track project progress</p>
                  <Button 
                    className="mt-4 bg-primary hover:bg-primary/90 rounded-sm"
                    onClick={handleOpenCreate}
                  >
                    <Plus className="w-4 h-4 mr-2" />
                    Add First Stage
                  </Button>
                </CardContent>
              </Card>
            )}

            {stages.length > 0 && stages.length < 8 && (
              <p className="text-xs text-muted-foreground text-center">
                {8 - stages.length} more stage{8 - stages.length !== 1 ? 's' : ''} can be added (max 8)
              </p>
            )}
          </div>
        )}
      </div>

      {/* Create/Edit Dialog */}
      <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
        <DialogContent className="max-w-lg">
          <DialogHeader>
            <DialogTitle className="font-outfit">
              {editingStage ? 'Edit Stage' : 'Add Stage'}
            </DialogTitle>
          </DialogHeader>

          <div className="space-y-4 py-4">
            {/* Template Selector (only for new stages) */}
            {!editingStage && (
              <div>
                <Label className="text-xs text-muted-foreground">Quick Templates</Label>
                <div className="flex flex-wrap gap-1 mt-1">
                  {STAGE_TEMPLATES.filter(t => !stages.some(s => s.title === t.name)).slice(0, 4).map((template) => (
                    <Button
                      key={template.name}
                      variant="outline"
                      size="sm"
                      className="text-xs h-7"
                      onClick={() => handleSelectTemplate(template)}
                    >
                      {template.name}
                    </Button>
                  ))}
                </div>
              </div>
            )}

            <div className="grid grid-cols-2 gap-4">
              <div className="col-span-2">
                <Label htmlFor="name">Stage Name *</Label>
                <Input
                  id="name"
                  value={formData.title}
                  onChange={(e) => setFormData(prev => ({ ...prev, title: e.target.value }))}
                  placeholder="e.g., Foundation"
                  className="mt-1"
                  data-testid="stage-name-input"
                />
              </div>

              <div className="col-span-2">
                <Label htmlFor="description">Description</Label>
                <Textarea
                  id="description"
                  value={formData.description}
                  onChange={(e) => setFormData(prev => ({ ...prev, description: e.target.value }))}
                  placeholder="Brief description of this stage"
                  className="mt-1"
                  rows={2}
                />
              </div>

              <div>
                <Label htmlFor="planned_start">Planned Start *</Label>
                <Input
                  id="planned_start"
                  type="date"
                  value={formData.planned_start}
                  onChange={(e) => setFormData(prev => ({ ...prev, planned_start: e.target.value }))}
                  className="mt-1"
                  data-testid="planned-start-input"
                />
              </div>

              <div>
                <Label htmlFor="planned_end">Planned End *</Label>
                <Input
                  id="planned_end"
                  type="date"
                  value={formData.planned_end}
                  onChange={(e) => setFormData(prev => ({ ...prev, planned_end: e.target.value }))}
                  className="mt-1"
                  data-testid="planned-end-input"
                />
              </div>

              {editingStage && (
                <>
                  <div>
                    <Label htmlFor="actual_start">Actual Start</Label>
                    <Input
                      id="actual_start"
                      type="date"
                      value={formData.actual_start}
                      onChange={(e) => setFormData(prev => ({ ...prev, actual_start: e.target.value }))}
                      className="mt-1"
                    />
                  </div>

                  <div>
                    <Label htmlFor="actual_end">Actual End</Label>
                    <Input
                      id="actual_end"
                      type="date"
                      value={formData.actual_end}
                      onChange={(e) => setFormData(prev => ({ ...prev, actual_end: e.target.value }))}
                      className="mt-1"
                    />
                  </div>
                </>
              )}

              <div>
                <Label htmlFor="status">Status</Label>
                <Select 
                  value={formData.status} 
                  onValueChange={(value) => setFormData(prev => ({ ...prev, status: value }))}
                >
                  <SelectTrigger className="mt-1" data-testid="status-select">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="pending">Pending</SelectItem>
                    <SelectItem value="in_progress">In Progress</SelectItem>
                    <SelectItem value="completed">Completed</SelectItem>
                    <SelectItem value="delayed">Delayed</SelectItem>
                  </SelectContent>
                </Select>
              </div>

              <div>
                <Label htmlFor="progress_percent">Progress %</Label>
                <Input
                  id="progress_percent"
                  type="number"
                  min="0"
                  max="100"
                  value={formData.progress_percent}
                  onChange={(e) => setFormData(prev => ({ ...prev, progress_percent: parseInt(e.target.value) || 0 }))}
                  className="mt-1"
                />
              </div>

              <div className="col-span-2">
                <Label htmlFor="notes">Notes</Label>
                <Textarea
                  id="notes"
                  value={formData.notes}
                  onChange={(e) => setFormData(prev => ({ ...prev, notes: e.target.value }))}
                  placeholder="Additional notes for buyers"
                  className="mt-1"
                  rows={2}
                />
              </div>
            </div>
          </div>

          <DialogFooter>
            <Button variant="outline" onClick={() => setDialogOpen(false)}>
              Cancel
            </Button>
            <Button 
              className="bg-primary hover:bg-primary/90"
              onClick={handleSave}
              disabled={saving}
              data-testid="save-stage-btn"
            >
              {saving ? (
                <>
                  <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                  Saving...
                </>
              ) : (
                editingStage ? 'Update Stage' : 'Add Stage'
              )}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Existing Timeline Warning Dialog */}
      <Dialog open={existingTimelineWarning} onOpenChange={setExistingTimelineWarning}>
        <DialogContent className="max-w-md">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2 text-amber-600">
              <AlertTriangle className="w-5 h-5" />
              Timeline Already Exists
            </DialogTitle>
            <DialogDescription>
              This project already has {stages.length} stage{stages.length !== 1 ? 's' : ''} defined. 
              What would you like to do?
            </DialogDescription>
          </DialogHeader>
          
          <div className="space-y-2 py-4">
            <p className="text-sm text-muted-foreground">
              Current stages:
            </p>
            <div className="max-h-32 overflow-y-auto space-y-1">
              {stages.map((stage, i) => (
                <div key={stage.step_id} className="text-sm flex items-center gap-2">
                  <span className="w-5 h-5 rounded-full bg-muted flex items-center justify-center text-xs">{i + 1}</span>
                  {stage.title}
                </div>
              ))}
            </div>
          </div>
          
          <DialogFooter className="flex-col sm:flex-row gap-2">
            <Button 
              variant="outline" 
              onClick={() => setExistingTimelineWarning(false)}
              className="flex-1"
              data-testid="cancel-upload-btn"
            >
              Cancel
            </Button>
            <Button 
              variant="outline"
              onClick={handleUpdateTimeline}
              disabled={saving}
              className="flex-1 border-primary text-primary hover:bg-primary/10"
              data-testid="update-timeline-btn"
            >
              <Plus className="w-4 h-4 mr-2" />
              Update (Add New)
            </Button>
            <Button 
              variant="destructive"
              onClick={handleReplaceTimeline}
              disabled={saving}
              className="flex-1"
              data-testid="replace-timeline-btn"
            >
              {saving ? <Loader2 className="w-4 h-4 animate-spin mr-2" /> : null}
              Replace All
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Upload Preview Dialog */}
      <Dialog open={uploadDialogOpen} onOpenChange={setUploadDialogOpen}>
        <DialogContent className="max-w-2xl max-h-[80vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <FileText className="w-5 h-5" />
              {uploading ? 'Extracting Timeline...' : 'Review Extracted Stages'}
            </DialogTitle>
            {uploadFile && (
              <DialogDescription>
                From: {uploadFile.name}
                {extractionConfidence > 0 && (
                  <span className={`ml-2 px-2 py-0.5 text-xs rounded ${
                    extractionConfidence > 0.7 ? 'bg-green-100 text-green-700' :
                    extractionConfidence > 0.4 ? 'bg-amber-100 text-amber-700' :
                    'bg-red-100 text-red-700'
                  }`}>
                    {Math.round(extractionConfidence * 100)}% confidence
                  </span>
                )}
              </DialogDescription>
            )}
          </DialogHeader>
          
          {uploading ? (
            <div className="py-12 text-center">
              <Loader2 className="w-8 h-8 animate-spin mx-auto text-primary" />
              <p className="mt-4 text-muted-foreground">Analyzing document with AI...</p>
              <p className="text-xs text-muted-foreground mt-1">Extracting timeline stages and dates</p>
            </div>
          ) : extractedStages.length > 0 ? (
            <div className="space-y-4 py-4">
              <p className="text-sm text-muted-foreground">
                Review and edit the extracted stages below. You can remove or modify them before saving.
              </p>
              
              <div className="space-y-3">
                {extractedStages.map((stage, index) => (
                  <div key={stage.title || `stage-${index}`} className="p-3 border rounded-lg bg-card">
                    <div className="flex items-start justify-between gap-3">
                      <div className="flex-1 space-y-2">
                        <Input
                          value={stage.title}
                          onChange={(e) => handleEditExtractedStage(index, 'title', e.target.value)}
                          placeholder="Step title"
                          className="font-medium"
                        />
                        <div className="grid grid-cols-2 gap-2">
                          <Input
                            value={stage.date_text || ''}
                            onChange={(e) => handleEditExtractedStage(index, 'date_text', e.target.value)}
                            placeholder="Date/Period"
                            className="text-sm"
                          />
                          <Select
                            value={stage.status}
                            onValueChange={(value) => handleEditExtractedStage(index, 'status', value)}
                          >
                            <SelectTrigger className="text-sm">
                              <SelectValue />
                            </SelectTrigger>
                            <SelectContent>
                              <SelectItem value="pending">Pending</SelectItem>
                              <SelectItem value="in_progress">In Progress</SelectItem>
                              <SelectItem value="completed">Completed</SelectItem>
                            </SelectContent>
                          </Select>
                        </div>
                        {stage.description && (
                          <Input
                            value={stage.description}
                            onChange={(e) => handleEditExtractedStage(index, 'description', e.target.value)}
                            placeholder="Description"
                            className="text-sm"
                          />
                        )}
                      </div>
                      <Button
                        variant="ghost"
                        size="icon"
                        className="text-muted-foreground hover:text-destructive"
                        onClick={() => handleRemoveExtractedStage(index)}
                      >
                        <X className="w-4 h-4" />
                      </Button>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          ) : (
            <div className="py-8 text-center">
              <AlertCircle className="w-8 h-8 text-muted-foreground mx-auto" />
              <p className="mt-2 text-muted-foreground">No stages could be extracted</p>
              <p className="text-xs text-muted-foreground">Try uploading a different document or add stages manually</p>
            </div>
          )}
          
          <DialogFooter>
            <Button variant="outline" onClick={() => setUploadDialogOpen(false)}>
              Cancel
            </Button>
            {extractedStages.length > 0 && (
              <Button 
                className="bg-primary hover:bg-primary/90"
                onClick={handleSaveExtractedStages}
                disabled={saving}
              >
                {saving ? (
                  <>
                    <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                    Saving...
                  </>
                ) : (
                  <>
                    <CheckCircle className="w-4 h-4 mr-2" />
                    Save {extractedStages.length} Stages
                  </>
                )}
              </Button>
            )}
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </AgentLayout>
  );
};
