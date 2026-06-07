import { useState } from 'react';
import { Button } from '../ui/button';
import { Card, CardContent } from '../ui/card';
import { toast } from 'sonner';
import { FolderKanban, Plus, Trash2, Loader2 } from 'lucide-react';
import { cn } from '../../lib/utils';
import { parseApiError } from './ganttApiUtils';
import { GanttNewChartWizard } from './GanttNewChartWizard';

export const GanttProjectList = ({
  projects,
  selectedId,
  onSelect,
  onRefresh,
  apiFetch,
  taskTypes,
  hasUnsavedChanges,
}) => {
  const [wizardOpen, setWizardOpen] = useState(false);
  const [deleting, setDeleting] = useState(null);

  const handleSelect = (projectId) => {
    if (projectId === selectedId) return;
    if (hasUnsavedChanges && !window.confirm('You have unsaved changes. Switch project anyway?')) {
      return;
    }
    onSelect(projectId);
  };

  const handleCreated = async (projectId) => {
    if (
      hasUnsavedChanges &&
      !window.confirm('You have unsaved changes. Switch to the new chart anyway?')
    ) {
      return;
    }
    await onRefresh();
    onSelect(projectId);
  };

  const handleDelete = async (projectId, e) => {
    e.stopPropagation();
    if (!window.confirm('Delete this project and all its tasks?')) return;

    setDeleting(projectId);
    try {
      const res = await apiFetch(`/gantt/projects/${projectId}`, { method: 'DELETE' });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(parseApiError(err, 'Failed to delete project'));
      }
      if (selectedId === projectId) {
        onSelect(null);
      }
      await onRefresh();
      toast.success('Project deleted');
    } catch (error) {
      toast.error(error.message);
    } finally {
      setDeleting(null);
    }
  };

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <h2 className="text-sm font-medium text-muted-foreground uppercase tracking-wide">
          Projects
        </h2>
        <Button size="sm" variant="outline" onClick={() => setWizardOpen(true)}>
          <Plus className="h-4 w-4 mr-1" />
          New chart
        </Button>
      </div>

      {projects.length === 0 ? (
        <Card>
          <CardContent className="py-8 text-center text-sm text-muted-foreground space-y-3">
            <p>No charts yet. Create one to get started.</p>
            <Button size="sm" onClick={() => setWizardOpen(true)}>
              <Plus className="h-4 w-4 mr-1" />
              New chart
            </Button>
          </CardContent>
        </Card>
      ) : (
        <div className="space-y-2">
          {projects.map((project) => (
            <button
              key={project.gantt_project_id}
              type="button"
              onClick={() => handleSelect(project.gantt_project_id)}
              className={cn(
                'w-full flex items-center gap-3 p-3 rounded-lg border text-left transition-colors',
                selectedId === project.gantt_project_id
                  ? 'border-primary bg-primary/5'
                  : 'hover:bg-muted/50'
              )}
            >
              <FolderKanban className="h-4 w-4 shrink-0 text-muted-foreground" />
              <div className="flex-1 min-w-0">
                <p className="font-medium truncate">{project.title}</p>
                {project.description && (
                  <p className="text-xs text-muted-foreground truncate">{project.description}</p>
                )}
              </div>
              <Button
                variant="ghost"
                size="icon"
                className="h-7 w-7 shrink-0 text-destructive"
                onClick={(e) => handleDelete(project.gantt_project_id, e)}
                disabled={deleting === project.gantt_project_id}
              >
                {deleting === project.gantt_project_id ? (
                  <Loader2 className="h-3 w-3 animate-spin" />
                ) : (
                  <Trash2 className="h-3 w-3" />
                )}
              </Button>
            </button>
          ))}
        </div>
      )}

      <GanttNewChartWizard
        open={wizardOpen}
        onOpenChange={setWizardOpen}
        apiFetch={apiFetch}
        onCreated={handleCreated}
        taskTypes={taskTypes}
      />
    </div>
  );
};
