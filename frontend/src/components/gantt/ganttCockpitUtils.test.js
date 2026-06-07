import {
  buildCockpitRows,
  buildRowLayout,
  buildStatusDotMap,
  mergeTaskPreviews,
  buildDependencyPaths,
  getTimelineLayout,
} from './ganttCockpitUtils';

describe('ganttCockpitUtils', () => {
  const sampleTasks = [
    {
      task_id: 'gt_a',
      order: 0,
      type: 'task',
      phase: 'Phase 1',
      title: 'Task A',
      start_date: '2026-03-01',
      end_date: '2026-03-05',
      dependencies: [],
    },
    {
      task_id: 'gt_b',
      order: 1,
      type: 'task',
      phase: 'Phase 1',
      title: 'Task B',
      start_date: '2026-03-06',
      end_date: '2026-03-08',
      dependencies: [{ task_id: 'gt_a', type: 'finish_to_start' }],
    },
  ];

  test('buildStatusDotMap uses config statuses', () => {
    const map = buildStatusDotMap(['not_started', 'in_progress', 'completed', 'blocked']);
    expect(map.not_started).toBeTruthy();
    expect(map.custom_status).toBeUndefined();
    const extended = buildStatusDotMap(['not_started', 'custom_status']);
    expect(extended.custom_status).toBeTruthy();
  });

  test('mergeTaskPreviews overlays drag preview dates', () => {
    const merged = mergeTaskPreviews(sampleTasks, {
      gt_a: { start_date: '2026-03-02', end_date: '2026-03-06' },
    });
    expect(merged[0].start_date).toBe('2026-03-02');
    expect(merged[1].start_date).toBe('2026-03-06');
  });

  test('buildCockpitRows respects collapsed phases', () => {
    const collapsed = new Set(['Phase 1']);
    const rows = buildCockpitRows(sampleTasks, collapsed);
    expect(rows).toHaveLength(1);
    expect(rows[0].kind).toBe('phase');
    expect(rows[0].collapsed).toBe(true);
  });

  test('buildDependencyPaths uses full expanded layout when phases collapsed', () => {
    const collapsedRows = buildCockpitRows(sampleTasks, new Set(['Phase 1']));
    const fullRows = buildCockpitRows(sampleTasks, new Set());
    const fullLayout = buildRowLayout(fullRows);
    const { minDate, totalDays, pxPerDay } = getTimelineLayout(sampleTasks, 'Week');
    const paths = buildDependencyPaths(sampleTasks, fullLayout, minDate, pxPerDay, totalDays);
    expect(paths).toHaveLength(1);
    expect(collapsedRows).toHaveLength(1);
  });
});
