import { useState, useCallback, useRef, useMemo } from 'react';
import { Button } from '../ui/button';
import { Input } from '../ui/input';
import { Badge } from '../ui/badge';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../ui/select';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '../ui/table';
import { parseApiError, getGanttHeaders } from './ganttApiUtils';
import { GanttImportProgress } from './GanttImportProgress';
import {
  getFileSourceType,
  formatExtractionModelLabel,
  UPLOAD_PROGRESS_STEPS,
  EXTRACT_PROGRESS_STEPS,
  IMPORT_FLOW_STEPS,
} from './ganttImportUtils';
import { toast } from 'sonner';
import { AlertTriangle, Check, Loader2, Sparkles, Trash2, Upload, X } from 'lucide-react';
import { cn } from '../../lib/utils';

const ConfidenceBadge = ({ field, confidence, threshold }) => {
  if (confidence == null) return null;
  const pct = Math.round(confidence * 100);
  const low = confidence < threshold;
  return (
    <Badge
      variant={low ? 'destructive' : 'secondary'}
      className="text-[10px] px-1 py-0"
      title={`${field}: ${pct}% confidence`}
    >
      {field} {pct}%
    </Badge>
  );
};

export const GanttImportReview = ({
  projectId,
  apiFetch,
  onConfirmed,
  onClose,
  importConfig,
  taskTypes = ['task', 'milestone'],
}) => {
  const allowedExtensions = importConfig?.allowed_extensions || [];
  const maxSizeMb = importConfig?.max_size_mb || 15;
  const lowConfidenceThreshold = importConfig?.low_confidence_threshold ?? 0.6;
  const [selectedFile, setSelectedFile] = useState(null);
  const [uploadedFileId, setUploadedFileId] = useState(null);
  const [draft, setDraft] = useState(null);
  const [draftTasks, setDraftTasks] = useState([]);
  const [uploading, setUploading] = useState(false);
  const [extracting, setExtracting] = useState(false);
  const [saving, setSaving] = useState(false);
  const [confirming, setConfirming] = useState(false);
  const [discarding, setDiscarding] = useState(false);
  const [dragActive, setDragActive] = useState(false);
  const [flowError, setFlowError] = useState(null);
  const inputRef = useRef(null);

  const validateFile = (file) => {
    const ext = file.name.includes('.')
      ? `.${file.name.split('.').pop().toLowerCase()}`
      : '';
    if (!allowedExtensions.includes(ext)) {
      return `Unsupported file type. Allowed: ${allowedExtensions.join(', ')}`;
    }
    if (file.size > maxSizeMb * 1024 * 1024) {
      return `File exceeds ${maxSizeMb} MB limit`;
    }
    return null;
  };

  const handleFileSelect = (file) => {
    if (!file) return;
    const error = validateFile(file);
    if (error) {
      toast.error(error);
      return;
    }
    setSelectedFile(file);
    setUploadedFileId(null);
    setDraft(null);
    setDraftTasks([]);
    setFlowError(null);
  };

  const handleDrop = (e) => {
    e.preventDefault();
    setDragActive(false);
    handleFileSelect(e.dataTransfer.files?.[0]);
  };

  const uploadSelectedFile = async () => {
    const form = new FormData();
    form.append('gantt_project_id', projectId);
    form.append('file', selectedFile);

    const uploadHeaders = getGanttHeaders();
    delete uploadHeaders['Content-Type'];

    const res = await fetch(`${process.env.REACT_APP_BACKEND_URL}/api/gantt/upload`, {
      method: 'POST',
      credentials: 'include',
      headers: uploadHeaders,
      body: form,
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(parseApiError(err, 'Upload failed'));
    }
    const data = await res.json();
    setUploadedFileId(data.file_id);
    return data.file_id;
  };

  const extractUploadedFile = async (fileId) => {
    const res = await apiFetch('/gantt/extract', {
      method: 'POST',
      body: JSON.stringify({
        file_id: fileId,
        gantt_project_id: projectId,
      }),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(parseApiError(err, 'Extraction failed'));
    }
    return res.json();
  };

  const discardDraftById = async (draftId) => {
    if (!draftId) return;
    await apiFetch(`/gantt/drafts/${draftId}/discard`, { method: 'POST' }).catch(() => {});
  };

  const handleAnalyze = async () => {
    if (!projectId || (!selectedFile && !uploadedFileId)) return;

    setFlowError(null);

    try {
      let fileId = uploadedFileId;

      if (selectedFile && !fileId) {
        setUploading(true);
        fileId = await uploadSelectedFile();
        setUploading(false);
      }

      setExtracting(true);
      const data = await extractUploadedFile(fileId);

      if (!(data.tasks || []).length) {
        await discardDraftById(data.draft_id);
        setDraft(null);
        setDraftTasks([]);
        const warningText = (data.warnings || []).join(' ') || 'No tasks were found in this document.';
        setFlowError(
          `Analysis completed but no tasks were extracted. ${warningText} Try a CSV export, a PDF with a text layer, or a clearer chart image.`
        );
      } else {
        setDraft(data);
        setDraftTasks(data.tasks || []);
        setFlowError(null);
        toast.success('Draft ready for review');
      }
    } catch (error) {
      setFlowError(error.message);
      toast.error(error.message);
    } finally {
      setUploading(false);
      setExtracting(false);
    }
  };

  const updateDraftTask = (tempId, field, value) => {
    setDraftTasks((prev) =>
      prev.map((t) => (t.temp_id === tempId ? { ...t, [field]: value } : t))
    );
  };

  const handleSaveDraft = async () => {
    if (!draft?.draft_id) return;
    setSaving(true);
    try {
      const res = await apiFetch(`/gantt/drafts/${draft.draft_id}`, {
        method: 'PATCH',
        body: JSON.stringify({ tasks: draftTasks }),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(parseApiError(err, 'Failed to save draft'));
      }
      const data = await res.json();
      setDraft(data);
      setDraftTasks(data.tasks || []);
      toast.success('Draft saved');
    } catch (error) {
      toast.error(error.message);
    } finally {
      setSaving(false);
    }
  };

  const handleConfirm = async () => {
    if (!draft?.draft_id) return;
    setConfirming(true);
    try {
      const saveRes = await apiFetch(`/gantt/drafts/${draft.draft_id}`, {
        method: 'PATCH',
        body: JSON.stringify({ tasks: draftTasks }),
      });
      if (!saveRes.ok) {
        const err = await saveRes.json().catch(() => ({}));
        throw new Error(parseApiError(err, 'Failed to save draft before confirm'));
      }

      const res = await apiFetch(`/gantt/drafts/${draft.draft_id}/confirm`, {
        method: 'POST',
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(parseApiError(err, 'Confirm failed'));
      }
      const data = await res.json();
      toast.success(`${data.created_task_count} tasks imported`);
      setDraft(null);
      setDraftTasks([]);
      setSelectedFile(null);
      setUploadedFileId(null);
      await onConfirmed?.();
    } catch (error) {
      toast.error(error.message);
    } finally {
      setConfirming(false);
    }
  };

  const handleDiscard = async () => {
    if (!draft?.draft_id) {
      onClose?.();
      return;
    }
    setDiscarding(true);
    try {
      const res = await apiFetch(`/gantt/drafts/${draft.draft_id}/discard`, {
        method: 'POST',
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(parseApiError(err, 'Discard failed'));
      }
      toast.success('Draft discarded');
      setDraft(null);
      setDraftTasks([]);
      setSelectedFile(null);
      setUploadedFileId(null);
      setFlowError(null);
      onClose?.();
    } catch (error) {
      toast.error(error.message);
    } finally {
      setDiscarding(false);
    }
  };

  const removeDraftTask = (tempId) => {
    setDraftTasks((prev) => prev.filter((t) => t.temp_id !== tempId));
  };

  const hasLowConfidence = useCallback((task) => {
    const confidence = task.field_confidence || {};
    const hasLowScore = Object.values(confidence).some(
      (v) => typeof v === 'number' && v < lowConfidenceThreshold
    );
    const hasWarnings = (task.warnings || []).length > 0;
    return hasLowScore || hasWarnings;
  }, [lowConfidenceThreshold]);

  const acceptAttr = useMemo(
    () => allowedExtensions.join(','),
    [allowedExtensions]
  );

  const sourceType = selectedFile ? getFileSourceType(selectedFile.name) : null;

  const modelLabel = formatExtractionModelLabel(importConfig?.extraction_model);

  const analyzeExplanation = useMemo(() => {
    if (!sourceType) return null;
    if (sourceType === 'csv') {
      return 'CSV files are parsed directly: column headers are matched to phases, task titles, dates, and dependencies. No AI is used.';
    }
    if (sourceType === 'xlsx') {
      return 'Excel files are parsed directly from the Tasks sheet (or first sheet): same column mapping as CSV export. No AI is used.';
    }
    if (sourceType === 'pdf') {
      return `PDFs are read for text, then ${modelLabel} extracts phases, tasks, milestones, dates, and dependencies into a reviewable draft.`;
    }
    return `Images are analyzed with ${modelLabel} vision to detect chart bars, milestones, phases, dates, and dependencies into a reviewable draft.`;
  }, [sourceType, modelLabel]);

  const extractSteps = sourceType
    ? EXTRACT_PROGRESS_STEPS[sourceType]
    : EXTRACT_PROGRESS_STEPS.pdf;

  const analyzing = uploading || extracting;

  const analyzeButtonLabel = useMemo(() => {
    if (uploading) return 'Uploading…';
    if (extracting) {
      return sourceType === 'csv' || sourceType === 'xlsx' ? 'Parsing spreadsheet…' : 'Analyzing…';
    }
    return sourceType === 'csv' || sourceType === 'xlsx' ? 'Parse spreadsheet' : 'Analyze with AI';
  }, [uploading, extracting, sourceType]);

  const activeFlowStep = draft
    ? 'review'
    : analyzing
      ? 'analyze'
      : selectedFile
        ? 'analyze'
        : 'select';

  return (
    <div className="rounded-lg border bg-card p-4 space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h3 className="font-semibold flex items-center gap-2">
            <Sparkles className="h-4 w-4 text-primary" />
            Import from document
          </h3>
          <p className="text-sm text-muted-foreground mt-1">
            Upload a PDF, image, CSV, or Excel file to extract a draft schedule.
          </p>
        </div>
        <Button variant="ghost" size="icon" onClick={onClose} title="Close">
          <X className="h-4 w-4" />
        </Button>
      </div>

      {flowError && (
        <div className="rounded-md border border-destructive/40 bg-destructive/5 px-3 py-2 text-sm text-destructive flex gap-2">
          <AlertTriangle className="h-4 w-4 shrink-0 mt-0.5" />
          <p>{flowError}</p>
        </div>
      )}

      {!draft && (
        <div className="space-y-3">
          <div className="rounded-lg border bg-muted/30 p-4 space-y-4">
            <div>
              <p className="text-sm font-medium">How import works</p>
              <p className="text-sm text-muted-foreground mt-1">
                Upload a planning document and let AI build a draft schedule. Nothing is saved
                to your chart until you review and confirm.
              </p>
              {importConfig?.review_message && (
                <p className="text-sm text-muted-foreground mt-2">{importConfig.review_message}</p>
              )}
            </div>
            <ol className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3">
              {IMPORT_FLOW_STEPS.map((step, index) => {
                const stepOrder = ['select', 'analyze', 'review', 'confirm'];
                const activeIndex = stepOrder.indexOf(activeFlowStep);
                const stepIndex = stepOrder.indexOf(step.key);
                const isActive = step.key === activeFlowStep;
                const isDone = stepIndex >= 0 && activeIndex > stepIndex;
                return (
                  <li
                    key={step.key}
                    className={cn(
                      'rounded-md border p-3 text-sm',
                      isActive && 'border-primary bg-primary/5',
                      isDone && 'border-emerald-500/40 bg-emerald-500/5'
                    )}
                  >
                    <div className="flex items-center gap-2 font-medium">
                      <span
                        className={cn(
                          'flex h-5 w-5 items-center justify-center rounded-full text-[10px]',
                          isDone
                            ? 'bg-emerald-500 text-white'
                            : isActive
                              ? 'bg-primary text-primary-foreground'
                              : 'bg-muted text-muted-foreground'
                        )}
                      >
                        {isDone ? <Check className="h-3 w-3" /> : index + 1}
                      </span>
                      {step.label}
                    </div>
                    <p className="text-xs text-muted-foreground mt-2 pl-7">{step.description}</p>
                  </li>
                );
              })}
            </ol>
          </div>

          {uploading && (
            <GanttImportProgress
              active={uploading}
              steps={UPLOAD_PROGRESS_STEPS}
              label="Uploading your document"
            />
          )}

          {extracting && (
            <GanttImportProgress
              active={extracting}
              steps={extractSteps}
              label={sourceType === 'csv' || sourceType === 'xlsx' ? 'Parsing your spreadsheet' : 'AI is analyzing your document'}
            />
          )}

          <div
            className={`border-2 border-dashed rounded-lg p-8 text-center cursor-pointer transition-colors ${
              dragActive ? 'border-primary bg-primary/5' : 'border-muted-foreground/25'
            }`}
            onDragOver={(e) => { e.preventDefault(); setDragActive(true); }}
            onDragLeave={() => setDragActive(false)}
            onDrop={handleDrop}
            onClick={() => inputRef.current?.click()}
          >
            <Upload className="h-8 w-8 mx-auto mb-2 text-muted-foreground" />
            <p className="text-sm text-muted-foreground">
              Drop PDF, image, CSV, or Excel here (max {maxSizeMb} MB)
            </p>
            <input
              ref={inputRef}
              type="file"
              className="hidden"
              accept={acceptAttr}
              onChange={(e) => handleFileSelect(e.target.files?.[0])}
            />
          </div>
          {selectedFile && (
            <div className="rounded-md bg-muted/40 px-3 py-2 text-sm space-y-1">
              <p className="text-muted-foreground">
                Selected: <span className="text-foreground font-medium">{selectedFile.name}</span>
              </p>
              {analyzeExplanation && (
                <p className="text-xs text-muted-foreground">{analyzeExplanation}</p>
              )}
              {!analyzing && !draft && (
                <p className="text-xs text-primary font-medium">
                  Click {sourceType === 'csv' || sourceType === 'xlsx' ? 'Parse spreadsheet' : 'Analyze with AI'} below to build your draft.
                </p>
              )}
            </div>
          )}

          <div className="flex gap-2">
            <Button
              onClick={handleAnalyze}
              disabled={(!selectedFile && !uploadedFileId) || analyzing}
              className="min-w-[180px]"
            >
              {analyzing ? (
                <Loader2 className="h-4 w-4 animate-spin mr-2" />
              ) : (
                <Sparkles className="h-4 w-4 mr-2" />
              )}
              {analyzeButtonLabel}
            </Button>
          </div>
        </div>
      )}

      {draft && (
        <div className="space-y-4">
          <div className="rounded-md bg-muted/50 p-3 text-sm flex gap-2">
            <AlertTriangle className="h-4 w-4 shrink-0 mt-0.5 text-amber-500" />
            <p>{draft.review_message}</p>
          </div>

          {(draft.warnings || []).length > 0 && (
            <div className="text-sm text-amber-600 dark:text-amber-400 space-y-1">
              {draft.warnings.map((w, i) => (
                <p key={i}>• {w}</p>
              ))}
            </div>
          )}

          <div className="overflow-x-auto rounded-lg border">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Type</TableHead>
                  <TableHead>Phase</TableHead>
                  <TableHead>Title</TableHead>
                  <TableHead>Start</TableHead>
                  <TableHead>End</TableHead>
                  <TableHead>Confidence</TableHead>
                  <TableHead className="w-10" />
                </TableRow>
              </TableHeader>
              <TableBody>
                {draftTasks.map((task) => (
                  <TableRow
                    key={task.temp_id}
                    className={hasLowConfidence(task) ? 'bg-amber-50/50 dark:bg-amber-950/20' : ''}
                  >
                    <TableCell>
                      <Select
                        value={task.type || 'task'}
                        onValueChange={(v) => updateDraftTask(task.temp_id, 'type', v)}
                      >
                        <SelectTrigger className="h-8 w-28">
                          <SelectValue />
                        </SelectTrigger>
                        <SelectContent>
                          {taskTypes.map((type) => (
                            <SelectItem key={type} value={type}>
                              {type === 'milestone' ? 'Milestone' : 'Task'}
                            </SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
                    </TableCell>
                    <TableCell>
                      <Input
                        className="h-8 min-w-[90px]"
                        value={task.phase || ''}
                        onChange={(e) =>
                          updateDraftTask(task.temp_id, 'phase', e.target.value || null)
                        }
                      />
                    </TableCell>
                    <TableCell>
                      <Input
                        className="h-8 min-w-[140px]"
                        value={task.title || ''}
                        onChange={(e) =>
                          updateDraftTask(task.temp_id, 'title', e.target.value)
                        }
                      />
                    </TableCell>
                    <TableCell>
                      <Input
                        type="date"
                        className="h-8 w-36"
                        value={task.start_date || ''}
                        onChange={(e) =>
                          updateDraftTask(task.temp_id, 'start_date', e.target.value || null)
                        }
                      />
                    </TableCell>
                    <TableCell>
                      <Input
                        type="date"
                        className="h-8 w-36"
                        value={task.end_date || ''}
                        onChange={(e) =>
                          updateDraftTask(task.temp_id, 'end_date', e.target.value || null)
                        }
                      />
                    </TableCell>
                    <TableCell>
                      <div className="flex flex-wrap gap-1 max-w-[180px]">
                        {Object.entries(task.field_confidence || {}).map(([field, score]) => (
                          <ConfidenceBadge
                            key={field}
                            field={field}
                            confidence={score}
                            threshold={lowConfidenceThreshold}
                          />
                        ))}
                        {(task.warnings || []).map((w, i) => (
                          <Badge
                            key={i}
                            variant="outline"
                            className="text-[10px] text-amber-600"
                            title={w}
                          >
                            <AlertTriangle className="h-3 w-3 mr-0.5" />
                            warn
                          </Badge>
                        ))}
                      </div>
                    </TableCell>
                    <TableCell>
                      <Button
                        variant="ghost"
                        size="icon"
                        className="h-7 w-7 text-destructive"
                        onClick={() => removeDraftTask(task.temp_id)}
                      >
                        <Trash2 className="h-3 w-3" />
                      </Button>
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>

          <div className="flex gap-2 justify-end">
            <Button
              variant="outline"
              onClick={handleDiscard}
              disabled={discarding || confirming}
            >
              {discarding ? <Loader2 className="h-4 w-4 animate-spin mr-2" /> : null}
              Discard
            </Button>
            <Button
              variant="outline"
              onClick={handleSaveDraft}
              disabled={saving || confirming}
            >
              {saving ? <Loader2 className="h-4 w-4 animate-spin mr-2" /> : null}
              Save edits
            </Button>
            <Button onClick={handleConfirm} disabled={confirming || !draftTasks.length}>
              {confirming ? (
                <Loader2 className="h-4 w-4 animate-spin mr-2" />
              ) : (
                <Check className="h-4 w-4 mr-2" />
              )}
              Confirm import
            </Button>
          </div>
        </div>
      )}
    </div>
  );
};
