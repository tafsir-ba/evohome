export const getFileSourceType = (filename) => {
  const ext = filename?.includes('.')
    ? `.${filename.split('.').pop().toLowerCase()}`
    : '';
  if (ext === '.csv') return 'csv';
  if (ext === '.xlsx') return 'xlsx';
  if (ext === '.pdf') return 'pdf';
  return 'image';
};

export const UPLOAD_PROGRESS_STEPS = [
  'Validating file format and size…',
  'Uploading document to secure storage…',
];

export const EXTRACT_PROGRESS_STEPS = {
  csv: [
    'Reading CSV spreadsheet…',
    'Detecting column headers…',
    'Mapping tasks, phases, and dates…',
    'Building reviewable draft…',
  ],
  xlsx: [
    'Reading Excel workbook…',
    'Detecting column headers…',
    'Mapping tasks, phases, and dates…',
    'Building reviewable draft…',
  ],
  pdf: [
    'Extracting text from PDF pages…',
    'Sending document content to AI…',
    'Identifying phases, tasks, and milestones…',
    'Extracting dates and dependencies…',
    'Preparing draft for your review…',
  ],
  image: [
    'Loading chart image…',
    'Analyzing layout with vision AI…',
    'Identifying phases, tasks, and milestones…',
    'Extracting dates and dependencies…',
    'Preparing draft for your review…',
  ],
};

/** Human-readable label for backend extraction_model (e.g. gpt-5.4 → GPT 5.4). */
export const formatExtractionModelLabel = (model) => {
  if (!model) return 'AI';
  return model.replace(/^gpt-/i, 'GPT ').replace(/-/g, ' ');
};

export const IMPORT_FLOW_STEPS = [
  {
    key: 'select',
    label: 'Select file',
    description: 'Choose a PDF, image, CSV, or Excel planning document.',
  },
  {
    key: 'analyze',
    label: 'Extract draft',
    description: 'One click uploads and analyzes — nothing is saved until you confirm.',
  },
  {
    key: 'review',
    label: 'Review',
    description: 'Edit tasks, dates, and phases before saving.',
  },
  {
    key: 'confirm',
    label: 'Confirm',
    description: 'Import only after you approve the draft.',
  },
];
