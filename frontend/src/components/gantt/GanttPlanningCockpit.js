import { useState, useRef, useCallback, useMemo, useEffect } from 'react';
import { cn } from '../../lib/utils';
import { PHASE_BAR_COLORS } from './ganttTimelineUtils';
import {
  parseGanttDate,
  formatIsoDate,
  diffDays,
  applyDragDelta,
} from './ganttTimelineUtils';
import { parseApiError } from './ganttApiUtils';
import { GanttTaskInspector } from './GanttTaskInspector';
import { GanttPhaseInspector } from './GanttPhaseInspector';
import { groupTasksByPhase } from './ganttTaskUtils';
import {
  LEFT_PANEL_WIDTH,
  TASK_ROW_HEIGHT,
  PHASE_ROW_HEIGHT,
  HANDLE_WIDTH,
  buildCockpitRows,
  buildRowLayout,
  mergeTaskPreviews,
  computePhaseSpan,
  getTimelineLayout,
  buildZoomTicks,
  buildDependencyPaths,
  connectorPointForTask,
  rowHeightFor,
  barPixels,
  initialsFor,
  buildStatusDotMap,
} from './ganttCockpitUtils';
import { toast } from 'sonner';
import {
  ChevronDown,
  ChevronRight,
  Diamond,
  Link2,
} from 'lucide-react';

const TimelineBar = ({
  task,
  barColor,
  px,
  isActive,
  previewDates,
  onHover,
  onSelect,
  onDragStart,
  onDepDragStart,
}) => {
  const displayStart = previewDates?.start_date || task.start_date;
  const displayEnd = previewDates?.end_date || task.end_date || task.start_date;
  const isMilestone = task.type === 'milestone';

  if (!px) {
    return <div className="relative flex-1 h-full bg-muted/5" />;
  }

  return (
    <div
      className="relative flex-1 h-full"
      onMouseEnter={() => onHover(task.task_id)}
      onMouseLeave={() => onHover(null)}
      onClick={(e) => {
        e.stopPropagation();
        onSelect(task.task_id);
      }}
    >
      <div
        className={cn(
          'absolute top-1/2 -translate-y-1/2 group',
          isMilestone ? 'h-2.5 w-2.5' : 'h-3 min-w-[4px]',
          isActive && 'z-20'
        )}
        style={{ left: px.left, width: isMilestone ? undefined : px.width }}
      >
        {isActive && displayStart && (
          <div className="absolute -top-5 left-1/2 -translate-x-1/2 whitespace-nowrap rounded bg-foreground text-background px-1.5 py-0.5 text-[9px] font-medium z-30 pointer-events-none">
            {displayStart}
            {!isMilestone && displayEnd !== displayStart ? ` → ${displayEnd}` : ''}
          </div>
        )}

        {!isMilestone && (
          <div
            className={cn(
              'absolute left-0 top-0 bottom-0 rounded-l cursor-ew-resize opacity-0 group-hover:opacity-100',
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
        />

        {!isMilestone && (
          <>
            <div
              className={cn(
                'absolute right-0 top-0 bottom-0 rounded-r cursor-ew-resize opacity-0 group-hover:opacity-100',
                isActive && 'opacity-100 bg-black/20'
              )}
              style={{ width: HANDLE_WIDTH }}
              onMouseDown={(e) => onDragStart(e, task, 'resize-end')}
            />
            <button
              type="button"
              className="absolute -right-1 top-1/2 -translate-y-1/2 h-2 w-2 rounded-full bg-primary border border-background opacity-0 group-hover:opacity-100 z-10"
              title="Drag to link dependency"
              onMouseDown={(e) => {
                e.stopPropagation();
                onDepDragStart(e, task);
              }}
            />
          </>
        )}
      </div>
    </div>
  );
};

export const GanttPlanningCockpit = ({
  tasks,
  projectId,
  apiFetch,
  taskStatuses,
  taskTypes,
  zoom = 'Week',
  fitToScreen = false,
  onTasksChange,
  onSaving,
  onSaveStatusChange,
  onRevert,
  onRefresh,
}) => {
  const scrollRef = useRef(null);
  const timelineHeaderRef = useRef(null);
  const timelineBodyRef = useRef(null);
  const dragPreviewRef = useRef(null);
  const skipBlurSaveRef = useRef(false);

  const [collapsedPhases, setCollapsedPhases] = useState(new Set());
  const [selectedId, setSelectedId] = useState(null);
  const [selectedPhase, setSelectedPhase] = useState(null);
  const [hoveredId, setHoveredId] = useState(null);
  const [dragging, setDragging] = useState(null);
  const [previews, setPreviews] = useState({});
  const [editingTitleId, setEditingTitleId] = useState(null);
  const [titleDraft, setTitleDraft] = useState('');
  const [fitWidth, setFitWidth] = useState(null);
  const [depDrag, setDepDrag] = useState(null);

  const statusDotMap = useMemo(
    () => buildStatusDotMap(taskStatuses),
    [taskStatuses]
  );

  const rows = useMemo(
    () => buildCockpitRows(tasks, collapsedPhases),
    [tasks, collapsedPhases]
  );

  const phaseColorMap = useMemo(() => {
    const groups = groupTasksByPhase(tasks);
    return Object.fromEntries(
      groups.map((g, i) => [g.phase, PHASE_BAR_COLORS[i % PHASE_BAR_COLORS.length]])
    );
  }, [tasks]);

  const layout = useMemo(
    () => getTimelineLayout(tasks, zoom, fitToScreen ? fitWidth : null),
    [tasks, zoom, fitToScreen, fitWidth]
  );

  const { minDate, totalDays, pxPerDay, timelineWidth } = layout;
  const ticks = useMemo(
    () => buildZoomTicks(minDate, layout.maxDate, zoom),
    [minDate, layout.maxDate, zoom]
  );

  const rowOffsets = useMemo(() => {
    let y = 0;
    return rows.map((row) => {
      const top = y;
      y += rowHeightFor(row);
      return top;
    });
  }, [rows]);

  const totalBodyHeight = rows.reduce((sum, row) => sum + rowHeightFor(row), 0);

  const dependencyLayout = useMemo(
    () => buildRowLayout(buildCockpitRows(tasks, new Set())),
    [tasks]
  );

  const effectiveTasks = useMemo(
    () => mergeTaskPreviews(tasks, previews),
    [tasks, previews]
  );

  const timelineContentHeight = Math.max(totalBodyHeight, dependencyLayout.totalHeight);

  const dependencyPaths = useMemo(() => {
    if (!minDate) return [];
    return buildDependencyPaths(
      effectiveTasks,
      dependencyLayout,
      minDate,
      pxPerDay,
      totalDays
    );
  }, [effectiveTasks, dependencyLayout, minDate, pxPerDay, totalDays]);

  useEffect(() => {
    onSaveStatusChange?.({ saving: Boolean(dragging), dirty: Boolean(editingTitleId) });
  }, [dragging, editingTitleId, onSaveStatusChange]);

  const selectedTask = tasks.find((t) => t.task_id === selectedId);

  useEffect(() => {
    if (!fitToScreen || !timelineBodyRef.current) return;
    const measure = () => setFitWidth(timelineBodyRef.current?.clientWidth || null);
    measure();
    window.addEventListener('resize', measure);
    return () => window.removeEventListener('resize', measure);
  }, [fitToScreen]);

  const syncHeaderScroll = useCallback(() => {
    if (timelineHeaderRef.current && timelineBodyRef.current) {
      timelineHeaderRef.current.scrollLeft = timelineBodyRef.current.scrollLeft;
    }
  }, []);

  const selectTask = useCallback((taskId) => {
    setSelectedId(taskId);
    setSelectedPhase(null);
  }, []);

  const selectPhase = useCallback((phase) => {
    setSelectedPhase(phase);
    setSelectedId(null);
    setEditingTitleId(null);
  }, []);

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
        const updated = await res.json();
        onTasksChange?.(tasks.map((t) => (t.task_id === task.task_id ? updated : t)));
      } catch (error) {
        toast.error(error.message);
        throw error;
      } finally {
        onSaving?.(false);
      }
    },
    [apiFetch, projectId, onSaving, onTasksChange, tasks]
  );

  const commitTitle = useCallback(
    async (taskId, title) => {
      if (!title.trim()) {
        toast.error('Title is required');
        return;
      }
      onSaving?.(true);
      try {
        const res = await apiFetch(`/gantt/projects/${projectId}/tasks/${taskId}`, {
          method: 'PATCH',
          body: JSON.stringify({ title: title.trim() }),
        });
        if (!res.ok) {
          const err = await res.json().catch(() => ({}));
          throw new Error(parseApiError(err, 'Failed to update title'));
        }
        await onRefresh?.();
      } catch (error) {
        toast.error(error.message);
      } finally {
        onSaving?.(false);
      }
    },
    [apiFetch, projectId, onSaving, onRefresh]
  );

  const addDependency = useCallback(
    async (fromTaskId, toTaskId) => {
      if (fromTaskId === toTaskId) return;
      const target = tasks.find((t) => t.task_id === toTaskId);
      if (!target) return;
      const existing = (target.dependencies || []).map((d) => d.task_id);
      if (existing.includes(fromTaskId)) return;

      onSaving?.(true);
      try {
        const res = await apiFetch(`/gantt/projects/${projectId}/tasks/${toTaskId}`, {
          method: 'PATCH',
          body: JSON.stringify({
            dependencies: [
              ...(target.dependencies || []),
              { task_id: fromTaskId, type: 'finish_to_start' },
            ],
          }),
        });
        if (!res.ok) {
          const err = await res.json().catch(() => ({}));
          throw new Error(parseApiError(err, 'Invalid dependency'));
        }
        await onRefresh?.();
      } catch (error) {
        toast.error(error.message);
      } finally {
        onSaving?.(false);
      }
    },
    [apiFetch, projectId, onSaving, onRefresh, tasks]
  );

  const handleDragStart = useCallback(
    (event, task, mode) => {
      event.preventDefault();
      event.stopPropagation();

      const originStart = parseGanttDate(task.start_date);
      const originEnd = parseGanttDate(task.end_date || task.start_date);
      if (!originStart || !originEnd || !minDate) return;

      const startX = event.clientX;
      setDragging({ taskId: task.task_id, mode });
      setHoveredId(task.task_id);

      const onMove = (e) => {
        const deltaX = e.clientX - startX;
        const deltaDays = Math.round(deltaX / pxPerDay);
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
          layout.maxDate
        );
        if (!next) return;

        dragPreviewRef.current = next;
        setPreviews((prev) => ({ ...prev, [task.task_id]: next }));
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
    [minDate, layout.maxDate, pxPerDay, commitDates, onRevert]
  );

  const handleDepDragStart = useCallback(
    (event, fromTask) => {
      event.preventDefault();
      if (!minDate) return;

      const origin = connectorPointForTask(
        fromTask,
        dependencyLayout,
        minDate,
        pxPerDay,
        totalDays,
        'end'
      );
      if (!origin) return;

      const timelineEl = timelineBodyRef.current;
      const clientToTimeline = (clientX, clientY) => {
        const rect = timelineEl.getBoundingClientRect();
        return {
          x: clientX - rect.left + (timelineEl.scrollLeft || 0),
          y: clientY - rect.top,
        };
      };

      setDepDrag({
        x1: origin.x,
        y1: origin.y,
        x2: origin.x,
        y2: origin.y,
        fromTaskId: fromTask.task_id,
      });

      const onMove = (e) => {
        const { x, y } = clientToTimeline(e.clientX, e.clientY);
        setDepDrag((prev) => (prev ? { ...prev, x2: x, y2: y } : null));
      };

      const onUp = (e) => {
        document.removeEventListener('mousemove', onMove);
        document.removeEventListener('mouseup', onUp);
        setDepDrag(null);
        const el = document.elementFromPoint(e.clientX, e.clientY);
        const row = el?.closest('[data-task-id]');
        const toId = row?.getAttribute('data-task-id');
        if (toId && toId !== fromTask.task_id) {
          addDependency(fromTask.task_id, toId);
        }
      };

      document.addEventListener('mousemove', onMove);
      document.addEventListener('mouseup', onUp);
    },
    [minDate, dependencyLayout, pxPerDay, totalDays, addDependency]
  );

  const togglePhase = (phase) => {
    setCollapsedPhases((prev) => {
      const next = new Set(prev);
      if (next.has(phase)) next.delete(phase);
      else next.add(phase);
      return next;
    });
  };

  const startInlineEdit = (task) => {
    setEditingTitleId(task.task_id);
    setTitleDraft(task.title);
    selectTask(task.task_id);
  };

  const cancelInlineEdit = () => {
    setEditingTitleId(null);
    setTitleDraft('');
  };

  const saveInlineEdit = async (taskId) => {
    if (skipBlurSaveRef.current) {
      skipBlurSaveRef.current = false;
      return;
    }
    const task = tasks.find((t) => t.task_id === taskId);
    const trimmed = titleDraft.trim();
    if (!trimmed) {
      toast.error('Title is required');
      setTitleDraft(task?.title || '');
      cancelInlineEdit();
      return;
    }
    if (task && trimmed === task.title) {
      cancelInlineEdit();
      return;
    }
    await commitTitle(taskId, trimmed);
    cancelInlineEdit();
  };

  if (!tasks.length) {
    return (
      <div className="rounded border bg-muted/20 px-4 py-8 text-center text-xs text-muted-foreground">
        No tasks yet. Use the toolbar to add a task, phase, or milestone.
      </div>
    );
  }

  return (
    <div className="flex flex-1 min-h-0 border rounded-md bg-card overflow-hidden">
      <div className="flex flex-col flex-1 min-w-0 min-h-0">
        {/* Sticky header */}
        <div className="flex border-b bg-muted/40 shrink-0 text-[10px] text-muted-foreground">
          <div
            className="shrink-0 border-r px-2 py-1 font-semibold uppercase tracking-wide"
            style={{ width: LEFT_PANEL_WIDTH }}
          >
            Tasks
          </div>
          <div
            ref={timelineHeaderRef}
            className="flex-1 overflow-x-auto overflow-y-hidden relative h-6 [scrollbar-width:none] [&::-webkit-scrollbar]:hidden"
            onScroll={() => {
              if (timelineHeaderRef.current && timelineBodyRef.current) {
                timelineBodyRef.current.scrollLeft = timelineHeaderRef.current.scrollLeft;
              }
            }}
          >
            <div className="relative h-full" style={{ width: timelineWidth }}>
              {minDate &&
                ticks.map((tick) => {
                  const left = diffDays(tick.date, minDate) * pxPerDay;
                  return (
                    <span
                      key={tick.label + tick.date.toISOString()}
                      className="absolute top-1 -translate-x-1/2 whitespace-nowrap"
                      style={{ left }}
                    >
                      {tick.label}
                    </span>
                  );
                })}
            </div>
          </div>
        </div>

        {/* Shared vertical scroll */}
        <div
          ref={scrollRef}
          className="flex-1 overflow-y-auto overflow-x-hidden min-h-0"
          style={{ maxHeight: 'calc(100vh - 220px)' }}
        >
          <div className="flex min-h-full">
            {/* Left task panel */}
            <div className="shrink-0 border-r bg-card" style={{ width: LEFT_PANEL_WIDTH }}>
              {rows.map((row, i) => {
                if (row.kind === 'phase') {
                  const color = phaseColorMap[row.phase] || PHASE_BAR_COLORS[0];
                  return (
                    <div
                      key={row.key}
                      role="button"
                      tabIndex={0}
                      className={cn(
                        'flex items-center gap-1 px-2 border-b bg-muted/30 text-[10px] font-semibold uppercase tracking-wide cursor-pointer hover:bg-muted/50',
                        selectedPhase === row.phase && 'bg-primary/10 ring-1 ring-inset ring-primary/30'
                      )}
                      style={{ height: PHASE_ROW_HEIGHT }}
                      onClick={() => selectPhase(row.phase)}
                      onKeyDown={(e) => e.key === 'Enter' && selectPhase(row.phase)}
                    >
                      <button
                        type="button"
                        className="shrink-0 text-muted-foreground hover:text-foreground"
                        onClick={(e) => {
                          e.stopPropagation();
                          togglePhase(row.phase);
                        }}
                      >
                        {row.collapsed ? (
                          <ChevronRight className="h-3 w-3" />
                        ) : (
                          <ChevronDown className="h-3 w-3" />
                        )}
                      </button>
                      <span className={cn('h-1.5 w-1.5 rounded-sm shrink-0', color)} />
                      <span className="truncate flex-1">{row.phase}</span>
                      <span className="text-[9px] text-muted-foreground">{row.tasks.length}</span>
                    </div>
                  );
                }

                const task = row.task;
                const isSelected = selectedId === task.task_id;
                const isMilestone = task.type === 'milestone';

                return (
                  <div
                    key={row.key}
                    data-task-id={task.task_id}
                    className={cn(
                      'flex items-center gap-1.5 px-2 border-b text-[11px] cursor-pointer',
                      i % 2 === 0 ? 'bg-background' : 'bg-muted/10',
                      isSelected && 'bg-primary/10 ring-1 ring-inset ring-primary/30'
                    )}
                    style={{ height: TASK_ROW_HEIGHT }}
                    onClick={() => selectTask(task.task_id)}
                  >
                    <span
                      className={cn(
                        'h-1.5 w-1.5 rounded-full shrink-0',
                        statusDotMap[task.status] || statusDotMap.not_started
                      )}
                      title={task.status}
                    />
                    {isMilestone && (
                      <Diamond className="h-2.5 w-2.5 shrink-0 text-muted-foreground" />
                    )}
                    {editingTitleId === task.task_id ? (
                      <input
                        className="flex-1 min-w-0 h-5 px-1 text-[11px] border rounded bg-background"
                        value={titleDraft}
                        autoFocus
                        onChange={(e) => setTitleDraft(e.target.value)}
                        onKeyDown={(e) => {
                          if (e.key === 'Enter') {
                            e.preventDefault();
                            saveInlineEdit(task.task_id);
                          }
                          if (e.key === 'Escape') {
                            skipBlurSaveRef.current = true;
                            cancelInlineEdit();
                          }
                        }}
                        onBlur={() => saveInlineEdit(task.task_id)}
                        onClick={(e) => e.stopPropagation()}
                      />
                    ) : (
                      <span
                        className="truncate flex-1 hover:underline"
                        onClick={(e) => {
                          e.stopPropagation();
                          startInlineEdit(task);
                        }}
                        title={`${task.title} — click to edit`}
                      >
                        {task.title}
                      </span>
                    )}
                    {task.responsible_party && (
                      <span
                        className="shrink-0 text-[9px] font-medium text-muted-foreground bg-muted px-1 rounded"
                        title={task.responsible_party}
                      >
                        {initialsFor(task.responsible_party)}
                      </span>
                    )}
                    {(task.dependencies || []).length > 0 && (
                      <Link2 className="h-2.5 w-2.5 shrink-0 text-muted-foreground" />
                    )}
                  </div>
                );
              })}
            </div>

            {/* Timeline body */}
            <div
              ref={timelineBodyRef}
              className="flex-1 overflow-x-auto overflow-y-hidden relative"
              onScroll={syncHeaderScroll}
            >
              <div className="relative" style={{ width: timelineWidth, height: timelineContentHeight }}>
                {!minDate && (
                  <div className="absolute inset-0 flex items-center justify-center text-[11px] text-muted-foreground pointer-events-none z-20">
                    Add start dates to tasks to display the timeline.
                  </div>
                )}
                {/* Grid lines */}
                {minDate &&
                  ticks.map((tick) => {
                    const left = diffDays(tick.date, minDate) * pxPerDay;
                    return (
                      <div
                        key={`grid-${tick.date.toISOString()}`}
                        className="absolute top-0 bottom-0 border-l border-border/30 pointer-events-none"
                        style={{ left }}
                      />
                    );
                  })}

                {/* Dependency lines */}
                <svg
                  className="absolute inset-0 pointer-events-none z-10"
                  width={timelineWidth}
                  height={timelineContentHeight}
                >
                  {dependencyPaths.map((path) => (
                    <path
                      key={path.id}
                      d={path.d}
                      fill="none"
                      stroke="currentColor"
                      strokeWidth="1.5"
                      className="text-muted-foreground/60"
                      markerEnd="url(#arrowhead)"
                    />
                  ))}
                  {depDrag && (
                    <line
                      x1={depDrag.x1}
                      y1={depDrag.y1}
                      x2={depDrag.x2}
                      y2={depDrag.y2}
                      stroke="currentColor"
                      strokeWidth="2"
                      strokeDasharray="4 2"
                      className="text-primary"
                    />
                  )}
                  <defs>
                    <marker
                      id="arrowhead"
                      markerWidth="6"
                      markerHeight="6"
                      refX="5"
                      refY="3"
                      orient="auto"
                    >
                      <polygon points="0 0, 6 3, 0 6" className="fill-muted-foreground/60" />
                    </marker>
                  </defs>
                </svg>

                {rows.map((row, i) => {
                  const top = rowOffsets[i];
                  const height = rowHeightFor(row);

                  if (row.kind === 'phase') {
                    const span = computePhaseSpan(row.tasks);
                    const color = phaseColorMap[row.phase] || PHASE_BAR_COLORS[0];
                    const phasePx = span && minDate
                      ? barPixels(
                          { ...row.tasks[0], start_date: span.start_date, end_date: span.end_date, type: 'task' },
                          minDate,
                          pxPerDay,
                          totalDays
                        )
                      : null;

                    return (
                      <div
                        key={row.key}
                        className="absolute left-0 right-0 border-b bg-muted/20"
                        style={{ top, height }}
                      >
                        {phasePx && (
                          <div
                            className={cn('absolute top-1/2 -translate-y-1/2 h-1.5 rounded opacity-40', color)}
                            style={{ left: phasePx.left, width: phasePx.width }}
                          />
                        )}
                      </div>
                    );
                  }

                  const task = row.task;
                  const effective = previews[task.task_id]
                    ? { ...task, ...previews[task.task_id] }
                    : task;
                  const px = task.start_date && minDate
                    ? barPixels(effective, minDate, pxPerDay, totalDays)
                    : null;
                  const barColor = phaseColorMap[row.phase] || PHASE_BAR_COLORS[0];
                  const isActive =
                    hoveredId === task.task_id || dragging?.taskId === task.task_id;

                  return (
                    <div
                      key={row.key}
                      data-task-id={task.task_id}
                      className={cn(
                        'absolute left-0 right-0 border-b border-border/30',
                        i % 2 === 0 ? 'bg-background/50' : 'bg-muted/5'
                      )}
                      style={{ top, height }}
                      onClick={() => selectTask(task.task_id)}
                    >
                      <TimelineBar
                        task={effective}
                        barColor={barColor}
                        px={px}
                        isActive={isActive}
                        previewDates={previews[task.task_id]}
                        onHover={setHoveredId}
                        onSelect={selectTask}
                        onDragStart={handleDragStart}
                        onDepDragStart={handleDepDragStart}
                      />
                    </div>
                  );
                })}
              </div>
            </div>
          </div>
        </div>
      </div>

      {selectedTask && (
        <GanttTaskInspector
          task={selectedTask}
          tasks={tasks}
          projectId={projectId}
          apiFetch={apiFetch}
          taskStatuses={taskStatuses}
          taskTypes={taskTypes}
          onClose={() => setSelectedId(null)}
          onRefresh={onRefresh}
          onDeleted={() => setSelectedId(null)}
        />
      )}
      {selectedPhase && !selectedTask && (
        <GanttPhaseInspector
          phase={selectedPhase}
          tasks={tasks}
          projectId={projectId}
          apiFetch={apiFetch}
          onClose={() => setSelectedPhase(null)}
          onRefresh={onRefresh}
        />
      )}
    </div>
  );
};
