export const UNASSIGNED_PHASE = '(Unassigned)';

export const normalizePhase = (phase) => {
  const trimmed = phase?.trim();
  return trimmed || UNASSIGNED_PHASE;
};

/** Group tasks by phase, ordered by earliest task order within each phase. */
export const groupTasksByPhase = (tasks) => {
  const groups = new Map();
  tasks.forEach((task) => {
    const phase = normalizePhase(task.phase);
    if (!groups.has(phase)) groups.set(phase, []);
    groups.get(phase).push(task);
  });

  return Array.from(groups.entries())
    .map(([phase, phaseTasks]) => ({
      phase,
      tasks: [...phaseTasks].sort((a, b) => a.order - b.order),
      minOrder: Math.min(...phaseTasks.map((t) => t.order)),
    }))
    .sort((a, b) => {
      if (a.phase === UNASSIGNED_PHASE) return 1;
      if (b.phase === UNASSIGNED_PHASE) return -1;
      return a.minOrder - b.minOrder;
    });
};

const splitRow = (line) => {
  if (line.includes('\t')) return line.split('\t').map((c) => c.trim());
  if (line.includes(',')) return line.split(',').map((c) => c.trim());
  return [line.trim()];
};

/**
 * Parse pasted rows into task payloads.
 * Supported columns (tab or comma separated):
 *   phase, title, start_date, end_date, type, status, responsible_party
 * Minimum: title per line (phase defaults to null).
 */
export const parseBulkTaskRows = (text, { taskTypes = ['task', 'milestone'], taskStatuses = [] } = {}) => {
  const lines = text
    .split(/\r?\n/)
    .map((l) => l.trim())
    .filter(Boolean);

  const rows = [];
  const errors = [];

  lines.forEach((line, index) => {
    const cols = splitRow(line);
    const lineNum = index + 1;

    let phase = null;
    let title;
    let start_date = null;
    let end_date = null;
    let type = 'task';
    let status = 'not_started';
    let responsible_party = null;

    if (cols.length === 1) {
      title = cols[0];
    } else if (cols.length === 2) {
      [phase, title] = cols;
    } else {
      [phase, title, start_date, end_date, type, status, responsible_party] = cols;
    }

    if (!title) {
      errors.push(`Line ${lineNum}: title is required`);
      return;
    }

    if (type && !taskTypes.includes(type)) {
      errors.push(`Line ${lineNum}: invalid type "${type}"`);
      return;
    }

    if (status && taskStatuses.length > 0 && !taskStatuses.includes(status)) {
      errors.push(`Line ${lineNum}: invalid status "${status}"`);
      return;
    }

    rows.push({
      type: type || 'task',
      phase: phase || null,
      title,
      description: null,
      start_date: start_date || null,
      end_date: end_date || null,
      status: status || 'not_started',
      responsible_party: responsible_party || null,
      dependencies: [],
    });
  });

  return { rows, errors };
};

export const duplicateTaskPayload = (task) => ({
  type: task.type,
  phase: task.phase,
  title: `${task.title} (copy)`,
  description: task.description,
  start_date: task.start_date,
  end_date: task.end_date,
  status: task.status,
  responsible_party: task.responsible_party,
  dependencies: (task.dependencies || []).map((d) => ({ ...d })),
});
