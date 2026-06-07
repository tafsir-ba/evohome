export const DAY_MS = 1000 * 60 * 60 * 24;

export const PHASE_BAR_COLORS = [
  'bg-blue-500',
  'bg-emerald-500',
  'bg-amber-500',
  'bg-violet-500',
  'bg-rose-500',
  'bg-cyan-500',
  'bg-orange-500',
  'bg-indigo-500',
];

export const parseGanttDate = (value) => {
  if (!value) return null;
  const d = new Date(`${value}T00:00:00`);
  return Number.isNaN(d.getTime()) ? null : d;
};

export const formatIsoDate = (date) => {
  if (!date) return null;
  const y = date.getFullYear();
  const m = String(date.getMonth() + 1).padStart(2, '0');
  const d = String(date.getDate()).padStart(2, '0');
  return `${y}-${m}-${d}`;
};

export const addDays = (date, days) => {
  const next = new Date(date.getTime());
  next.setDate(next.getDate() + days);
  return next;
};

export const diffDays = (a, b) => Math.round((a.getTime() - b.getTime()) / DAY_MS);

export const computeTimelineRange = (tasks) => {
  const withDates = tasks.filter((t) => t.start_date);
  if (!withDates.length) {
    return { minDate: null, maxDate: null, totalDays: 1 };
  }
  const starts = withDates.map((t) => parseGanttDate(t.start_date)).filter(Boolean);
  const ends = withDates
    .map((t) => parseGanttDate(t.end_date || t.start_date))
    .filter(Boolean);
  const min = new Date(Math.min(...starts.map((d) => d.getTime())));
  const max = new Date(Math.max(...ends.map((d) => d.getTime())));
  const totalDays = Math.max(1, diffDays(max, min) + 1);
  return { minDate: min, maxDate: max, totalDays };
};

export const barMetrics = (task, minDate, totalDays) => {
  const start = parseGanttDate(task.start_date);
  const end = parseGanttDate(task.end_date || task.start_date);
  if (!start || !end || !minDate) return null;
  const offsetDays = diffDays(start, minDate);
  const spanDays = Math.max(1, diffDays(end, start) + 1);
  return {
    leftPct: (offsetDays / totalDays) * 100,
    widthPct: (spanDays / totalDays) * 100,
    start,
    end,
  };
};

export const applyDragDelta = (task, mode, deltaDays, minDate, maxDate) => {
  const start = parseGanttDate(task.start_date);
  const end = parseGanttDate(task.end_date || task.start_date);
  if (!start || !end) return null;

  const isMilestone = task.type === 'milestone';

  if (isMilestone) {
    if (mode === 'resize-start' || mode === 'resize-end') return null;
    const nextStart = addDays(start, deltaDays);
    const iso = formatIsoDate(nextStart);
    return { start_date: iso, end_date: iso };
  }

  if (mode === 'move') {
    const nextStart = addDays(start, deltaDays);
    const nextEnd = addDays(end, deltaDays);
    return {
      start_date: formatIsoDate(nextStart),
      end_date: formatIsoDate(nextEnd),
    };
  }

  if (mode === 'resize-start') {
    const nextStart = addDays(start, deltaDays);
    if (nextStart > end) return null;
    return { start_date: formatIsoDate(nextStart), end_date: formatIsoDate(end) };
  }

  if (mode === 'resize-end') {
    const nextEnd = addDays(end, deltaDays);
    if (nextEnd < start) return null;
    return { start_date: formatIsoDate(start), end_date: formatIsoDate(nextEnd) };
  }

  return null;
};

export const monthTicks = (minDate, maxDate) => {
  if (!minDate || !maxDate) return [];
  const ticks = [];
  const cursor = new Date(minDate.getFullYear(), minDate.getMonth(), 1);
  const end = new Date(maxDate.getFullYear(), maxDate.getMonth() + 1, 0);
  while (cursor <= end) {
    ticks.push({
      label: cursor.toLocaleDateString(undefined, { month: 'short', year: '2-digit' }),
      date: new Date(cursor),
    });
    cursor.setMonth(cursor.getMonth() + 1);
  }
  return ticks;
};
