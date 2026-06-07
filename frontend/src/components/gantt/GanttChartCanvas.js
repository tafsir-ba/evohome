import { useEffect, useRef, useMemo, useCallback } from 'react';
import Gantt from 'frappe-gantt';
import { parseApiError } from './ganttApiUtils';
import { toFrappeTasks, frappeDateToIso } from './ganttCanvasUtils';
import { toast } from 'sonner';

const VIEW_MODES = ['Day', 'Week', 'Month'];

export const GanttChartCanvas = ({
  tasks,
  projectId,
  apiFetch,
  onTasksChange,
  onSaving,
  onRevert,
  viewMode = 'Week',
}) => {
  const containerRef = useRef(null);
  const ganttRef = useRef(null);
  const tasksRef = useRef(tasks);
  const viewModeRef = useRef(viewMode);

  const frappeTasks = useMemo(() => toFrappeTasks(tasks), [tasks]);

  useEffect(() => {
    tasksRef.current = tasks;
  }, [tasks]);

  useEffect(() => {
    viewModeRef.current = viewMode;
  }, [viewMode]);

  const commitDates = useCallback(
    async (taskId, startDate, endDate) => {
      if (!projectId) return;
      onSaving?.(true);
      try {
        const res = await apiFetch(`/gantt/projects/${projectId}/tasks/${taskId}`, {
          method: 'PATCH',
          body: JSON.stringify({ start_date: startDate, end_date: endDate }),
        });
        if (!res.ok) {
          const err = await res.json().catch(() => ({}));
          throw new Error(parseApiError(err, 'Failed to update dates'));
        }
        const updated = await res.json();
        onTasksChange?.(
          tasksRef.current.map((t) => (t.task_id === taskId ? updated : t))
        );
      } catch (error) {
        toast.error(error.message);
        onRevert?.();
        throw error;
      } finally {
        onSaving?.(false);
      }
    },
    [apiFetch, projectId, onSaving, onTasksChange, onRevert]
  );

  const handleDateChange = useCallback(
    async (task, start, end) => {
      const source = tasksRef.current.find((t) => t.task_id === task.id);
      if (!source) return;

      const startIso = frappeDateToIso(start);
      const endIso = frappeDateToIso(end);
      const payload =
        source.type === 'milestone'
          ? { start_date: startIso, end_date: startIso }
          : { start_date: startIso, end_date: endIso };

      try {
        await commitDates(task.id, payload.start_date, payload.end_date);
      } catch {
        // commitDates reverts via onRevert
      }
    },
    [commitDates]
  );

  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;

    if (!frappeTasks.length) {
      container.innerHTML = '';
      ganttRef.current = null;
      return;
    }

    const mode = VIEW_MODES.includes(viewMode) ? viewMode : 'Week';

    if (ganttRef.current) {
      ganttRef.current.refresh(frappeTasks);
      if (viewModeRef.current !== mode) {
        ganttRef.current.change_view_mode(mode);
      }
      return;
    }

    ganttRef.current = new Gantt(container, frappeTasks, {
      view_mode: mode,
      bar_height: 22,
      padding: 14,
      date_format: 'YYYY-MM-DD',
      language: 'en',
      on_date_change: (task, start, end) => {
        handleDateChange(task, start, end);
      },
    });

    return () => {
      container.innerHTML = '';
      ganttRef.current = null;
    };
  }, [frappeTasks, viewMode, handleDateChange]);

  if (!frappeTasks.length) {
    return (
      <div className="rounded border bg-muted/20 px-3 py-4 text-center text-[11px] text-muted-foreground">
        Add start dates to tasks to render the Gantt chart.
      </div>
    );
  }

  return (
    <div className="w-full rounded border bg-card overflow-x-auto gantt-canvas-root">
      <div ref={containerRef} className="min-w-[640px]" />
    </div>
  );
};
