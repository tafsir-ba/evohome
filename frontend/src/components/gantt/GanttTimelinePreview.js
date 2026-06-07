import { useState, useRef, useCallback, useMemo, useEffect } from 'react';
import { cn } from '../../lib/utils';
import { groupTasksByPhase } from './ganttTaskUtils';
import { parseApiError } from './ganttApiUtils';
import { toast } from 'sonner';
import {
  PHASE_BAR_COLORS,
  parseGanttDate,
  formatIsoDate,
  diffDays,
  computeTimelineRange,
  barMetrics,
  applyDragDelta,
  monthTicks,
} from './ganttTimelineUtils';

const LABEL_WIDTH = 160;
const ROW_HEIGHT = 20;
const PHASE_HEIGHT = 18;
const HANDLE_WIDTH = 6;

const GanttBar = ({
  task,
  metrics,
  barColor,
  isActive,
  previewDates,
  onHover,
  onDragStart,
}) => {
  const displayStart = previewDates?.start_date || task.start_date;
  const displayEnd = previewDates?.end_date || task.end_date || task.start_date;
  const isMilestone = task.type === 'milestone';

  return (
    <div
      className="relative flex-1 h-full"
      onMouseEnter={() => onHover(task.task_id)}
      onMouseLeave={() => onHover(null)}
    >
      <div
        className={cn(
          'absolute top-1/2 -translate-y-1/2 group',
          isMilestone ? 'h-3 w-3' : 'h-3.5 min-w-[4px]',
          isActive && 'z-20'
        )}
        style={{
          left: `${metrics.leftPct}%`,
          width: isMilestone ? undefined : `${Math.max(metrics.widthPct, 0.4)}%`,
        }}
      >
        {isActive && (
          <div className="absolute -top-5 left-1/2 -translate-x-1/2 whitespace-nowrap rounded bg-foreground text-background px-1.5 py-0.5 text-[9px] font-medium z-30 pointer-events-none">
            {displayStart}
            {!isMilestone && displayEnd !== displayStart ? ` → ${displayEnd}` : ''}
          </div>
        )}

        {!isMilestone && (
          <div
            className={cn(
              'absolute left-0 top-0 bottom-0 w-1.5 rounded-l cursor-ew-resize opacity-0 group-hover:opacity-100',
              isActive && 'opacity-100 bg-black/20'
            )}
            style={{ width: HANDLE_WIDTH }}
            onMouseDown={(e) => onDragStart(e, task, 'resize-start')}
          />
        )}

        <div
          className={cn(
            'h-full w-full rounded-sm border border-black/10 shadow-sm',
            barColor,
            isMilestone && 'rotate-45 rounded-[1px]',
            !isMilestone && 'cursor-grab active:cursor-grabbing'
          )}
          onMouseDown={(e) => onDragStart(e, task, 'move')}
          title={task.title}
        />

        {!isMilestone && (
          <div
            className={cn(
              'absolute right-0 top-0 bottom-0 rounded-r cursor-ew-resize opacity-0 group-hover:opacity-100',
              isActive && 'opacity-100 bg-black/20'
            )}
            style={{ width: HANDLE_WIDTH }}
            onMouseDown={(e) => onDragStart(e, task, 'resize-end')}
          />
        )}
      </div>
    </div>
  );
};

export const GanttTimelinePreview = ({
  tasks,
  projectId,
  apiFetch,
  onTasksChange,
  onSaving,
  onRevert,
}) => {
  const trackRef = useRef(null);
  const dragPreviewRef = useRef(null);
  const [hoveredId, setHoveredId] = useState(null);
  const [dragging, setDragging] = useState(null);
  const [previews, setPreviews] = useState({});

  const datedTasks = useMemo(() => tasks.filter((t) => t.start_date), [tasks]);
  const { minDate, maxDate, totalDays } = useMemo(
    () => computeTimelineRange(datedTasks),
    [datedTasks]
  );
  const phaseGroups = useMemo(() => groupTasksByPhase(datedTasks), [datedTasks]);
  const ticks = useMemo(
    () => (minDate && maxDate ? monthTicks(minDate, maxDate) : []),
    [minDate, maxDate]
  );
  const phaseColorMap = useMemo(
    () =>
      Object.fromEntries(
        phaseGroups.map((g, i) => [g.phase, PHASE_BAR_COLORS[i % PHASE_BAR_COLORS.length]])
      ),
    [phaseGroups]
  );

  const getTrackWidth = () => trackRef.current?.offsetWidth || 1;

  const commitDates = useCallback(
    async (task, dates) => {
      if (!projectId || !dates) return;
      onSaving?.(true);
      try {
        const res = await apiFetch(`/gantt/projects/${projectId}/tasks/${task.task_id}`, {
          method: 'PATCH',
          body: JSON.stringify(dates),
        });
        if (!res.ok) {
          const err = await res.json().catch(() => ({}));
          throw new Error(parseApiError(err, 'Failed to update dates'));
        }
      } catch (error) {
        toast.error(error.message);
        throw error;
      } finally {
        onSaving?.(false);
      }
    },
    [apiFetch, projectId, onSaving]
  );

  const handleDragStart = useCallback(
    (event, task, mode) => {
      event.preventDefault();
      event.stopPropagation();

      const startX = event.clientX;
      const originStart = parseGanttDate(task.start_date);
      const originEnd = parseGanttDate(task.end_date || task.start_date);
      if (!originStart || !originEnd || !minDate) return;

      setDragging({ taskId: task.task_id, mode });
      setHoveredId(task.task_id);

      const onMove = (e) => {
        const deltaX = e.clientX - startX;
        const deltaDays = Math.round(deltaX / (getTrackWidth() / totalDays));
        if (deltaDays === 0) return;

        const next = applyDragDelta(
          {
            ...task,
            start_date: formatIsoDate(originStart),
            end_date: formatIsoDate(originEnd),
          },
          mode,
          deltaDays,
          minDate,
          maxDate
        );
        if (!next) return;

        dragPreviewRef.current = next;
        setPreviews((prev) => ({ ...prev, [task.task_id]: next }));
        onTasksChange?.(
          tasks.map((t) => (t.task_id === task.task_id ? { ...t, ...next } : t))
        );
      };

      const onUp = async () => {
        document.removeEventListener('mousemove', onMove);
        document.removeEventListener('mouseup', onUp);
        setDragging(null);

        const finalDates = dragPreviewRef.current;
        dragPreviewRef.current = null;
        setPreviews((prev) => {
          const next = { ...prev };
          delete next[task.task_id];
          return next;
        });

        if (!finalDates) return;

        try {
          await commitDates(task, finalDates);
        } catch {
          onRevert?.();
        }
      };

      document.addEventListener('mousemove', onMove);
      document.addEventListener('mouseup', onUp);
    },
    [minDate, maxDate, totalDays, tasks, onTasksChange, commitDates, onRevert]
  );

  useEffect(() => {
    if (!dragging) return;
    const cancel = () => setDragging(null);
    window.addEventListener('blur', cancel);
    return () => window.removeEventListener('blur', cancel);
  }, [dragging]);

  if (!phaseGroups.length || !minDate) {
    return (
      <div className="rounded border bg-muted/20 px-3 py-4 text-center text-[11px] text-muted-foreground">
        Add start dates to tasks to use the Gantt chart.
      </div>
    );
  }

  return (
    <div className="w-full rounded border bg-card overflow-hidden">
      <div className="flex border-b bg-muted/30 text-[9px] text-muted-foreground">
        <div className="shrink-0 border-r px-1.5 py-0.5" style={{ width: LABEL_WIDTH }}>
          Task
        </div>
        <div className="relative flex-1 min-w-0 h-4" ref={trackRef}>
          {ticks.map((tick) => {
            const leftPct = (diffDays(tick.date, minDate) / totalDays) * 100;
            return (
              <span
                key={tick.label + tick.date.toISOString()}
                className="absolute top-0.5 -translate-x-1/2 whitespace-nowrap"
                style={{ left: `${Math.max(0, Math.min(100, leftPct))}%` }}
              >
                {tick.label}
              </span>
            );
          })}
        </div>
      </div>

      <div className="max-h-[min(70vh,720px)] overflow-y-auto overflow-x-hidden">
        {phaseGroups.map(({ phase, tasks: phaseTasks }) => {
          const barColor = phaseColorMap[phase] || PHASE_BAR_COLORS[0];
          const datedInPhase = phaseTasks.filter((t) => t.start_date);
          if (!datedInPhase.length) return null;

          return (
            <div key={phase}>
              <div
                className="flex items-center border-b bg-muted/20 text-[9px] font-semibold uppercase tracking-wide text-muted-foreground"
                style={{ height: PHASE_HEIGHT }}
              >
                <div
                  className="shrink-0 flex items-center gap-1 px-1.5 border-r truncate"
                  style={{ width: LABEL_WIDTH }}
                >
                  <span className={cn('h-1.5 w-1.5 rounded-sm shrink-0', barColor)} />
                  <span className="truncate">{phase}</span>
                </div>
                <div className="flex-1" />
              </div>

              {datedInPhase.map((task) => {
                const effectiveTask = previews[task.task_id]
                  ? { ...task, ...previews[task.task_id] }
                  : task;
                const metrics = barMetrics(effectiveTask, minDate, totalDays);
                if (!metrics) return null;

                const isActive =
                  hoveredId === task.task_id || dragging?.taskId === task.task_id;

                return (
                  <div
                    key={task.task_id}
                    className="flex items-center border-b border-border/40 hover:bg-muted/10"
                    style={{ height: ROW_HEIGHT }}
                  >
                    <div
                      className="shrink-0 truncate text-[10px] text-muted-foreground px-1.5 border-r"
                      style={{ width: LABEL_WIDTH, lineHeight: `${ROW_HEIGHT}px` }}
                      title={task.title}
                    >
                      {task.title}
                    </div>
                    <GanttBar
                      task={task}
                      metrics={metrics}
                      barColor={barColor}
                      isActive={isActive}
                      previewDates={previews[task.task_id]}
                      onHover={setHoveredId}
                      onDragStart={handleDragStart}
                    />
                  </div>
                );
              })}
            </div>
          );
        })}
      </div>

      <div className="flex border-t bg-muted/20 text-[9px] text-muted-foreground px-1.5 py-0.5">
        <span style={{ width: LABEL_WIDTH }} className="shrink-0" />
        <div className="flex-1 flex justify-between">
          <span>{formatIsoDate(minDate)}</span>
          <span>{formatIsoDate(maxDate)}</span>
        </div>
      </div>
    </div>
  );
};
