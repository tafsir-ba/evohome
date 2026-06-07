import { useState, useEffect, useCallback } from 'react';
import { Link } from 'react-router-dom';
import { useAuth } from '../../context/AuthContext';
import { Button } from '../../components/ui/button';
import { Input } from '../../components/ui/input';
import { GanttProjectList } from '../../components/gantt/GanttProjectList';
import { GanttTaskTable } from '../../components/gantt/GanttTaskTable';
import { GanttTimelinePreview } from '../../components/gantt/GanttTimelinePreview';
import { ThemeToggle } from '../../components/ThemeToggle';
import { toast } from 'sonner';
import { Download, LogOut, BarChart3, Loader2 } from 'lucide-react';

const API = process.env.REACT_APP_BACKEND_URL + '/api';

const getAuthHeaders = () => {
  const token = localStorage.getItem('auth_token');
  const headers = { 'Content-Type': 'application/json' };
  if (token) headers.Authorization = `Bearer ${token}`;
  return headers;
};

export const GanttChartTool = () => {
  const { user, logout } = useAuth();
  const [projects, setProjects] = useState([]);
  const [selectedId, setSelectedId] = useState(null);
  const [tasks, setTasks] = useState([]);
  const [loadingProjects, setLoadingProjects] = useState(true);
  const [loadingTasks, setLoadingTasks] = useState(false);
  const [editingTitle, setEditingTitle] = useState(false);
  const [titleDraft, setTitleDraft] = useState('');
  const [ganttConfig, setGanttConfig] = useState({
    task_statuses: ['not_started', 'in_progress', 'completed', 'blocked'],
    task_types: ['task', 'milestone'],
    dependency_types: ['FS'],
  });

  const apiFetch = useCallback((path, options = {}) => {
    return fetch(`${API}${path}`, {
      credentials: 'include',
      headers: getAuthHeaders(),
      ...options,
    });
  }, []);

  const fetchProjects = useCallback(async () => {
    try {
      const res = await apiFetch('/gantt/projects');
      if (!res.ok) throw new Error('Failed to load projects');
      const data = await res.json();
      setProjects(data);
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
      if (res.ok) {
        setGanttConfig(await res.json());
      }
    } catch {
      // Keep fallback defaults; backend validation remains authoritative.
    }
  }, [apiFetch]);

  useEffect(() => {
    fetchProjects();
    fetchConfig();
  }, [fetchProjects, fetchConfig]);

  useEffect(() => {
    fetchTasks(selectedId);
  }, [selectedId, fetchTasks]);

  const selectedProject = projects.find((p) => p.gantt_project_id === selectedId);

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

  const handleExportCsv = async () => {
    if (!selectedId) return;
    try {
      const res = await apiFetch(`/gantt/projects/${selectedId}/export.csv`);
      if (!res.ok) throw new Error('Export failed');
      const blob = await res.blob();
      const disposition = res.headers.get('Content-Disposition') || '';
      const match = disposition.match(/filename="?([^"]+)"?/);
      const filename = match ? match[1] : 'gantt_export.csv';
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = filename;
      a.click();
      URL.revokeObjectURL(url);
      toast.success('CSV downloaded');
    } catch (error) {
      toast.error(error.message);
    }
  };

  return (
    <div className="min-h-screen bg-background">
      <header className="border-b bg-card">
        <div className="max-w-7xl mx-auto px-4 py-3 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <BarChart3 className="h-6 w-6 text-primary" />
            <div>
              <h1 className="text-lg font-semibold">Gantt Chart</h1>
              <p className="text-xs text-muted-foreground">Standalone planning tool</p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            {user && (
              <span className="text-sm text-muted-foreground hidden sm:inline">
                {user.name || user.email}
              </span>
            )}
            <ThemeToggle />
            <Button variant="ghost" size="sm" asChild>
              <Link to={user?.role === 'buyer' ? '/buyer/dashboard' : '/agent/home'}>
                Back to app
              </Link>
            </Button>
            <Button variant="ghost" size="icon" onClick={logout} title="Logout">
              <LogOut className="h-4 w-4" />
            </Button>
          </div>
        </div>
      </header>

      <main className="max-w-7xl mx-auto px-4 py-6">
        <div className="grid grid-cols-1 lg:grid-cols-4 gap-6">
          <aside className="lg:col-span-1">
            {loadingProjects ? (
              <div className="flex justify-center py-8">
                <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
              </div>
            ) : (
              <GanttProjectList
                projects={projects}
                selectedId={selectedId}
                onSelect={setSelectedId}
                onRefresh={fetchProjects}
                apiFetch={apiFetch}
              />
            )}
          </aside>

          <section className="lg:col-span-3 space-y-6">
            {!selectedProject ? (
              <div className="rounded-lg border bg-muted/30 p-12 text-center text-muted-foreground">
                Select or create a project to manage tasks.
              </div>
            ) : (
              <>
                <div className="flex items-center justify-between gap-4">
                  {editingTitle ? (
                    <div className="flex items-center gap-2 flex-1">
                      <Input
                        value={titleDraft}
                        onChange={(e) => setTitleDraft(e.target.value)}
                        className="max-w-md"
                      />
                      <Button size="sm" onClick={handleTitleSave}>Save</Button>
                      <Button
                        size="sm"
                        variant="ghost"
                        onClick={() => setEditingTitle(false)}
                      >
                        Cancel
                      </Button>
                    </div>
                  ) : (
                    <h2
                      className="text-xl font-semibold cursor-pointer hover:text-primary"
                      onClick={() => {
                        setTitleDraft(selectedProject.title);
                        setEditingTitle(true);
                      }}
                      title="Click to edit"
                    >
                      {selectedProject.title}
                    </h2>
                  )}
                  <Button variant="outline" size="sm" onClick={handleExportCsv}>
                    <Download className="h-4 w-4 mr-2" />
                    Export CSV
                  </Button>
                </div>

                <GanttTaskTable
                  projectId={selectedId}
                  tasks={tasks}
                  loading={loadingTasks}
                  taskStatuses={ganttConfig.task_statuses}
                  taskTypes={ganttConfig.task_types}
                  onRefresh={() => fetchTasks(selectedId)}
                  apiFetch={apiFetch}
                />

                <div>
                  <h3 className="text-sm font-medium text-muted-foreground mb-3 uppercase tracking-wide">
                    Timeline Preview
                  </h3>
                  <GanttTimelinePreview tasks={tasks} />
                </div>
              </>
            )}
          </section>
        </div>
      </main>
    </div>
  );
};
