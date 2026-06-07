import { useState, useEffect } from 'react';
import { Button } from '../ui/button';
import { Input } from '../ui/input';
import { Label } from '../ui/label';
import { parseApiError } from './ganttApiUtils';
import { toast } from 'sonner';
import { X } from 'lucide-react';
import { normalizePhase } from './ganttTaskUtils';

export const GanttPhaseInspector = ({
  phase,
  tasks,
  projectId,
  apiFetch,
  onClose,
  onRefresh,
}) => {
  const [name, setName] = useState(phase);
  const [saving, setSaving] = useState(false);
  const phaseTasks = tasks.filter((t) => normalizePhase(t.phase) === phase);

  useEffect(() => {
    setName(phase);
  }, [phase]);

  const renamePhase = async (nextName) => {
    const trimmed = nextName.trim();
    if (!trimmed || trimmed === phase) return;
    setSaving(true);
    try {
      const results = await Promise.all(
        phaseTasks.map((task) =>
          apiFetch(`/gantt/projects/${projectId}/tasks/${task.task_id}`, {
            method: 'PATCH',
            body: JSON.stringify({ phase: trimmed }),
          })
        )
      );
      const failed = results.find((res) => !res.ok);
      if (failed) {
        const err = await failed.json().catch(() => ({}));
        throw new Error(parseApiError(err, 'Failed to rename phase'));
      }
      await onRefresh?.();
      toast.success('Phase renamed');
      onClose?.();
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
          Phase
        </span>
        <Button variant="ghost" size="icon" className="h-7 w-7" onClick={onClose}>
          <X className="h-3.5 w-3.5" />
        </Button>
      </div>
      <div className="p-3 space-y-3 text-sm">
        <div className="space-y-1">
          <Label className="text-xs">Phase name</Label>
          <Input
            className="h-8 text-sm"
            value={name}
            disabled={saving}
            onChange={(e) => setName(e.target.value)}
            onBlur={() => renamePhase(name)}
            onKeyDown={(e) => {
              if (e.key === 'Enter') renamePhase(name);
              if (e.key === 'Escape') onClose?.();
            }}
          />
        </div>
        <p className="text-xs text-muted-foreground">
          {phaseTasks.length} task{phaseTasks.length === 1 ? '' : 's'} in this phase.
          Renaming updates all tasks in the phase.
        </p>
      </div>
    </aside>
  );
};
