import { useState, useEffect, useCallback } from 'react';
import { useAuth } from '../../context/AuthContext';
import { Button } from '../../components/ui/button';
import { Input } from '../../components/ui/input';
import { GanttProjectList } from '../../components/gantt/GanttProjectList';
import { GanttTaskTable } from '../../components/gantt/GanttTaskTable';
import { GanttPlanningCockpit } from '../../components/gantt/GanttPlanningCockpit';
import { GanttAddPhaseDialog } from '../../components/gantt/GanttAddPhaseDialog';
import { GanttImportReview } from '../../components/gantt/GanttImportReview';
import { GanttSaveIndicator } from '../../components/gantt/GanttSaveIndicator';
import { ThemeToggle } from '../../components/ThemeToggle';
import { toast } from 'sonner';
import {
  Download,
  LogOut,
  Loader2,
  Upload,
  LogIn,
  Plus,
  Diamond,
  Layers,
  Table2,
  Maximize2,
  ChevronDown,
} from 'lucide-react';
import { Link, Navigate } from 'react-router-dom';
import { getApiBaseUrl } from '../../lib/api';
import { getGanttHeaders, parseApiError } from '../../components/gantt/ganttApiUtils';
import { GANTT_APP_NAME } from '../../components/gantt/ganttHostUtils';
import { useGanttBranding } from '../../components/gantt/ganttBrandingUtils';
import { GanttLogo } from '../../components/gantt/GanttLogo';
import { ZOOM_LEVELS } from '../../components/gantt/ganttCockpitUtils';
import { formatIsoDate } from '../../components/gantt/ganttTimelineUtils';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '../../components/ui/select';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '../../components/ui/dropdown-menu';

export const GanttChartTool = () => {
  const { user, logout, loading: authLoading } = useAuth();
  const [projects, setProjects] = useState([]);
  const [selectedId, setSelectedId] = useState(null);
  const [tasks, setTasks] = useState([]);
  const [loadingProjects, setLoadingProjects] = useState(true);
  const [loadingTasks, setLoadingTasks] = useState(false);
  const [editingTitle, setEditingTitle] = useState(false);
  const [titleDraft, setTitleDraft] = useState('');
  const [ganttConfig, setGanttConfig] = useState({
    app_name: GANTT_APP_NAME,
    task_statuses: ['not_started', 'in_progress', 'completed', 'blocked'],
    task_types: ['task', 'milestone'],
    dependency_types: ['finish_to_start'],
    import: {
      allowed_extensions: ['.csv', '.jpeg', '.jpg', '.pdf', '.png', '.webp', '.xlsx'],
      max_size_mb: 15,
      low_confidence_threshold: 0.6,
      review_message: '',
      extraction_model: 'gpt-5.4',
    },
  });
  const [showImport, setShowImport] = useState(false);
  const [saveStatus, setSaveStatus] = useState({ saving: false, dirty: false });
  const [chartSaving, setChartSaving] = useState(false);
  const [viewMode, setViewMode] = useState('cockpit');
  const [zoom, setZoom] = useState('Week');
  const [fitToScreen, setFitToScreen] = useState(false);
  const [showAddPhase, setShowAddPhase] = useState(false);

  const apiFetch = useCallback(async (path, options = {}) => {
    const { headers: optionHeaders, ...rest } = options;
    const mergedHeaders = getGanttHeaders(optionHeaders || {});
    if (rest.body instanceof FormData) {
      delete mergedHeaders['Content-Type'];
    }
    const res = await fetch(`${getApiBaseUrl()}${path}`, {
      credentials: 'include',
      headers: mergedHeaders,
      ...rest,
    });
    if (res.status === 401) {
      toast.error('Session expired. Please sign in again.');
      logout();
    }
    return res;
  }, [logout]);

  const fetchProjects = useCallback(async () => {
    try {
      const res = await apiFetch('/gantt/projects');
      if (!res.ok) throw new Error('Failed to load projects');
      setProjects(await res.json());
    } catch (error) {
      toast.error(error.message);
    } finally {
      setLoadingProjects(false);
    }
  }, [apiFetch]);

  const fetchTasks = useCallback(async (projectId) => {
    if (!projectId) {
      setTasks([]);
      return;
    }
    setLoadingTasks(true);
    try {
      const res = await apiFetch(`/gantt/projects/${projectId}/tasks`);
      if (!res.ok) throw new Error('Failed to load tasks');
      setTasks(await res.json());
    } catch (error) {
      toast.error(error.message);
    } finally {
      setLoadingTasks(false);
    }
  }, [apiFetch]);

  const fetchConfig = useCallback(async () => {
    try {
      const res = await apiFetch('/gantt/config');
      if (res.ok) setGanttConfig(await res.json());
    } catch {
      // Backend validation remains authoritative.
    }
  }, [apiFetch]);

  useEffect(() => {
    if (!user) {
      setLoadingProjects(false);
      return;
    }
    fetchProjects();
    fetchConfig();
  }, [fetchProjects, fetchConfig, user]);

  const appName = ganttConfig.app_name || GANTT_APP_NAME;
  useGanttBranding(appName);

  useEffect(() => {
    if (!user) return;
    fetchTasks(selectedId);
    setShowImport(false);
    setSaveStatus({ saving: false, dirty: false });
    setEditingTitle(false);
    setTitleDraft('');
    setViewMode('cockpit');
  }, [selectedId, fetchTasks, user]);

  if (authLoading) {
    return (
      <div className="h-screen flex items-center justify-center bg-background">
        <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
      </div>
    );
  }

  if (!user) {
    return <Navigate to="/login" replace />;
  }

  const selectedProject = projects.find((p) => p.gantt_project_id === selectedId);

  const titleDirty =
    editingTitle && selectedProject && titleDraft.trim() !== selectedProject.title;

  const combinedSaveStatus = {
    saving: saveStatus.saving || chartSaving,
    dirty: saveStatus.dirty || titleDirty,
  };

  useEffect(() => {
    if (!combinedSaveStatus.dirty) return;
    const handler = (e) => {
      e.preventDefault();
      e.returnValue = '';
    };
    window.addEventListener('beforeunload', handler);
    return () => window.removeEventListener('beforeunload', handler);
  }, [combinedSaveStatus.dirty]);

  const handleTitleSave = async () => {
    if (!selectedId || !titleDraft.trim()) return;
    try {
      const res = await apiFetch(`/gantt/projects/${selectedId}`, {
        method: 'PATCH',
        body: JSON.stringify({ title: titleDraft.trim() }),
      });
      if (!res.ok) throw new Error('Failed to update title');
      await fetchProjects();
      setEditingTitle(false);
    } catch (error) {
      toast.error(error.message);
    }
  };

  const handleExport = async (format, pdfMode = 'presentation') => {
    if (!selectedId) return;
    const defaults = {
      csv: 'gantt_export.csv',
      xlsx: 'gantt_export.xlsx',
      pdf: pdfMode === 'detailed' ? 'gantt_export_detailed.pdf' : 'gantt_export.pdf',
    };
    try {
      const path =
        format === 'pdf'
          ? `/gantt/projects/${selectedId}/export.pdf?mode=${pdfMode}`
          : `/gantt/projects/${selectedId}/export.${format}`;
      const res = await apiFetch(path);
      if (!res.ok) throw new Error('Export failed');
      const blob = await res.blob();
      const disposition = res.headers.get('Content-Disposition') || '';
      const match = disposition.match(/filename="?([^"]+)"?/);
      const filename = match ? match[1] : defaults[format];
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = filename;
      a.click();
      URL.revokeObjectURL(url);
      const label =
        format === 'pdf'
          ? pdfMode === 'detailed'
            ? 'Detailed PDF'
            : 'Presentation PDF'
          : format.toUpperCase();
      toast.success(`${label} downloaded`);
    } catch (error) {
      toast.error(error.message);
    }
  };

  const createTask = async (payload) => {
    if (!selectedId) return;
    setChartSaving(true);
    try {
      const res = await apiFetch(`/gantt/projects/${selectedId}/tasks`, {
        method: 'POST',
        body: JSON.stringify(payload),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(parseApiError(err, 'Failed to create task'));
      }
      await fetchTasks(selectedId);
    } catch (error) {
      toast.error(error.message);
    } finally {
      setChartSaving(false);
    }
  };

  const handleAddTask = () => createTask({ title: 'New task', type: 'task' });
  const handleAddMilestone = () => {
    const today = formatIsoDate(new Date());
    createTask({
      title: 'New milestone',
      type: 'milestone',
      start_date: today,
      end_date: today,
    });
  };
  const handleAddPhase = (name) => {
    createTask({ title: 'New task', type: 'task', phase: name.trim() });
  };

  return (
    <div className="h-screen flex flex-col bg-background overflow-hidden">
      <header className="border-b bg-card shrink-0">
        <div className="px-3 sm:px-4 py-2 sm:py-2.5 flex items-center justify-between">
          <Link to="/gantt" className="flex items-center shrink-0" aria-label={appName}>
            <GanttLogo size="header" alt={appName} />
          </Link>
          <div className="flex items-center gap-2">
            {user && (
              <span className="text-xs text-muted-foreground hidden sm:inline">
                {user.name || user.email}
              </span>
            )}
            <ThemeToggle />
            {user ? (
              <Button variant="ghost" size="icon" className="h-8 w-8" onClick={logout} title="Logout">
                <LogOut className="h-3.5 w-3.5" />
              </Button>
            ) : (
              <Button variant="ghost" size="sm" className="h-8" asChild>
                <Link to="/login">
                  <LogIn className="h-3.5 w-3.5 mr-1" />
                  Login
                </Link>
              </Button>
            )}
          </div>
        </div>
      </header>

      <main className="flex-1 flex min-h-0 px-2 py-2 sm:px-3 gap-2">
        <aside className="w-44 sm:w-52 shrink-0 overflow-y-auto">
          {loadingProjects ? (
            <div className="flex justify-center py-8">
              <Loader2 className="h-5 w-5 animate-spin text-muted-foreground" />
            </div>
          ) : (
            <GanttProjectList
              projects={projects}
              selectedId={selectedId}
              onSelect={setSelectedId}
              onRefresh={fetchProjects}
              apiFetch={apiFetch}
              taskTypes={ganttConfig.task_types}
              hasUnsavedChanges={combinedSaveStatus.dirty}
            />
          )}
        </aside>

        <section className="flex-1 flex flex-col min-w-0 min-h-0">
          {!selectedProject ? (
            <div className="flex-1 rounded border bg-muted/30 flex items-center justify-center text-sm text-muted-foreground">
              Select or create a project to start planning.
            </div>
          ) : (
            <>
              {/* Project toolbar */}
              <div className="shrink-0 flex items-center gap-1.5 flex-wrap py-1 border-b mb-2">
                {editingTitle ? (
                  <div className="flex items-center gap-1 mr-2">
                    <Input
                      value={titleDraft}
                      onChange={(e) => setTitleDraft(e.target.value)}
                      className="h-7 text-sm max-w-[200px]"
                    />
                    <Button size="sm" className="h-7 px-2" onClick={handleTitleSave}>Save</Button>
                    <Button size="sm" variant="ghost" className="h-7 px-2" onClick={() => setEditingTitle(false)}>
                      Cancel
                    </Button>
                  </div>
                ) : (
                  <button
                    type="button"
                    className="text-sm font-semibold mr-2 hover:text-primary truncate max-w-[180px]"
                    onClick={() => {
                      setTitleDraft(selectedProject.title);
                      setEditingTitle(true);
                    }}
                    title="Click to rename"
                  >
                    {selectedProject.title}
                  </button>
                )}

                <GanttSaveIndicator
                  saving={combinedSaveStatus.saving}
                  dirty={combinedSaveStatus.dirty}
                />

                <div className="h-4 w-px bg-border mx-1" />

                <Button variant="ghost" size="sm" className="h-7 px-2 text-xs" onClick={handleAddTask}>
                  <Plus className="h-3 w-3 mr-1" />Task
                </Button>
                <Button
                  variant="ghost"
                  size="sm"
                  className="h-7 px-2 text-xs"
                  onClick={() => setShowAddPhase(true)}
                >
                  <Layers className="h-3 w-3 mr-1" />Phase
                </Button>
                <Button variant="ghost" size="sm" className="h-7 px-2 text-xs" onClick={handleAddMilestone}>
                  <Diamond className="h-3 w-3 mr-1" />Milestone
                </Button>

                <div className="h-4 w-px bg-border mx-1" />

                <Select value={zoom} onValueChange={(v) => { setZoom(v); setFitToScreen(false); }}>
                  <SelectTrigger className="h-7 w-[88px] text-xs">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {ZOOM_LEVELS.map((z) => (
                      <SelectItem key={z} value={z} className="text-xs">{z}</SelectItem>
                    ))}
                  </SelectContent>
                </Select>

                <Button
                  variant="ghost"
                  size="sm"
                  className="h-7 px-2 text-xs"
                  title="Fit timeline to screen"
                  onClick={() => setFitToScreen((v) => !v)}
                >
                  <Maximize2 className="h-3 w-3" />
                </Button>

                <div className="h-4 w-px bg-border mx-1" />

                <Button
                  variant="ghost"
                  size="sm"
                  className="h-7 px-2 text-xs"
                  onClick={() => setShowImport((v) => !v)}
                >
                  <Upload className="h-3 w-3 mr-1" />Import
                </Button>
                <Button variant="ghost" size="sm" className="h-7 px-2 text-xs" onClick={() => handleExport('csv')}>
                  <Download className="h-3 w-3 mr-1" />CSV
                </Button>
                <Button variant="ghost" size="sm" className="h-7 px-2 text-xs" onClick={() => handleExport('xlsx')}>
                  Excel
                </Button>
                <div className="flex items-center">
                  <Button
                    variant="ghost"
                    size="sm"
                    className="h-7 px-2 text-xs rounded-r-none"
                    onClick={() => handleExport('pdf', 'presentation')}
                  >
                    <Download className="h-3 w-3 mr-1" />
                    PDF
                  </Button>
                  <DropdownMenu>
                    <DropdownMenuTrigger asChild>
                      <Button
                        variant="ghost"
                        size="sm"
                        className="h-7 px-1 text-xs rounded-l-none border-l border-border/60"
                        title="More PDF export options"
                      >
                        <ChevronDown className="h-3 w-3" />
                      </Button>
                    </DropdownMenuTrigger>
                    <DropdownMenuContent align="start" className="text-xs">
                      <DropdownMenuItem onClick={() => handleExport('pdf', 'detailed')}>
                        Detailed PDF
                      </DropdownMenuItem>
                    </DropdownMenuContent>
                  </DropdownMenu>
                </div>

                <div className="ml-auto">
                  <Button
                    variant={viewMode === 'table' ? 'secondary' : 'ghost'}
                    size="sm"
                    className="h-7 px-2 text-xs"
                    onClick={() => setViewMode((v) => (v === 'cockpit' ? 'table' : 'cockpit'))}
                  >
                    <Table2 className="h-3 w-3 mr-1" />
                    {viewMode === 'cockpit' ? 'Table view' : 'Gantt view'}
                  </Button>
                </div>
              </div>

              <div className="flex-1 min-h-0 flex flex-col overflow-hidden">
                {showImport ? (
                  <GanttImportReview
                    projectId={selectedId}
                    apiFetch={apiFetch}
                    importConfig={ganttConfig.import}
                    taskTypes={ganttConfig.task_types}
                    onConfirmed={() => {
                      setShowImport(false);
                      fetchTasks(selectedId);
                    }}
                    onClose={() => setShowImport(false)}
                  />
                ) : loadingTasks ? (
                  <div className="flex-1 flex items-center justify-center">
                    <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
                  </div>
                ) : viewMode === 'cockpit' ? (
                  <GanttPlanningCockpit
                    tasks={tasks}
                    projectId={selectedId}
                    apiFetch={apiFetch}
                    taskStatuses={ganttConfig.task_statuses}
                    taskTypes={ganttConfig.task_types}
                    zoom={zoom}
                    fitToScreen={fitToScreen}
                    onTasksChange={setTasks}
                    onSaving={setChartSaving}
                    onSaveStatusChange={setSaveStatus}
                    onRevert={() => fetchTasks(selectedId)}
                    onRefresh={() => fetchTasks(selectedId)}
                  />
                ) : (
                  <GanttTaskTable
                    key={selectedId}
                    projectId={selectedId}
                    tasks={tasks}
                    loading={loadingTasks}
                    taskStatuses={ganttConfig.task_statuses}
                    taskTypes={ganttConfig.task_types}
                    onRefresh={() => fetchTasks(selectedId)}
                    apiFetch={apiFetch}
                    onSaveStatusChange={setSaveStatus}
                  />
                )}
              </div>
            </>
          )}
        </section>
      </main>

      <GanttAddPhaseDialog
        open={showAddPhase}
        onOpenChange={setShowAddPhase}
        onConfirm={handleAddPhase}
        saving={chartSaving}
      />
    </div>
  );
};
