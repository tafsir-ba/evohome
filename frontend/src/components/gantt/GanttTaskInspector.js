import { useState, useEffect } from 'react';
import { Button } from '../ui/button';
import { Input } from '../ui/input';
import { Label } from '../ui/label';
import { Textarea } from '../ui/textarea';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../ui/select';
import { GanttDependencyPicker } from './GanttDependencyPicker';
import { parseApiError } from './ganttApiUtils';
import { duplicateTaskPayload } from './ganttTaskUtils';
import { toast } from 'sonner';
import { Copy, Trash2, X } from 'lucide-react';

export const GanttTaskInspector = ({
  task,
  tasks,
  projectId,
  apiFetch,
  taskStatuses,
  taskTypes,
  onClose,
  onRefresh,
  onDeleted,
}) => {
  const [draft, setDraft] = useState(task);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    setDraft(task);
  }, [task]);

  if (!task) return null;

  const patch = async (updates) => {
    setSaving(true);
    try {
      const res = await apiFetch(
        `/gantt/projects/${projectId}/tasks/${task.task_id}`,
        { method: 'PATCH', body: JSON.stringify(updates) }
      );
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(parseApiError(err, 'Failed to update task'));
      }
      await onRefresh?.();
    } catch (error) {
      toast.error(error.message);
    } finally {
      setSaving(false);
    }
  };

  const handleField = (field, value) => {
    const updates = { [field]: value };
    if (field === 'type' && value === 'milestone' && draft.start_date) {
      updates.end_date = draft.start_date;
    }
    if (field === 'start_date' && draft.type === 'milestone') {
      updates.end_date = value;
    }
    setDraft((prev) => ({ ...prev, ...updates }));
    patch(updates);
  };

  const handleDelete = async () => {
    setSaving(true);
    try {
      const res = await apiFetch(
        `/gantt/projects/${projectId}/tasks/${task.task_id}`,
        { method: 'DELETE' }
      );
      if (res.status === 409) {
        const err = await res.json().catch(() => ({}));
        toast.error(err.detail || 'Cannot delete: other tasks depend on this one');
        return;
      }
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(parseApiError(err, 'Failed to delete task'));
      }
      onDeleted?.(task.task_id);
      onClose?.();
      toast.success('Task deleted');
    } catch (error) {
      toast.error(error.message);
    } finally {
      setSaving(false);
    }
  };

  const handleDuplicate = async () => {
    setSaving(true);
    try {
      const res = await apiFetch(`/gantt/projects/${projectId}/tasks`, {
        method: 'POST',
        body: JSON.stringify(duplicateTaskPayload(task)),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(parseApiError(err, 'Failed to duplicate task'));
      }
      await onRefresh?.();
      toast.success('Task duplicated');
    } catch (error) {
      toast.error(error.message);
    } finally {
      setSaving(false);
    }
  };

  return (
    <aside className="w-72 shrink-0 border-l bg-card flex flex-col max-h-full overflow-hidden">
      <div className="flex items-center justify-between px-3 py-2 border-b">
        <span className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
          Inspector
        </span>
        <Button variant="ghost" size="icon" className="h-7 w-7" onClick={onClose}>
          <X className="h-3.5 w-3.5" />
        </Button>
      </div>

      <div className="flex-1 overflow-y-auto p-3 space-y-3 text-sm">
        <div className="space-y-1">
          <Label className="text-xs">Title</Label>
          <Input
            className="h-8 text-sm"
            value={draft.title}
            disabled={saving}
            onChange={(e) => setDraft((p) => ({ ...p, title: e.target.value }))}
            onBlur={(e) => {
              const v = e.target.value.trim();
              if (!v) {
                toast.error('Title is required');
                setDraft((p) => ({ ...p, title: task.title }));
                return;
              }
              if (v !== task.title) handleField('title', v);
            }}
          />
        </div>

        <div className="space-y-1">
          <Label className="text-xs">Type</Label>
          <Select value={draft.type} onValueChange={(v) => handleField('type', v)} disabled={saving}>
            <SelectTrigger className="h-8 text-sm">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {taskTypes.map((t) => (
                <SelectItem key={t} value={t}>{t === 'milestone' ? 'Milestone' : 'Task'}</SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>

        <div className="space-y-1">
          <Label className="text-xs">Phase</Label>
          <Input
            className="h-8 text-sm"
            value={draft.phase || ''}
            disabled={saving}
            onChange={(e) => setDraft((p) => ({ ...p, phase: e.target.value }))}
            onBlur={(e) => {
              const v = e.target.value.trim() || null;
              if (v !== (task.phase || null)) handleField('phase', v);
            }}
          />
        </div>

        <div className="grid grid-cols-2 gap-2">
          <div className="space-y-1">
            <Label className="text-xs">Start</Label>
            <Input
              type="date"
              className="h-8 text-sm"
              value={draft.start_date || ''}
              disabled={saving}
              onChange={(e) => handleField('start_date', e.target.value || null)}
            />
          </div>
          <div className="space-y-1">
            <Label className="text-xs">End</Label>
            <Input
              type="date"
              className="h-8 text-sm"
              value={draft.end_date || ''}
              disabled={saving || draft.type === 'milestone'}
              onChange={(e) => handleField('end_date', e.target.value || null)}
            />
          </div>
        </div>

        <div className="space-y-1">
          <Label className="text-xs">Status</Label>
          <Select
            value={draft.status}
            onValueChange={(v) => handleField('status', v)}
            disabled={saving}
          >
            <SelectTrigger className="h-8 text-sm">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {taskStatuses.map((s) => (
                <SelectItem key={s} value={s}>{s.replace(/_/g, ' ')}</SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>

        <div className="space-y-1">
          <Label className="text-xs">Responsible</Label>
          <Input
            className="h-8 text-sm"
            value={draft.responsible_party || ''}
            disabled={saving}
            onChange={(e) => setDraft((p) => ({ ...p, responsible_party: e.target.value }))}
            onBlur={(e) => {
              const v = e.target.value.trim() || null;
              if (v !== (task.responsible_party || null)) handleField('responsible_party', v);
            }}
          />
        </div>

        <div className="space-y-1">
          <Label className="text-xs">Dependencies (finish-to-start)</Label>
          <GanttDependencyPicker
            taskId={task.task_id}
            tasks={tasks}
            dependencies={draft.dependencies || []}
            disabled={saving}
            onChange={(deps) => handleField('dependencies', deps)}
          />
        </div>

        <div className="space-y-1">
          <Label className="text-xs">Notes</Label>
          <Textarea
            className="text-sm min-h-[72px]"
            value={draft.description || ''}
            disabled={saving}
            onChange={(e) => setDraft((p) => ({ ...p, description: e.target.value }))}
            onBlur={(e) => {
              const v = e.target.value.trim() || null;
              if (v !== (task.description || null)) handleField('description', v);
            }}
          />
        </div>
      </div>

      <div className="border-t p-3 flex gap-2">
        <Button variant="outline" size="sm" className="flex-1 h-8" onClick={handleDuplicate} disabled={saving}>
          <Copy className="h-3.5 w-3.5 mr-1" />
          Duplicate
        </Button>
        <Button variant="destructive" size="sm" className="h-8" onClick={handleDelete} disabled={saving}>
          <Trash2 className="h-3.5 w-3.5" />
        </Button>
      </div>
    </aside>
  );
};
