import { groupTasksByPhase, UNASSIGNED_PHASE } from './ganttTaskUtils';
import {
  parseGanttDate,
  formatIsoDate,
  diffDays,
  computeTimelineRange,
  barMetrics,
} from './ganttTimelineUtils';

export const LEFT_PANEL_WIDTH = 280;
export const TASK_ROW_HEIGHT = 22;
export const PHASE_ROW_HEIGHT = 24;
export const HANDLE_WIDTH = 6;

export const ZOOM_LEVELS = ['Day', 'Week', 'Month', 'Quarter'];

export const ZOOM_PX_PER_DAY = {
  Day: 28,
  Week: 10,
  Month: 3,
  Quarter: 1,
};

export const STATUS_DOT = {
  not_started: 'bg-muted-foreground/40',
  in_progress: 'bg-blue-500',
  completed: 'bg-emerald-500',
  blocked: 'bg-rose-500',
};

export const initialsFor = (name) => {
  if (!name) return '';
  const parts = name.trim().split(/\s+/);
  if (parts.length === 1) return parts[0].slice(0, 2).toUpperCase();
  return `${parts[0][0] || ''}${parts[1][0] || ''}`.toUpperCase();
};

/** Flat row list for aligned left panel + timeline (phase headers + tasks). */
export const buildCockpitRows = (tasks, collapsedPhases = new Set()) => {
  const groups = groupTasksByPhase(tasks);
  const rows = [];

  groups.forEach((group) => {
    const collapsed = collapsedPhases.has(group.phase);
    rows.push({
      kind: 'phase',
      key: `phase-${group.phase}`,
      phase: group.phase,
      tasks: group.tasks,
      collapsed,
    });
    if (!collapsed) {
      group.tasks.forEach((task) => {
        rows.push({
          kind: 'task',
          key: task.task_id,
          task,
          phase: group.phase,
        });
      });
    }
  });

  return rows;
};

export const computePhaseSpan = (phaseTasks) => {
  const dated = phaseTasks.filter((t) => t.start_date);
  if (!dated.length) return null;
  const starts = dated.map((t) => parseGanttDate(t.start_date)).filter(Boolean);
  const ends = dated
    .map((t) => parseGanttDate(t.end_date || t.start_date))
    .filter(Boolean);
  if (!starts.length || !ends.length) return null;
  const min = new Date(Math.min(...starts.map((d) => d.getTime())));
  const max = new Date(Math.max(...ends.map((d) => d.getTime())));
  return {
    start_date: formatIsoDate(min),
    end_date: formatIsoDate(max),
  };
};

export const getTimelineLayout = (tasks, zoom, fitWidth = null) => {
  const dated = tasks.filter((t) => t.start_date);
  const { minDate, maxDate, totalDays } = computeTimelineRange(dated);
  let pxPerDay = ZOOM_PX_PER_DAY[zoom] || ZOOM_PX_PER_DAY.Week;
  if (fitWidth && minDate && totalDays > 0) {
    pxPerDay = Math.max(0.5, fitWidth / totalDays);
  }
  const timelineWidth = Math.max(fitWidth || 0, totalDays * pxPerDay, 480);
  return { minDate, maxDate, totalDays, pxPerDay, timelineWidth };
};

export const barPixels = (task, minDate, pxPerDay, totalDays) => {
  const metrics = barMetrics(task, minDate, totalDays);
  if (!metrics || !minDate) return null;
  const spanDays = Math.max(1, diffDays(metrics.end, metrics.start) + 1);
  const offsetDays = diffDays(metrics.start, minDate);
  return {
    left: offsetDays * pxPerDay,
    width: task.type === 'milestone' ? 10 : Math.max(spanDays * pxPerDay, 4),
    start: metrics.start,
    end: metrics.end,
  };
};

export const buildZoomTicks = (minDate, maxDate, zoom) => {
  if (!minDate || !maxDate) return [];
  const ticks = [];
  const cursor = new Date(minDate);

  if (zoom === 'Day') {
    while (cursor <= maxDate) {
      ticks.push({
        date: new Date(cursor),
        label: cursor.toLocaleDateString(undefined, { day: 'numeric', month: 'short' }),
      });
      cursor.setDate(cursor.getDate() + 1);
    }
    return ticks;
  }

  if (zoom === 'Week') {
    while (cursor <= maxDate) {
      ticks.push({
        date: new Date(cursor),
        label: cursor.toLocaleDateString(undefined, { day: 'numeric', month: 'short' }),
      });
      cursor.setDate(cursor.getDate() + 7);
    }
    return ticks;
  }

  if (zoom === 'Quarter') {
    cursor.setMonth(Math.floor(cursor.getMonth() / 3) * 3, 1);
    while (cursor <= maxDate) {
      const q = Math.floor(cursor.getMonth() / 3) + 1;
      ticks.push({
        date: new Date(cursor),
        label: `Q${q} ${String(cursor.getFullYear()).slice(2)}`,
      });
      cursor.setMonth(cursor.getMonth() + 3);
    }
    return ticks;
  }

  // Month (default)
  cursor.setDate(1);
  while (cursor <= maxDate) {
    ticks.push({
      date: new Date(cursor),
      label: cursor.toLocaleDateString(undefined, { month: 'short', year: '2-digit' }),
    });
    cursor.setMonth(cursor.getMonth() + 1);
  }
  return ticks;
};

/** SVG dependency connector paths (finish → start). */
export const buildDependencyPaths = (
  tasks,
  rowIndexByTaskId,
  rowOffsets,
  rows,
  minDate,
  pxPerDay,
  totalDays
) => {
  const paths = [];
  tasks.forEach((task) => {
    const toIdx = rowIndexByTaskId[task.task_id];
    if (toIdx == null || !task.start_date) return;

    (task.dependencies || []).forEach((dep) => {
      const fromTask = tasks.find((t) => t.task_id === dep.task_id);
      const fromIdx = rowIndexByTaskId[dep.task_id];
      if (!fromTask?.start_date || fromIdx == null) return;

      const fromBar = barPixels(fromTask, minDate, pxPerDay, totalDays);
      const toBar = barPixels(task, minDate, pxPerDay, totalDays);
      if (!fromBar || !toBar) return;

      const x1 = fromBar.left + fromBar.width;
      const y1 = rowOffsets[fromIdx] + rowHeightFor(rows[fromIdx]) / 2;
      const x2 = toBar.left;
      const y2 = rowOffsets[toIdx] + rowHeightFor(rows[toIdx]) / 2;
      const midX = x1 + Math.max(12, (x2 - x1) / 2);

      paths.push({
        id: `${dep.task_id}->${task.task_id}`,
        d: `M ${x1} ${y1} H ${midX} V ${y2} H ${x2}`,
      });
    });
  });
  return paths;
};

export const rowHeightFor = (row) =>
  row.kind === 'phase' ? PHASE_ROW_HEIGHT : TASK_ROW_HEIGHT;

export const isUnassignedPhase = (phase) => phase === UNASSIGNED_PHASE;
