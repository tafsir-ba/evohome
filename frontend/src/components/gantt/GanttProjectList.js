import { useState } from 'react';
import { Button } from '../ui/button';
import { Input } from '../ui/input';
import { Card, CardContent } from '../ui/card';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from '../ui/dialog';
import { Label } from '../ui/label';
import { Textarea } from '../ui/textarea';
import { toast } from 'sonner';
import { FolderKanban, Plus, Trash2, Loader2 } from 'lucide-react';
import { cn } from '../../lib/utils';
import { parseApiError } from './ganttApiUtils';

export const GanttProjectList = ({
  projects,
  selectedId,
  onSelect,
  onRefresh,
  apiFetch,
}) => {
  const [createOpen, setCreateOpen] = useState(false);
  const [title, setTitle] = useState('');
  const [description, setDescription] = useState('');
  const [creating, setCreating] = useState(false);
  const [deleting, setDeleting] = useState(null);

  const handleCreate = async () => {
    if (!title.trim()) {
      toast.error('Project title is required');
      return;
    }
    setCreating(true);
    try {
      const res = await apiFetch('/gantt/projects', {
        method: 'POST',
        body: JSON.stringify({ title: title.trim(), description: description || null }),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(parseApiError(err, 'Failed to create project'));
      }
      const project = await res.json();
      setCreateOpen(false);
      setTitle('');
      setDescription('');
      await onRefresh();
      onSelect(project.gantt_project_id);
      toast.success('Project created');
    } catch (error) {
      toast.error(error.message);
    } finally {
      setCreating(false);
    }
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
        <Button size="sm" variant="outline" onClick={() => setCreateOpen(true)}>
          <Plus className="h-4 w-4 mr-1" />
          New
        </Button>
      </div>

      {projects.length === 0 ? (
        <Card>
          <CardContent className="py-8 text-center text-sm text-muted-foreground">
            No projects yet. Create one to get started.
          </CardContent>
        </Card>
      ) : (
        <div className="space-y-2">
          {projects.map((project) => (
            <button
              key={project.gantt_project_id}
              type="button"
              onClick={() => onSelect(project.gantt_project_id)}
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

      <Dialog open={createOpen} onOpenChange={setCreateOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>New Gantt Project</DialogTitle>
          </DialogHeader>
          <div className="space-y-4">
            <div>
              <Label htmlFor="project-title">Title</Label>
              <Input
                id="project-title"
                value={title}
                onChange={(e) => setTitle(e.target.value)}
                placeholder="Project name"
              />
            </div>
            <div>
              <Label htmlFor="project-desc">Description (optional)</Label>
              <Textarea
                id="project-desc"
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                placeholder="Brief description"
                rows={3}
              />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setCreateOpen(false)}>
              Cancel
            </Button>
            <Button onClick={handleCreate} disabled={creating}>
              {creating && <Loader2 className="h-4 w-4 mr-2 animate-spin" />}
              Create
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
};
