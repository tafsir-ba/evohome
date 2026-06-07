import { useState } from 'react';
import { Button } from '../ui/button';
import { Input } from '../ui/input';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../ui/select';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '../ui/table';
import { GanttDependencyPicker } from './GanttDependencyPicker';
import { parseApiError } from './ganttApiUtils';
import { toast } from 'sonner';
import { ArrowDown, ArrowUp, Plus, Trash2, Loader2 } from 'lucide-react';

const emptyTask = {
  type: 'task',
  phase: '',
  title: '',
  description: '',
  start_date: '',
  end_date: '',
  status: 'not_started',
  responsible_party: '',
  dependencies: [],
};

export const GanttTaskTable = ({
  projectId,
  tasks,
  loading,
  taskStatuses = [],
  taskTypes = ['task', 'milestone'],
  onRefresh,
  apiFetch,
}) => {
  const [saving, setSaving] = useState(null);
  const [newTask, setNewTask] = useState(emptyTask);
  const [adding, setAdding] = useState(false);

  const saveTask = async (taskId, updates) => {
    setSaving(taskId);
    try {
      const res = await apiFetch(
        `/gantt/projects/${projectId}/tasks/${taskId}`,
        { method: 'PATCH', body: JSON.stringify(updates) }
      );
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(parseApiError(err, 'Failed to update task'));
      }
      await onRefresh();
    } catch (error) {
      toast.error(error.message);
    } finally {
      setSaving(null);
    }
  };

  const handleFieldChange = (task, field, value) => {
    const updates = { [field]: value };
    if (field === 'type' && value === 'milestone' && task.start_date) {
      updates.end_date = task.start_date;
    }
    saveTask(task.task_id, updates);
  };

  const handleAddTask = async () => {
    if (!newTask.title.trim()) {
      toast.error('Title is required');
      return;
    }
    setAdding(true);
    try {
      const payload = {
        ...newTask,
        phase: newTask.phase || null,
        description: newTask.description || null,
        responsible_party: newTask.responsible_party || null,
        start_date: newTask.start_date || null,
        end_date: newTask.end_date || null,
      };
      const res = await apiFetch(`/gantt/projects/${projectId}/tasks`, {
        method: 'POST',
        body: JSON.stringify(payload),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(parseApiError(err, 'Failed to create task'));
      }
      setNewTask(emptyTask);
      await onRefresh();
      toast.success('Task added');
    } catch (error) {
      toast.error(error.message);
    } finally {
      setAdding(false);
    }
  };

  const handleDelete = async (taskId) => {
    setSaving(taskId);
    try {
      const res = await apiFetch(
        `/gantt/projects/${projectId}/tasks/${taskId}`,
        { method: 'DELETE' }
      );
      if (res.status === 409) {
        const err = await res.json().catch(() => ({}));
        const ids = err.dependent_task_ids || [];
        const base = err.detail || 'Cannot delete: other tasks depend on this one';
        toast.error(ids.length ? `${base} Blocked by: ${ids.join(', ')}` : base);
        return;
      }
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(parseApiError(err, 'Failed to delete task'));
      }
      await onRefresh();
      toast.success('Task deleted');
    } catch (error) {
      toast.error(error.message);
    } finally {
      setSaving(null);
    }
  };

  const handleReorder = async (taskId, direction) => {
    const index = tasks.findIndex((t) => t.task_id === taskId);
    if (index < 0) return;
    const swapIndex = direction === 'up' ? index - 1 : index + 1;
    if (swapIndex < 0 || swapIndex >= tasks.length) return;

    const ids = tasks.map((t) => t.task_id);
    [ids[index], ids[swapIndex]] = [ids[swapIndex], ids[index]];

    try {
      const res = await apiFetch(`/gantt/projects/${projectId}/tasks/reorder`, {
        method: 'POST',
        body: JSON.stringify({ task_ids: ids }),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(parseApiError(err, 'Failed to reorder'));
      }
      await onRefresh();
    } catch (error) {
      toast.error(error.message);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center py-12">
        <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <div className="overflow-x-auto rounded-lg border">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead className="w-10">#</TableHead>
              <TableHead>Type</TableHead>
              <TableHead>Phase</TableHead>
              <TableHead>Title</TableHead>
              <TableHead>Start</TableHead>
              <TableHead>End</TableHead>
              <TableHead>Status</TableHead>
              <TableHead>Responsible</TableHead>
              <TableHead>Dependencies</TableHead>
              <TableHead className="w-24">Actions</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {tasks.map((task) => (
              <TableRow key={`${task.task_id}-${task.updated_at}`}>
                <TableCell className="text-muted-foreground">{task.order + 1}</TableCell>
                <TableCell>
                  <Select
                    value={task.type}
                    onValueChange={(v) => handleFieldChange(task, 'type', v)}
                    disabled={saving === task.task_id}
                  >
                    <SelectTrigger className="w-28 h-8">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      {taskTypes.map((type) => (
                        <SelectItem key={type} value={type}>
                          {type === 'milestone' ? 'Milestone' : 'Task'}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </TableCell>
                <TableCell>
                  <Input
                    className="h-8 min-w-[100px]"
                    defaultValue={task.phase || ''}
                    onBlur={(e) => {
                      if (e.target.value !== (task.phase || '')) {
                        handleFieldChange(task, 'phase', e.target.value || null);
                      }
                    }}
                  />
                </TableCell>
                <TableCell>
                  <Input
                    className="h-8 min-w-[140px]"
                    defaultValue={task.title}
                    onBlur={(e) => {
                      if (e.target.value !== task.title) {
                        handleFieldChange(task, 'title', e.target.value);
                      }
                    }}
                  />
                </TableCell>
                <TableCell>
                  <Input
                    type="date"
                    className="h-8 w-36"
                    defaultValue={task.start_date || ''}
                    onBlur={(e) => {
                      const val = e.target.value || null;
                      if (val !== (task.start_date || null)) {
                        const updates = { start_date: val };
                        if (task.type === 'milestone' && val) {
                          updates.end_date = val;
                        }
                        saveTask(task.task_id, updates);
                      }
                    }}
                  />
                </TableCell>
                <TableCell>
                  {task.type === 'milestone' ? (
                    <span className="text-xs text-muted-foreground">{task.end_date || '—'}</span>
                  ) : (
                    <Input
                      type="date"
                      className="h-8 w-36"
                      defaultValue={task.end_date || ''}
                      onBlur={(e) => {
                        const val = e.target.value || null;
                        if (val !== (task.end_date || null)) {
                          handleFieldChange(task, 'end_date', val);
                        }
                      }}
                    />
                  )}
                </TableCell>
                <TableCell>
                  <Select
                    value={task.status}
                    onValueChange={(v) => handleFieldChange(task, 'status', v)}
                    disabled={saving === task.task_id}
                  >
                    <SelectTrigger className="w-32 h-8">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      {taskStatuses.map((s) => (
                        <SelectItem key={s} value={s}>{s.replace('_', ' ')}</SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </TableCell>
                <TableCell>
                  <Input
                    className="h-8 min-w-[100px]"
                    defaultValue={task.responsible_party || ''}
                    onBlur={(e) => {
                      if (e.target.value !== (task.responsible_party || '')) {
                        handleFieldChange(task, 'responsible_party', e.target.value || null);
                      }
                    }}
                  />
                </TableCell>
                <TableCell>
                  <GanttDependencyPicker
                    taskId={task.task_id}
                    tasks={tasks}
                    dependencies={task.dependencies || []}
                    onChange={(deps) => handleFieldChange(task, 'dependencies', deps)}
                    disabled={saving === task.task_id}
                  />
                </TableCell>
                <TableCell>
                  <div className="flex gap-1">
                    <Button
                      variant="ghost"
                      size="icon"
                      className="h-7 w-7"
                      onClick={() => handleReorder(task.task_id, 'up')}
                      disabled={task.order === 0}
                    >
                      <ArrowUp className="h-3 w-3" />
                    </Button>
                    <Button
                      variant="ghost"
                      size="icon"
                      className="h-7 w-7"
                      onClick={() => handleReorder(task.task_id, 'down')}
                      disabled={task.order === tasks.length - 1}
                    >
                      <ArrowDown className="h-3 w-3" />
                    </Button>
                    <Button
                      variant="ghost"
                      size="icon"
                      className="h-7 w-7 text-destructive"
                      onClick={() => handleDelete(task.task_id)}
                      disabled={saving === task.task_id}
                    >
                      <Trash2 className="h-3 w-3" />
                    </Button>
                  </div>
                </TableCell>
              </TableRow>
            ))}

            <TableRow className="bg-muted/20">
              <TableCell />
              <TableCell>
                <Select
                  value={newTask.type}
                  onValueChange={(v) => setNewTask((t) => ({ ...t, type: v }))}
                >
                  <SelectTrigger className="w-28 h-8">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {taskTypes.map((type) => (
                      <SelectItem key={type} value={type}>
                        {type === 'milestone' ? 'Milestone' : 'Task'}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </TableCell>
              <TableCell>
                <Input
                  className="h-8"
                  placeholder="Phase"
                  value={newTask.phase}
                  onChange={(e) => setNewTask((t) => ({ ...t, phase: e.target.value }))}
                />
              </TableCell>
              <TableCell>
                <Input
                  className="h-8"
                  placeholder="New task title"
                  value={newTask.title}
                  onChange={(e) => setNewTask((t) => ({ ...t, title: e.target.value }))}
                />
              </TableCell>
              <TableCell>
                <Input
                  type="date"
                  className="h-8 w-36"
                  value={newTask.start_date}
                  onChange={(e) =>
                    setNewTask((t) => ({
                      ...t,
                      start_date: e.target.value,
                      end_date: t.type === 'milestone' ? e.target.value : t.end_date,
                    }))
                  }
                />
              </TableCell>
              <TableCell>
                {newTask.type === 'milestone' ? (
                  <span className="text-xs text-muted-foreground">
                    {newTask.start_date || '—'}
                  </span>
                ) : (
                  <Input
                    type="date"
                    className="h-8 w-36"
                    value={newTask.end_date}
                    onChange={(e) => setNewTask((t) => ({ ...t, end_date: e.target.value }))}
                  />
                )}
              </TableCell>
              <TableCell colSpan={3} />
              <TableCell>
                <Button size="sm" onClick={handleAddTask} disabled={adding}>
                  {adding ? <Loader2 className="h-4 w-4 animate-spin" /> : <Plus className="h-4 w-4" />}
                </Button>
              </TableCell>
            </TableRow>
          </TableBody>
        </Table>
      </div>
    </div>
  );
};
