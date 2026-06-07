import { useState } from 'react';
import { Button } from '../ui/button';
import { Badge } from '../ui/badge';
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from '../ui/dialog';
import { Link2, X } from 'lucide-react';

export const GanttDependencyPicker = ({
  taskId,
  tasks,
  dependencies = [],
  onChange,
  disabled = false,
}) => {
  const [open, setOpen] = useState(false);
  const [selected, setSelected] = useState(
    dependencies.map((d) => d.task_id)
  );

  const candidates = tasks.filter((t) => t.task_id !== taskId);

  const handleOpen = () => {
    setSelected(dependencies.map((d) => d.task_id));
    setOpen(true);
  };

  const toggle = (id) => {
    setSelected((prev) =>
      prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id]
    );
  };

  const handleSave = () => {
    onChange(selected.map((id) => ({ task_id: id, type: 'finish_to_start' })));
    setOpen(false);
  };

  const removeDep = (id) => {
    onChange(dependencies.filter((d) => d.task_id !== id));
  };

  const labelFor = (id) => {
    const task = tasks.find((t) => t.task_id === id);
    return task ? task.title : id;
  };

  return (
    <div className="flex flex-wrap items-center gap-1">
      {dependencies.map((dep) => (
        <Badge key={dep.task_id} variant="secondary" className="text-xs gap-1">
          {labelFor(dep.task_id)}
          {!disabled && (
            <button
              type="button"
              onClick={() => removeDep(dep.task_id)}
              className="hover:text-destructive"
            >
              <X className="h-3 w-3" />
            </button>
          )}
        </Badge>
      ))}
      {!disabled && candidates.length > 0 && (
        <Button type="button" variant="ghost" size="sm" onClick={handleOpen}>
          <Link2 className="h-3 w-3 mr-1" />
          Add
        </Button>
      )}

      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Select dependencies (finish-to-start)</DialogTitle>
          </DialogHeader>
          <div className="space-y-2 max-h-60 overflow-y-auto">
            {candidates.map((task) => (
              <label
                key={task.task_id}
                className="flex items-center gap-2 p-2 rounded hover:bg-muted cursor-pointer"
              >
                <input
                  type="checkbox"
                  checked={selected.includes(task.task_id)}
                  onChange={() => toggle(task.task_id)}
                />
                <span className="text-sm">{task.title}</span>
              </label>
            ))}
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setOpen(false)}>
              Cancel
            </Button>
            <Button onClick={handleSave}>Save</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
};
