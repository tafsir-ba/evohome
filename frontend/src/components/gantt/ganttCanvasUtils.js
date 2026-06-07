/**
 * Map backend Gantt tasks to frappe-gantt task format.
 * Task table remains source of truth; canvas is a synced view.
 */
export const toFrappeTasks = (tasks) => {
  const dated = tasks.filter((t) => t.start_date);
  return dated.map((task) => {
    const end =
      task.type === 'milestone'
        ? task.start_date
        : task.end_date || task.start_date;

    const deps = (task.dependencies || [])
      .map((d) => d.task_id)
      .filter(Boolean)
      .join(',');

    const progress =
      task.status === 'completed'
        ? 100
        : task.status === 'in_progress'
          ? 50
          : 0;

    return {
      id: task.task_id,
      name: task.title,
      start: task.start_date,
      end,
      progress,
      dependencies: deps,
      custom_class: task.type === 'milestone' ? 'gantt-milestone' : '',
      _sourceTask: task,
    };
  });
};

export const frappeDateToIso = (date) => {
  if (!date) return null;
  if (typeof date === 'string') return date.slice(0, 10);
  const y = date.getFullYear();
  const m = String(date.getMonth() + 1).padStart(2, '0');
  const d = String(date.getDate()).padStart(2, '0');
  return `${y}-${m}-${d}`;
};
