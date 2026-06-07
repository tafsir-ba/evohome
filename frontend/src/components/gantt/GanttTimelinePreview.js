import { useMemo } from 'react';
import { cn } from '../../lib/utils';

const BAR_COLORS = [
  'bg-blue-500',
  'bg-emerald-500',
  'bg-amber-500',
  'bg-violet-500',
  'bg-rose-500',
  'bg-cyan-500',
];

const parseDate = (value) => {
  if (!value) return null;
  const d = new Date(`${value}T00:00:00`);
  return Number.isNaN(d.getTime()) ? null : d;
};

export const GanttTimelinePreview = ({ tasks }) => {
  const { datedTasks, minDate, maxDate, totalDays } = useMemo(() => {
    const withDates = tasks.filter((t) => t.start_date);
    if (withDates.length === 0) {
      return { datedTasks: [], minDate: null, maxDate: null, totalDays: 1 };
    }

    const starts = withDates.map((t) => parseDate(t.start_date)).filter(Boolean);
    const ends = withDates
      .map((t) => parseDate(t.end_date || t.start_date))
      .filter(Boolean);

    const min = new Date(Math.min(...starts.map((d) => d.getTime())));
    const max = new Date(Math.max(...ends.map((d) => d.getTime())));
    const days = Math.max(1, Math.ceil((max - min) / (1000 * 60 * 60 * 24)) + 1);

    return { datedTasks: withDates, minDate: min, maxDate: max, totalDays: days };
  }, [tasks]);

  if (datedTasks.length === 0) {
    return (
      <div className="rounded-lg border bg-muted/30 p-6 text-center text-sm text-muted-foreground">
        Add start dates to tasks to see the timeline preview.
      </div>
    );
  }

  const dayMs = 1000 * 60 * 60 * 24;

  return (
    <div className="rounded-lg border bg-card p-4 space-y-3">
      <div className="flex justify-between text-xs text-muted-foreground">
        <span>{minDate.toISOString().slice(0, 10)}</span>
        <span>{maxDate.toISOString().slice(0, 10)}</span>
      </div>

      <div className="space-y-2">
        {datedTasks.map((task, index) => {
          const start = parseDate(task.start_date);
          const end = parseDate(task.end_date || task.start_date);
          const offsetDays = Math.round((start - minDate) / dayMs);
          const spanDays = Math.max(1, Math.round((end - start) / dayMs) + 1);
          const leftPct = (offsetDays / totalDays) * 100;
          const widthPct = (spanDays / totalDays) * 100;
          const isMilestone = task.type === 'milestone';

          return (
            <div key={task.task_id} className="flex items-center gap-3">
              <div className="w-36 truncate text-xs text-muted-foreground" title={task.title}>
                {task.title}
              </div>
              <div className="relative flex-1 h-6 bg-muted/50 rounded">
                <div
                  className={cn(
                    'absolute top-1/2 -translate-y-1/2 rounded',
                    isMilestone ? 'h-4 w-4 rotate-45' : 'h-4',
                    BAR_COLORS[index % BAR_COLORS.length]
                  )}
                  style={{
                    left: `${leftPct}%`,
                    width: isMilestone ? undefined : `${Math.max(widthPct, 2)}%`,
                  }}
                  title={`${task.start_date}${task.end_date ? ` → ${task.end_date}` : ''}`}
                />
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
};
