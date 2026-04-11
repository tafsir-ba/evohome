import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Sheet, SheetContent, SheetHeader, SheetTitle, SheetFooter } from '../ui/sheet';
import { Button } from '../ui/button';
import { Badge } from '../ui/badge';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../ui/select';
import { toast } from 'sonner';
import { cn } from '../../lib/utils';
import { API, getAuthHeaders, getIntentLabel, formatCurrency, getConfidenceDisplay } from './utils';
import {
  FileText,
  Calendar,
  Building2,
  Clock,
  AlertCircle,
  CheckCircle,
  FileUp,
  X,
  ChevronRight,
  Sparkles,
  Loader2,
  Pencil,
  User,
  RefreshCw,
  Info,
} from 'lucide-react';

/**
 * ActionPreviewDrawer — shows extraction results, classification, and execution controls.
 * Owns: overrideDocType, reExtracting, executing state.
 * Receives: previewData, open state, context for re-extraction, callbacks.
 */
export const ActionPreviewDrawer = ({
  open,
  onOpenChange,
  previewData,
  setPreviewData,
  context,
  uploadedFileRef,
  onExecuted,
}) => {
  const navigate = useNavigate();
  const [overrideDocType, setOverrideDocType] = useState(null);
  const [reExtracting, setReExtracting] = useState(false);
  const [executing, setExecuting] = useState(false);

  const handleReExtract = async (newDocType = null) => {
    const filePath = previewData?.source_file || previewData?.classification?.file_path;
    const originalFile = previewData?.original_file;
    const refFile = uploadedFileRef?.current;
    const availableFile = originalFile || refFile;

    if (!filePath && !availableFile) {
      toast.error('No source file available. Please re-upload.');
      return;
    }

    setReExtracting(true);
    const docType = newDocType || overrideDocType || previewData?.document_type || previewData?.classification?.document_type || 'unknown';

    try {
      toast.info(`Re-extracting as ${docType}...`);
      let actualFilePath = filePath;

      if (!actualFilePath && availableFile) {
        toast.info('Re-uploading document...');
        const classifyForm = new FormData();
        classifyForm.append('file', availableFile);
        const classifyRes = await fetch(`${API}/command/classify-document`, {
          method: 'POST', credentials: 'include', headers: getAuthHeaders(), body: classifyForm,
        });
        if (!classifyRes.ok) throw new Error('Re-upload failed');
        const classification = await classifyRes.json();
        actualFilePath = classification.file_path;
        setPreviewData((prev) => ({ ...prev, source_file: actualFilePath, classification, original_file: availableFile }));
      }

      const extractForm = new FormData();
      extractForm.append('file_path', actualFilePath);
      extractForm.append('document_type', docType);
      extractForm.append('context', JSON.stringify({
        project_id: context.projectId, client_id: context.clientId, unit_id: context.unitId,
      }));

      const extractRes = await fetch(`${API}/command/extract-document`, {
        method: 'POST', credentials: 'include', headers: getAuthHeaders(), body: extractForm,
      });
      if (!extractRes.ok) throw new Error('Re-extraction failed');

      const plan = await extractRes.json();
      plan.classification = { ...previewData.classification, document_type: docType, was_overridden: newDocType !== null };
      plan.attachments = previewData.attachments;
      plan.original_file = availableFile;
      plan.source_file = actualFilePath;

      setPreviewData(plan);
      setOverrideDocType(null);
      toast.success('Extraction complete');
    } catch {
      toast.error('Re-extraction failed.');
    } finally {
      setReExtracting(false);
    }
  };

  const handleExecute = async () => {
    if (!previewData) return;
    setExecuting(true);

    try {
      const draftRes = await fetch(`${API}/command/draft`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', ...getAuthHeaders() },
        credentials: 'include',
        body: JSON.stringify(previewData),
      });
      if (!draftRes.ok) throw new Error((await draftRes.json()).detail || 'Failed to create draft');
      const draft = await draftRes.json();

      const execRes = await fetch(`${API}/command/execute`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', ...getAuthHeaders() },
        credentials: 'include',
        body: JSON.stringify({ draft_id: draft.draft_id, confirmed: true }),
      });

      if (execRes.ok) {
        const result = await execRes.json();
        const docType = result.result?.type || previewData.intent.replace('create_', '');
        const docNumber = result.result?.number || '';
        toast.success(`${docType.charAt(0).toUpperCase() + docType.slice(1)} ${docNumber} created!`);

        setTimeout(() => {
          if (result.result?.redirect) navigate(result.result.redirect);
          else {
            const path = docType === 'invoice' ? '/agent/invoices' : docType === 'quote' ? '/agent/quotes' : '/agent/feed';
            navigate(path);
          }
        }, 500);
      } else {
        throw new Error((await execRes.json()).detail || 'Execution failed');
      }
    } catch (error) {
      if (previewData.suggested_action?.path) {
        navigate(previewData.suggested_action.path);
        toast.info(`Navigating to ${previewData.suggested_action.label}`);
      } else {
        toast.error(error.message || 'Failed to execute');
      }
    } finally {
      setExecuting(false);
      onOpenChange(false);
      if (onExecuted) onExecuted();
    }
  };

  if (!previewData) return null;

  const effectiveCanExecute = previewData.can_execute || (
    overrideDocType && overrideDocType !== 'unknown' &&
    !previewData.missing_fields?.some((f) => f.required && f.name !== 'document_type')
  );

  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent className="sm:max-w-lg overflow-y-auto">
        <SheetHeader>
          <SheetTitle className="flex items-center gap-2">
            <Sparkles className="w-5 h-5 text-primary" />
            Action Preview
          </SheetTitle>
        </SheetHeader>

        <div className="mt-6 space-y-5">
          {/* Intent & Confidence */}
          <IntentBadge data={previewData} />

          {/* Document Classification */}
          {(previewData.classification || previewData.document_type) && (
            <ClassificationSection
              data={previewData}
              overrideDocType={overrideDocType}
              onOverrideChange={setOverrideDocType}
              onReExtract={handleReExtract}
              reExtracting={reExtracting}
            />
          )}

          {/* Validation Errors */}
          {previewData.validation_errors?.length > 0 && (
            <div className="p-3 rounded-lg bg-destructive/10 border border-destructive/20">
              <p className="text-xs font-semibold uppercase tracking-wider text-destructive mb-2">Validation Issues</p>
              <ul className="text-sm space-y-1">
                {previewData.validation_errors.map((err, i) => (
                  <li key={`err-${i}`} className="text-destructive flex items-center gap-2">
                    <X className="w-3 h-3" />{err}
                  </li>
                ))}
              </ul>
            </div>
          )}

          {/* Timeline Warning */}
          {previewData.timeline_exists && previewData.existing_timeline && (
            <TimelineWarning data={previewData} navigate={navigate} onClose={() => onOpenChange(false)} />
          )}

          {/* Target Context */}
          {(previewData.entities?.project_name || previewData.entities?.client_name) && (
            <div>
              <p className="text-xs font-semibold uppercase tracking-wider text-muted-foreground mb-2">Target Context</p>
              <div className="space-y-2">
                {previewData.entities.project_name && (
                  <div className="flex items-center gap-2 p-2 rounded-lg bg-muted/30">
                    <Building2 className="w-4 h-4 text-muted-foreground" />
                    <span className="text-sm">{previewData.entities.project_name}</span>
                  </div>
                )}
                {previewData.entities.client_name && (
                  <div className="flex items-center gap-2 p-2 rounded-lg bg-muted/30">
                    <User className="w-4 h-4 text-muted-foreground" />
                    <span className="text-sm">{previewData.entities.client_name}</span>
                  </div>
                )}
              </div>
            </div>
          )}

          {/* Extracted Fields */}
          <ExtractedFields fields={previewData.fields} />

          {/* Timeline Stages */}
          <TimelineStages fields={previewData.fields} />

          {/* Missing Fields */}
          <MissingFields fields={previewData.missing_fields} />

          {/* Attachments */}
          {previewData.attachments?.length > 0 && (
            <div>
              <p className="text-xs font-semibold uppercase tracking-wider text-muted-foreground mb-2">Attachments</p>
              <div className="space-y-2">
                {previewData.attachments.map((file, i) => (
                  <div key={file.name || `att-${i}`} className="flex items-center gap-2 p-2 rounded-lg bg-muted/50">
                    <FileUp className="w-4 h-4" />
                    <span className="text-sm truncate">{file.name}</span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Raw Command */}
          {previewData.raw_command && (
            <div>
              <p className="text-xs font-semibold uppercase tracking-wider text-muted-foreground mb-2">Your Command</p>
              <p className="text-sm italic bg-muted/50 p-3 rounded-lg">"{previewData.raw_command}"</p>
            </div>
          )}

          {/* Execution Status */}
          <div className={cn(
            'p-4 rounded-lg border',
            effectiveCanExecute ? 'bg-emerald-500/10 border-emerald-500/30' : 'bg-amber-500/10 border-amber-500/30'
          )}>
            <div className="flex items-center gap-2">
              {effectiveCanExecute ? (
                <>
                  <CheckCircle className="w-5 h-5 text-emerald-500" />
                  <div>
                    <p className="font-medium text-emerald-700 dark:text-emerald-400">Ready to Execute</p>
                    <p className="text-xs text-emerald-600 dark:text-emerald-500">All required fields are present</p>
                  </div>
                </>
              ) : (
                <>
                  <AlertCircle className="w-5 h-5 text-amber-500" />
                  <div>
                    <p className="font-medium text-amber-700 dark:text-amber-400">
                      {!overrideDocType && (previewData.document_type === 'unknown' || !previewData.document_type)
                        ? 'Select Document Type' : 'Cannot Execute'}
                    </p>
                    <p className="text-xs text-amber-600 dark:text-amber-500">
                      {!overrideDocType && (previewData.document_type === 'unknown' || !previewData.document_type)
                        ? 'Choose a type above, then click Re-run Extraction' : 'Fill in missing required fields first'}
                    </p>
                  </div>
                </>
              )}
            </div>
          </div>

          {/* Debug Log */}
          {previewData.interpretation_log?.length > 0 && (
            <details className="group">
              <summary className="cursor-pointer text-xs font-semibold uppercase tracking-wider text-muted-foreground flex items-center gap-1">
                <ChevronRight className="w-3 h-3 group-open:rotate-90 transition-transform" />
                Debug Log
              </summary>
              <div className="mt-2 p-2 rounded-lg bg-muted/30 font-mono text-xs space-y-1">
                {previewData.interpretation_log.map((log, i) => (
                  <p key={`log-${i}`} className="text-muted-foreground">{log}</p>
                ))}
              </div>
            </details>
          )}
        </div>

        <SheetFooter className="mt-8 gap-2">
          <Button variant="outline" onClick={() => onOpenChange(false)} disabled={executing}>Cancel</Button>
          <Button
            variant="outline"
            onClick={() => {
              const editPaths = { 'create_invoice': '/agent/invoices/new', 'create_quote': '/agent/quotes/new', 'create_message': '/agent/feed' };
              const path = editPaths[previewData?.intent] || previewData?.suggested_action?.path;
              if (path) { navigate(path); onOpenChange(false); }
            }}
            disabled={executing}
          >
            <Pencil className="w-4 h-4 mr-2" />Edit Manually
          </Button>
          <Button
            onClick={handleExecute}
            disabled={executing || !effectiveCanExecute}
            data-testid="confirm-action-btn"
          >
            {executing ? <Loader2 className="w-4 h-4 mr-2 animate-spin" /> : <CheckCircle className="w-4 h-4 mr-2" />}
            Create Draft
          </Button>
        </SheetFooter>
      </SheetContent>
    </Sheet>
  );
};

// --- Sub-components for readability ---

const IntentBadge = ({ data }) => (
  <div className="p-4 rounded-lg bg-muted/50 border border-border">
    <div className="flex items-center justify-between mb-3">
      <p className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">Detected Intent</p>
      {(data.intent_confidence || data.confidence) && (
        <Badge variant={(data.intent_confidence || data.confidence) >= 0.8 ? 'default' : (data.intent_confidence || data.confidence) >= 0.5 ? 'secondary' : 'outline'} className="text-xs">
          {Math.round((data.intent_confidence || data.confidence) * 100)}% confidence
        </Badge>
      )}
    </div>
    <div className="flex items-center gap-2">
      <Badge variant={data.can_execute ? 'default' : 'secondary'} className="text-sm py-1.5 px-3">
        {getIntentLabel(data.intent)}
      </Badge>
      {data.is_valid && <CheckCircle className="w-4 h-4 text-emerald-500" />}
      {!data.is_valid && data.intent !== 'unknown' && <AlertCircle className="w-4 h-4 text-amber-500" />}
    </div>
  </div>
);

const ClassificationSection = ({ data, overrideDocType, onOverrideChange, onReExtract, reExtracting }) => (
  <div className="p-4 rounded-lg bg-blue-500/10 border border-blue-500/30">
    <div className="flex items-center justify-between mb-3">
      <p className="text-xs font-semibold uppercase tracking-wider text-blue-600 dark:text-blue-400">Document Classification</p>
      {data.classification?.was_overridden && <Badge variant="outline" className="text-xs border-amber-500/50 text-amber-600">Overridden</Badge>}
    </div>
    {data.classification?.filename && (
      <div className="flex items-center gap-2 text-sm mb-3">
        <FileUp className="w-4 h-4 text-blue-500" />
        <span className="text-muted-foreground truncate">{data.classification.filename}</span>
      </div>
    )}
    <div className="flex items-center gap-2 mb-3">
      <span className="text-sm text-muted-foreground">Type:</span>
      <Select
        value={overrideDocType || (data.document_type !== 'unknown' ? data.document_type : undefined) || (data.classification?.document_type !== 'unknown' ? data.classification?.document_type : undefined)}
        onValueChange={onOverrideChange}
      >
        <SelectTrigger className="w-40 h-8 text-sm"><SelectValue placeholder="Select type..." /></SelectTrigger>
        <SelectContent>
          <SelectItem value="quote">Quote</SelectItem>
          <SelectItem value="invoice">Invoice</SelectItem>
          <SelectItem value="timeline">Timeline</SelectItem>
          <SelectItem value="contacts">Contacts</SelectItem>
        </SelectContent>
      </Select>
      <span className={cn('text-xs px-2 py-0.5 rounded', getConfidenceDisplay(data.classification?.confidence || data.intent_confidence || 0.5).color)}>
        {getConfidenceDisplay(data.classification?.confidence || data.intent_confidence || 0.5).label}
      </span>
    </div>
    <Button variant="outline" size="sm" onClick={() => onReExtract(overrideDocType)} disabled={reExtracting} className="w-full border-blue-500/30 text-blue-600 hover:bg-blue-500/10">
      {reExtracting ? <Loader2 className="w-4 h-4 mr-2 animate-spin" /> : <RefreshCw className="w-4 h-4 mr-2" />}
      {overrideDocType && overrideDocType !== (data.document_type || data.classification?.document_type) ? `Re-extract as ${overrideDocType}` : 'Re-run Extraction'}
    </Button>
  </div>
);

const TimelineWarning = ({ data, navigate, onClose }) => (
  <div className="p-4 rounded-lg bg-amber-500/10 border border-amber-500/30">
    <div className="flex items-start gap-3">
      <AlertCircle className="w-5 h-5 text-amber-600 flex-shrink-0 mt-0.5" />
      <div className="flex-1">
        <p className="font-medium text-amber-800 dark:text-amber-200">Timeline Already Exists</p>
        <p className="text-sm text-amber-700 dark:text-amber-300 mt-1">
          This project already has a timeline: <strong>"{data.existing_timeline.name}"</strong>
        </p>
        <p className="text-xs text-amber-600 dark:text-amber-400 mt-2">{data.message}</p>
        <div className="flex gap-2 mt-3">
          {data.available_actions?.map((action) => (
            <Button
              key={action.action}
              variant={action.action === 'view' ? 'default' : 'outline'}
              size="sm"
              onClick={() => { if (action.action === 'view') { navigate(action.path); onClose(); } }}
              className={action.action !== 'view' ? 'border-amber-500/50 text-amber-700 hover:bg-amber-500/10' : ''}
            >
              {action.label}
            </Button>
          ))}
        </div>
      </div>
    </div>
  </div>
);

const ExtractedFields = ({ fields }) => {
  if (!fields?.length) return null;
  return (
    <div>
      <div className="flex items-center justify-between mb-2">
        <p className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">Extracted Fields</p>
        <div className="flex items-center gap-1 text-xs text-muted-foreground"><Info className="w-3 h-3" /><span>Confidence per field</span></div>
      </div>
      <div className="space-y-2">
        {fields.map((field, i) => {
          const conf = getConfidenceDisplay(field.confidence || 0.5);
          return (
            <div key={field.name || `field-${i}`} className="flex items-center justify-between p-3 rounded-lg border border-border bg-card hover:bg-muted/20 transition-colors">
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2 mb-1">
                  <span className="text-xs font-medium uppercase text-muted-foreground">{field.name.replace(/_/g, ' ')}</span>
                  <span className={cn('text-[10px] px-1.5 py-0.5 rounded font-medium', conf.color)}>{conf.label}</span>
                  {field.source === 'ai_extraction' && <span className="text-[10px] px-1.5 py-0.5 rounded bg-purple-500/10 text-purple-600">AI</span>}
                  {field.source === 'context' && <span className="text-[10px] px-1.5 py-0.5 rounded bg-blue-500/10 text-blue-600">Context</span>}
                </div>
                <p className="text-sm font-medium truncate">
                  {field.name === 'amount' ? formatCurrency(field.value)
                    : (field.name === 'line_items' || field.name === 'stages') && Array.isArray(field.value) ? `${field.value.length} items`
                    : Array.isArray(field.value) ? `${field.value.length} items`
                    : typeof field.value === 'object' && field.value !== null ? JSON.stringify(field.value).substring(0, 60)
                    : String(field.value || '\u2014').substring(0, 60)}
                </p>
              </div>
              {field.confidence < 0.5 && <AlertCircle className="w-4 h-4 text-amber-500 flex-shrink-0 ml-2" />}
            </div>
          );
        })}
      </div>
    </div>
  );
};

const TimelineStages = ({ fields }) => {
  const stages = fields?.find((f) => f.name === 'stages' && Array.isArray(f.value) && f.value.length > 0)?.value;
  if (!stages) return null;
  return (
    <div>
      <p className="text-xs font-semibold uppercase tracking-wider text-muted-foreground mb-2">Timeline Stages</p>
      <div className="space-y-2">
        {stages.map((stage, i) => (
          <div key={stage.name || `stage-${i}`} className="p-3 rounded-lg border border-border bg-card">
            <div className="flex items-center justify-between mb-1">
              <span className="font-medium text-sm">{stage.name || stage.title || `Stage ${i + 1}`}</span>
              {stage.status && (
                <span className={cn('text-xs px-2 py-0.5 rounded',
                  stage.status === 'completed' ? 'bg-emerald-500/10 text-emerald-600' :
                  stage.status === 'in_progress' ? 'bg-blue-500/10 text-blue-600' : 'bg-muted text-muted-foreground'
                )}>{stage.status.replace('_', ' ')}</span>
              )}
            </div>
            {(stage.date_text || stage.start_date || stage.end_date || stage.date) && (
              <p className="text-xs text-muted-foreground flex items-center gap-1">
                <Calendar className="w-3 h-3" />
                {stage.date_text || (stage.start_date && stage.end_date ? `${stage.start_date} \u2192 ${stage.end_date}` : stage.date || stage.start_date || stage.end_date)}
              </p>
            )}
            {stage.description && <p className="text-xs text-muted-foreground mt-1">{stage.description}</p>}
          </div>
        ))}
      </div>
    </div>
  );
};

const MissingFields = ({ fields }) => {
  if (!fields?.length) return null;
  return (
    <div>
      <p className="text-xs font-semibold uppercase tracking-wider text-muted-foreground mb-2">Missing Fields</p>
      <div className="space-y-2">
        {fields.map((field, i) => (
          <div key={field.name || `missing-${i}`} className={cn('flex items-start gap-2 p-2 rounded-lg border', field.required ? 'bg-amber-500/10 border-amber-500/30' : 'bg-muted/30 border-border')}>
            {field.required ? <AlertCircle className="w-4 h-4 text-amber-500 mt-0.5 flex-shrink-0" /> : <Clock className="w-4 h-4 text-muted-foreground mt-0.5 flex-shrink-0" />}
            <div>
              <p className="text-sm font-medium capitalize">{field.name.replace(/_/g, ' ')}{field.required && <span className="text-amber-500 ml-1">*</span>}</p>
              <p className="text-xs text-muted-foreground">{field.description}</p>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
};
