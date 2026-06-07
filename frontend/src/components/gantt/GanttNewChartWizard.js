import { useState } from 'react';
import { Button } from '../ui/button';
import { Input } from '../ui/input';
import { Label } from '../ui/label';
import { Textarea } from '../ui/textarea';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
  DialogDescription,
} from '../ui/dialog';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '../ui/select';
import { toast } from 'sonner';
import { ChevronLeft, ChevronRight, Loader2, Plus, Trash2 } from 'lucide-react';
import { parseApiError } from './ganttApiUtils';
import { cn } from '../../lib/utils';

const STEPS = ['title', 'phases', 'tasks'];

const emptyWizardTask = () => ({
  phase: '',
  title: '',
  type: 'task',
  start_date: '',
  end_date: '',
});

export const GanttNewChartWizard = ({
  open,
  onOpenChange,
  apiFetch,
  onCreated,
  taskTypes = ['task', 'milestone'],
}) => {
  const [step, setStep] = useState(0);
  const [title, setTitle] = useState('');
  const [description, setDescription] = useState('');
  const [phases, setPhases] = useState(['']);
  const [tasks, setTasks] = useState([emptyWizardTask()]);
  const [creating, setCreating] = useState(false);

  const reset = () => {
    setStep(0);
    setTitle('');
    setDescription('');
    setPhases(['']);
    setTasks([emptyWizardTask()]);
  };

  const handleOpenChange = (next) => {
    if (!next) reset();
    onOpenChange(next);
  };

  const phaseOptions = phases.map((p) => p.trim()).filter(Boolean);

  const addPhase = () => setPhases((prev) => [...prev, '']);

  const removePhase = (index) => {
    setPhases((prev) => (prev.length <= 1 ? [''] : prev.filter((_, i) => i !== index)));
  };

  const addTaskRow = () => setTasks((prev) => [...prev, emptyWizardTask()]);

  const removeTaskRow = (index) => {
    setTasks((prev) => (prev.length <= 1 ? [emptyWizardTask()] : prev.filter((_, i) => i !== index)));
  };

  const canAdvance = () => {
    if (step === 0) return title.trim().length > 0;
    return true;
  };

  const handleNext = () => {
    if (step === 0 && !title.trim()) {
      toast.error('Chart title is required');
      return;
    }
    setStep((s) => Math.min(s + 1, STEPS.length - 1));
  };

  const handleBack = () => setStep((s) => Math.max(s - 1, 0));

  const handleCreate = async () => {
    const taskRows = tasks.filter((t) => t.title.trim());
    const milestoneWithoutDate = taskRows.find(
      (t) => t.type === 'milestone' && !t.start_date
    );
    if (milestoneWithoutDate) {
      toast.error(`Milestone "${milestoneWithoutDate.title}" requires a start date`);
      return;
    }
    setCreating(true);
    let createdProjectId = null;
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
      createdProjectId = project.gantt_project_id;

      for (const task of taskRows) {
        const startDate = task.start_date || null;
        const endDate =
          task.type === 'milestone' && startDate
            ? startDate
            : task.end_date || null;
        const payload = {
          type: task.type,
          phase: task.phase || null,
          title: task.title.trim(),
          description: null,
          start_date: startDate,
          end_date: endDate,
          responsible_party: null,
          dependencies: [],
        };
        const taskRes = await apiFetch(`/gantt/projects/${createdProjectId}/tasks`, {
          method: 'POST',
          body: JSON.stringify(payload),
        });
        if (!taskRes.ok) {
          const err = await taskRes.json().catch(() => ({}));
          throw new Error(parseApiError(err, `Failed to add task "${task.title}"`));
        }
      }

      handleOpenChange(false);
      await onCreated(createdProjectId);
      toast.success(
        taskRows.length
          ? `Chart created with ${taskRows.length} task${taskRows.length === 1 ? '' : 's'}`
          : 'Chart created'
      );
    } catch (error) {
      if (createdProjectId) {
        await apiFetch(`/gantt/projects/${createdProjectId}`, { method: 'DELETE' }).catch(() => {});
      }
      toast.error(error.message);
    } finally {
      setCreating(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <DialogContent className="max-w-lg">
        <DialogHeader>
          <DialogTitle>New chart</DialogTitle>
          <DialogDescription>
            Step {step + 1} of {STEPS.length}:{' '}
            {step === 0 ? 'Name your chart' : step === 1 ? 'Define phases' : 'Add initial tasks'}
          </DialogDescription>
        </DialogHeader>

        <div className="flex gap-2 mb-2">
          {STEPS.map((_, i) => (
            <div
              key={STEPS[i]}
              className={cn(
                'h-1 flex-1 rounded-full transition-colors',
                i <= step ? 'bg-primary' : 'bg-muted'
              )}
            />
          ))}
        </div>

        {step === 0 && (
          <div className="space-y-4">
            <div>
              <Label htmlFor="wizard-title">Chart title</Label>
              <Input
                id="wizard-title"
                value={title}
                onChange={(e) => setTitle(e.target.value)}
                placeholder="e.g. Product launch Q3"
                autoFocus
              />
            </div>
            <div>
              <Label htmlFor="wizard-desc">Description (optional)</Label>
              <Textarea
                id="wizard-desc"
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                placeholder="Brief description"
                rows={3}
              />
            </div>
          </div>
        )}

        {step === 1 && (
          <div className="space-y-3">
            <p className="text-sm text-muted-foreground">
              Add phase names to group tasks. You can skip this and add phases later in the table.
            </p>
            {phases.map((phase, index) => (
              <div key={index} className="flex gap-2">
                <Input
                  value={phase}
                  onChange={(e) =>
                    setPhases((prev) => prev.map((p, i) => (i === index ? e.target.value : p)))
                  }
                  placeholder={`Phase ${index + 1}`}
                />
                <Button
                  type="button"
                  variant="ghost"
                  size="icon"
                  onClick={() => removePhase(index)}
                  disabled={phases.length <= 1}
                >
                  <Trash2 className="h-4 w-4" />
                </Button>
              </div>
            ))}
            <Button type="button" variant="outline" size="sm" onClick={addPhase}>
              <Plus className="h-4 w-4 mr-1" />
              Add phase
            </Button>
          </div>
        )}

        {step === 2 && (
          <div className="space-y-3 max-h-72 overflow-y-auto pr-1">
            <p className="text-sm text-muted-foreground">
              Add tasks now or leave blank and build in the table. Only rows with a title are saved.
              Milestones require a start date.
            </p>
            {tasks.map((task, index) => (
              <div key={index} className="flex flex-wrap gap-2 items-end border rounded-lg p-3">
                {phaseOptions.length > 0 ? (
                  <div className="w-32">
                    <Label className="text-xs">Phase</Label>
                    <Select
                      value={task.phase || '__none__'}
                      onValueChange={(v) =>
                        setTasks((prev) =>
                          prev.map((t, i) =>
                            i === index ? { ...t, phase: v === '__none__' ? '' : v } : t
                          )
                        )
                      }
                    >
                      <SelectTrigger className="h-8">
                        <SelectValue placeholder="Phase" />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="__none__">—</SelectItem>
                        {phaseOptions.map((p) => (
                          <SelectItem key={p} value={p}>{p}</SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </div>
                ) : (
                  <div className="w-28">
                    <Label className="text-xs">Phase</Label>
                    <Input
                      className="h-8"
                      value={task.phase}
                      onChange={(e) =>
                        setTasks((prev) =>
                          prev.map((t, i) => (i === index ? { ...t, phase: e.target.value } : t))
                        )
                      }
                      placeholder="Phase"
                    />
                  </div>
                )}
                <div className="flex-1 min-w-[120px]">
                  <Label className="text-xs">Title</Label>
                  <Input
                    className="h-8"
                    value={task.title}
                    onChange={(e) =>
                      setTasks((prev) =>
                        prev.map((t, i) => (i === index ? { ...t, title: e.target.value } : t))
                      )
                    }
                    placeholder="Task title"
                  />
                </div>
                <div className="w-24">
                  <Label className="text-xs">Type</Label>
                  <Select
                    value={task.type}
                    onValueChange={(v) =>
                      setTasks((prev) =>
                        prev.map((t, i) =>
                          i === index
                            ? {
                                ...t,
                                type: v,
                                end_date: v === 'milestone' ? t.start_date : t.end_date,
                              }
                            : t
                        )
                      )
                    }
                  >
                    <SelectTrigger className="h-8">
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
                </div>
                <div className="w-32">
                  <Label className="text-xs">
                    Start{task.type === 'milestone' ? ' (required)' : ''}
                  </Label>
                  <Input
                    type="date"
                    className="h-8"
                    value={task.start_date}
                    onChange={(e) =>
                      setTasks((prev) =>
                        prev.map((t, i) =>
                          i === index
                            ? {
                                ...t,
                                start_date: e.target.value,
                                end_date: t.type === 'milestone' ? e.target.value : t.end_date,
                              }
                            : t
                        )
                      )
                    }
                  />
                </div>
                {task.type !== 'milestone' && (
                  <div className="w-32">
                    <Label className="text-xs">End</Label>
                    <Input
                      type="date"
                      className="h-8"
                      value={task.end_date}
                      onChange={(e) =>
                        setTasks((prev) =>
                          prev.map((t, i) =>
                            i === index ? { ...t, end_date: e.target.value } : t
                          )
                        )
                      }
                    />
                  </div>
                )}
                <Button
                  type="button"
                  variant="ghost"
                  size="icon"
                  className="h-8 w-8"
                  onClick={() => removeTaskRow(index)}
                  disabled={tasks.length <= 1}
                >
                  <Trash2 className="h-4 w-4" />
                </Button>
              </div>
            ))}
            <Button type="button" variant="outline" size="sm" onClick={addTaskRow}>
              <Plus className="h-4 w-4 mr-1" />
              Add task row
            </Button>
          </div>
        )}

        <DialogFooter className="gap-2 sm:gap-0">
          {step > 0 && (
            <Button type="button" variant="outline" onClick={handleBack} disabled={creating}>
              <ChevronLeft className="h-4 w-4 mr-1" />
              Back
            </Button>
          )}
          <div className="flex-1" />
          <Button type="button" variant="outline" onClick={() => handleOpenChange(false)} disabled={creating}>
            Cancel
          </Button>
          {step < STEPS.length - 1 ? (
            <Button type="button" onClick={handleNext} disabled={!canAdvance()}>
              Next
              <ChevronRight className="h-4 w-4 ml-1" />
            </Button>
          ) : (
            <Button type="button" onClick={handleCreate} disabled={creating}>
              {creating && <Loader2 className="h-4 w-4 mr-2 animate-spin" />}
              Create chart
            </Button>
          )}
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
};
