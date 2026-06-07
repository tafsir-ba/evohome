import { useState, useEffect, useRef, useCallback, useMemo, Fragment } from 'react';
import { Button } from '../ui/button';
import { Input } from '../ui/input';
import { Label } from '../ui/label';
import { Textarea } from '../ui/textarea';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../ui/select';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '../ui/table';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
  DialogDescription,
} from '../ui/dialog';
import { GanttDependencyPicker } from './GanttDependencyPicker';
import { parseApiError } from './ganttApiUtils';
import {
  groupTasksByPhase,
  parseBulkTaskRows,
  duplicateTaskPayload,
} from './ganttTaskUtils';
import { toast } from 'sonner';
import {
  ArrowDown,
  ArrowUp,
  Plus,
  Trash2,
  Loader2,
  ChevronDown,
  ChevronRight,
  Copy,
  ClipboardPaste,
  Keyboard,
} from 'lucide-react';
import { cn } from '../../lib/utils';

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

const isNewTaskDirty = (task) =>
  Boolean(
    task.title.trim() ||
    task.phase.trim() ||
    task.start_date ||
    task.end_date ||
    task.responsible_party.trim()
  );

const TaskRow = ({
  task,
  tasks,
  taskTypes,
  taskStatuses,
  saving,
  selected,
  onSelect,
  onFieldChange,
  onSaveDates,
  onReorder,
  onDelete,
  onDuplicate,
  onMarkDirty,
  onMarkClean,
}) => (
  <TableRow
    className={cn(selected && 'bg-primary/5 ring-1 ring-inset ring-primary/20')}
    onClick={() => onSelect(task.task_id)}
  >
    <TableCell className="text-muted-foreground">{task.order + 1}</TableCell>
    <TableCell onClick={(e) => e.stopPropagation()}>
      <Select
        value={task.type}
        onValueChange={(v) => onFieldChange(task, 'type', v)}
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
    <TableCell onClick={(e) => e.stopPropagation()}>
      <Input
        className="h-8 min-w-[100px]"
        defaultValue={task.phase || ''}
        onChange={() => onMarkDirty(task.task_id)}
        onBlur={(e) => {
          if (e.target.value !== (task.phase || '')) {
            onFieldChange(task, 'phase', e.target.value || null);
          } else {
            onMarkClean(task.task_id);
          }
        }}
      />
    </TableCell>
    <TableCell onClick={(e) => e.stopPropagation()}>
      <Input
        className="h-8 min-w-[140px]"
        defaultValue={task.title}
        onChange={() => onMarkDirty(task.task_id)}
        onBlur={(e) => {
          if (e.target.value !== task.title) {
            onFieldChange(task, 'title', e.target.value);
          } else {
            onMarkClean(task.task_id);
          }
        }}
      />
    </TableCell>
    <TableCell onClick={(e) => e.stopPropagation()}>
      <Input
        type="date"
        className="h-8 w-36"
        defaultValue={task.start_date || ''}
        onChange={() => onMarkDirty(task.task_id)}
        onBlur={(e) => {
          const val = e.target.value || null;
          if (val !== (task.start_date || null)) {
            onSaveDates(task, val);
          } else {
            onMarkClean(task.task_id);
          }
        }}
      />
    </TableCell>
    <TableCell onClick={(e) => e.stopPropagation()}>
      {task.type === 'milestone' ? (
        <span className="text-xs text-muted-foreground">{task.end_date || '—'}</span>
      ) : (
        <Input
          type="date"
          className="h-8 w-36"
          defaultValue={task.end_date || ''}
          onChange={() => onMarkDirty(task.task_id)}
          onBlur={(e) => {
            const val = e.target.value || null;
            if (val !== (task.end_date || null)) {
              onFieldChange(task, 'end_date', val);
            } else {
              onMarkClean(task.task_id);
            }
          }}
        />
      )}
    </TableCell>
    <TableCell onClick={(e) => e.stopPropagation()}>
      <Select
        value={task.status}
        onValueChange={(v) => onFieldChange(task, 'status', v)}
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
    <TableCell onClick={(e) => e.stopPropagation()}>
      <Input
        className="h-8 min-w-[100px]"
        defaultValue={task.responsible_party || ''}
        onChange={() => onMarkDirty(task.task_id)}
        onBlur={(e) => {
          if (e.target.value !== (task.responsible_party || '')) {
            onFieldChange(task, 'responsible_party', e.target.value || null);
          } else {
            onMarkClean(task.task_id);
          }
        }}
      />
    </TableCell>
    <TableCell onClick={(e) => e.stopPropagation()}>
      <GanttDependencyPicker
        taskId={task.task_id}
        tasks={tasks}
        dependencies={task.dependencies || []}
        onChange={(deps) => onFieldChange(task, 'dependencies', deps)}
        disabled={saving === task.task_id}
      />
    </TableCell>
    <TableCell onClick={(e) => e.stopPropagation()}>
      <div className="flex gap-1">
        <Button
          variant="ghost"
          size="icon"
          className="h-7 w-7"
          title="Move up (Alt+↑)"
          onClick={() => onReorder(task.task_id, 'up')}
          disabled={task.order === 0}
        >
          <ArrowUp className="h-3 w-3" />
        </Button>
        <Button
          variant="ghost"
          size="icon"
          className="h-7 w-7"
          title="Move down (Alt+↓)"
          onClick={() => onReorder(task.task_id, 'down')}
          disabled={task.order === tasks.length - 1}
        >
          <ArrowDown className="h-3 w-3" />
        </Button>
        <Button
          variant="ghost"
          size="icon"
          className="h-7 w-7"
          title="Duplicate (⌘D)"
          onClick={() => onDuplicate(task)}
          disabled={saving === task.task_id}
        >
          <Copy className="h-3 w-3" />
        </Button>
        <Button
          variant="ghost"
          size="icon"
          className="h-7 w-7 text-destructive"
          title="Delete"
          onClick={() => onDelete(task.task_id)}
          disabled={saving === task.task_id}
        >
          <Trash2 className="h-3 w-3" />
        </Button>
      </div>
    </TableCell>
  </TableRow>
);

export const GanttTaskTable = ({
  projectId,
  tasks,
  loading,
  taskStatuses = [],
  taskTypes = ['task', 'milestone'],
  onRefresh,
  apiFetch,
  onSaveStatusChange,
}) => {
  const [saving, setSaving] = useState(null);
  const [newTask, setNewTask] = useState(emptyTask);
  const [adding, setAdding] = useState(false);
  const [bulkOpen, setBulkOpen] = useState(false);
  const [bulkText, setBulkText] = useState('');
  const [bulkAdding, setBulkAdding] = useState(false);
  const [shortcutsOpen, setShortcutsOpen] = useState(false);
  const [selectedId, setSelectedId] = useState(null);
  const [dirtyTaskIds, setDirtyTaskIds] = useState(new Set());
  const [collapsedPhases, setCollapsedPhases] = useState(new Set());
  const tableRef = useRef(null);
  const newTitleRef = useRef(null);

  const phaseGroups = useMemo(() => groupTasksByPhase(tasks), [tasks]);

  const isDirty = dirtyTaskIds.size > 0 || isNewTaskDirty(newTask);
  const isSaving = saving !== null || adding || bulkAdding;

  useEffect(() => {
    onSaveStatusChange?.({ saving: isSaving, dirty: isDirty });
  }, [isSaving, isDirty, onSaveStatusChange]);

  const markDirty = useCallback((taskId) => {
    setDirtyTaskIds((prev) => new Set(prev).add(taskId));
  }, []);

  const markClean = useCallback((taskId) => {
    setDirtyTaskIds((prev) => {
      const next = new Set(prev);
      next.delete(taskId);
      return next;
    });
  }, []);

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
      markClean(taskId);
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

  const handleSaveDates = (task, startDate) => {
    const updates = { start_date: startDate };
    if (task.type === 'milestone' && startDate) {
      updates.end_date = startDate;
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

  const handleDuplicate = async (task) => {
    setSaving(task.task_id);
    try {
      const payload = duplicateTaskPayload(task);
      const res = await apiFetch(`/gantt/projects/${projectId}/tasks`, {
        method: 'POST',
        body: JSON.stringify(payload),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(parseApiError(err, 'Failed to duplicate task'));
      }
      await onRefresh();
      toast.success('Task duplicated');
    } catch (error) {
      toast.error(error.message);
    } finally {
      setSaving(null);
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
      if (selectedId === taskId) setSelectedId(null);
      markClean(taskId);
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

  const handleBulkAdd = async () => {
    const { rows, errors } = parseBulkTaskRows(bulkText, { taskTypes, taskStatuses });
    if (errors.length) {
      errors.forEach((msg) => toast.error(msg));
      return;
    }
    if (!rows.length) {
      toast.error('Paste at least one row');
      return;
    }

    setBulkAdding(true);
    let added = 0;
    try {
      for (const row of rows) {
        const res = await apiFetch(`/gantt/projects/${projectId}/tasks`, {
          method: 'POST',
          body: JSON.stringify(row),
        });
        if (!res.ok) {
          const err = await res.json().catch(() => ({}));
          throw new Error(parseApiError(err, `Failed to add "${row.title}"`));
        }
        added += 1;
      }
      setBulkText('');
      setBulkOpen(false);
      await onRefresh();
      toast.success(`Added ${added} task${added === 1 ? '' : 's'}`);
    } catch (error) {
      toast.error(error.message);
      if (added > 0) await onRefresh();
    } finally {
      setBulkAdding(false);
    }
  };

  const togglePhase = (phase) => {
    setCollapsedPhases((prev) => {
      const next = new Set(prev);
      if (next.has(phase)) next.delete(phase);
      else next.add(phase);
      return next;
    });
  };

  const isInputTarget = (target) =>
    target.tagName === 'INPUT' ||
    target.tagName === 'TEXTAREA' ||
    target.isContentEditable ||
    target.closest('[role="combobox"]');

  const handleKeyDown = useCallback(
    (e) => {
      const inInput = isInputTarget(e.target);

      if ((e.metaKey || e.ctrlKey) && e.key === 'd' && selectedId) {
        e.preventDefault();
        const task = tasks.find((t) => t.task_id === selectedId);
        if (task) handleDuplicate(task);
        return;
      }

      if (e.altKey && (e.key === 'ArrowUp' || e.key === 'ArrowDown') && selectedId) {
        e.preventDefault();
        handleReorder(selectedId, e.key === 'ArrowUp' ? 'up' : 'down');
        return;
      }

      if (inInput) return;

      if (e.key === 'n' && !e.metaKey && !e.ctrlKey) {
        e.preventDefault();
        newTitleRef.current?.focus();
        return;
      }

      if ((e.key === 'Delete' || e.key === 'Backspace') && selectedId) {
        e.preventDefault();
        handleDelete(selectedId);
        return;
      }

      if (e.key === '?' || (e.shiftKey && e.key === '/')) {
        e.preventDefault();
        setShortcutsOpen(true);
      }
    },
    [selectedId, tasks]
  );

  useEffect(() => {
    const el = tableRef.current;
    if (!el) return;
    el.addEventListener('keydown', handleKeyDown);
    return () => el.removeEventListener('keydown', handleKeyDown);
  }, [handleKeyDown]);

  if (loading) {
    return (
      <div className="flex items-center justify-center py-12">
        <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
      </div>
    );
  }

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between gap-2">
        <p className="text-xs text-muted-foreground">
          {phaseGroups.length} phase{phaseGroups.length === 1 ? '' : 's'} · {tasks.length} task{tasks.length === 1 ? '' : 's'}
        </p>
        <div className="flex gap-2">
          <Button variant="outline" size="sm" onClick={() => setBulkOpen(true)}>
            <ClipboardPaste className="h-4 w-4 mr-1" />
            Bulk add
          </Button>
          <Button variant="ghost" size="sm" onClick={() => setShortcutsOpen(true)} title="Keyboard shortcuts">
            <Keyboard className="h-4 w-4" />
          </Button>
        </div>
      </div>

      <div
        ref={tableRef}
        tabIndex={0}
        className="overflow-x-auto rounded-lg border outline-none focus-visible:ring-2 focus-visible:ring-ring"
      >
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
              <TableHead className="w-28">Actions</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {phaseGroups.map(({ phase, tasks: phaseTasks }) => {
              const collapsed = collapsedPhases.has(phase);
              return (
                <Fragment key={phase}>
                  <TableRow className="bg-muted/40 hover:bg-muted/50">
                    <TableCell colSpan={10} className="py-2">
                      <button
                        type="button"
                        className="flex items-center gap-2 w-full text-left font-medium text-sm"
                        onClick={() => togglePhase(phase)}
                      >
                        {collapsed ? (
                          <ChevronRight className="h-4 w-4 shrink-0" />
                        ) : (
                          <ChevronDown className="h-4 w-4 shrink-0" />
                        )}
                        <span>{phase}</span>
                        <span className="text-xs text-muted-foreground font-normal">
                          ({phaseTasks.length})
                        </span>
                      </button>
                    </TableCell>
                  </TableRow>
                  {!collapsed &&
                    phaseTasks.map((task) => (
                      <TaskRow
                        key={`${task.task_id}-${task.updated_at}`}
                        task={task}
                        tasks={tasks}
                        taskTypes={taskTypes}
                        taskStatuses={taskStatuses}
                        saving={saving}
                        selected={selectedId === task.task_id}
                        onSelect={setSelectedId}
                        onFieldChange={handleFieldChange}
                        onSaveDates={handleSaveDates}
                        onReorder={handleReorder}
                        onDelete={handleDelete}
                        onDuplicate={handleDuplicate}
                        onMarkDirty={markDirty}
                        onMarkClean={markClean}
                      />
                    ))}
                </Fragment>
              );
            })}

            <TableRow className="bg-muted/20">
              <TableCell />
              <TableCell>
                <Select
                  value={newTask.type}
                  onValueChange={(v) =>
                    setNewTask((t) => ({
                      ...t,
                      type: v,
                      end_date: v === 'milestone' ? t.start_date : t.end_date,
                    }))
                  }
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
                  ref={newTitleRef}
                  className="h-8"
                  placeholder="New task title (press N to focus)"
                  value={newTask.title}
                  onChange={(e) => setNewTask((t) => ({ ...t, title: e.target.value }))}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter') {
                      e.preventDefault();
                      handleAddTask();
                    }
                  }}
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

      <Dialog open={bulkOpen} onOpenChange={setBulkOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Bulk add tasks</DialogTitle>
            <DialogDescription>
              Paste one task per line. Use tab or comma between columns:
              phase, title, start, end, type, status, responsible.
              A single column is treated as title only.
            </DialogDescription>
          </DialogHeader>
          <div>
            <Label htmlFor="bulk-paste">Task rows</Label>
            <Textarea
              id="bulk-paste"
              value={bulkText}
              onChange={(e) => setBulkText(e.target.value)}
              placeholder={`Planning\tKickoff meeting\t2025-01-15\t2025-01-15\nDesign\tWireframes\t2025-01-20\t2025-02-01`}
              rows={8}
              className="font-mono text-sm mt-1"
            />
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setBulkOpen(false)} disabled={bulkAdding}>
              Cancel
            </Button>
            <Button onClick={handleBulkAdd} disabled={bulkAdding}>
              {bulkAdding && <Loader2 className="h-4 w-4 mr-2 animate-spin" />}
              Add tasks
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog open={shortcutsOpen} onOpenChange={setShortcutsOpen}>
        <DialogContent className="max-w-sm">
          <DialogHeader>
            <DialogTitle>Keyboard shortcuts</DialogTitle>
            <DialogDescription>Click a task row to select it first.</DialogDescription>
          </DialogHeader>
          <dl className="space-y-2 text-sm">
            <div className="flex justify-between gap-4">
              <dt className="text-muted-foreground">Focus new task</dt>
              <dd className="font-mono">N</dd>
            </div>
            <div className="flex justify-between gap-4">
              <dt className="text-muted-foreground">Add new task</dt>
              <dd className="font-mono">Enter</dd>
            </div>
            <div className="flex justify-between gap-4">
              <dt className="text-muted-foreground">Duplicate selected</dt>
              <dd className="font-mono">⌘D</dd>
            </div>
            <div className="flex justify-between gap-4">
              <dt className="text-muted-foreground">Move selected up/down</dt>
              <dd className="font-mono">Alt+↑ / Alt+↓</dd>
            </div>
            <div className="flex justify-between gap-4">
              <dt className="text-muted-foreground">Delete selected</dt>
              <dd className="font-mono">Delete</dd>
            </div>
            <div className="flex justify-between gap-4">
              <dt className="text-muted-foreground">Show shortcuts</dt>
              <dd className="font-mono">?</dd>
            </div>
          </dl>
        </DialogContent>
      </Dialog>
    </div>
  );
};
