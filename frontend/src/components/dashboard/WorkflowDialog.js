import { useState } from 'react';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '../ui/dialog';
import { Button } from '../ui/button';
import { Badge } from '../ui/badge';
import { Input } from '../ui/input';
import { Label } from '../ui/label';
import { Progress } from '../ui/progress';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '../ui/select';
import { toast } from 'sonner';
import { cn } from '../../lib/utils';
import { API, getAuthHeaders } from './utils';
import {
  CreditCard,
  AlertCircle,
  CheckCircle,
  X,
  Loader2,
  Info,
  Play,
  UserPlus,
  Flag,
  Send,
  RefreshCw,
  Workflow,
} from 'lucide-react';

const getWorkflowIcon = (iconName) => {
  const icons = { UserPlus, CreditCard, Flag, Send };
  return icons[iconName] || Workflow;
};

/**
 * WorkflowDialog — owns template selection, context form, execution, and retry.
 * Does NOT own document preview or generic command logic.
 */
export const WorkflowDialog = ({
  open,
  onOpenChange,
  template,
  projectContext,
  onExecuted,
}) => {
  const [workflowContext, setWorkflowContext] = useState({});
  const [workflowResult, setWorkflowResult] = useState(null);
  const [executing, setExecuting] = useState(false);
  const [showConfirmation, setShowConfirmation] = useState(false);
  const [loadingSelectors, setLoadingSelectors] = useState(false);
  const [selectors, setSelectors] = useState({ documents: [], timelineSteps: [] });

  // Fetch selectors when dialog opens with a template that needs them
  const initSelectors = async (tmpl) => {
    if (!tmpl?.ui_selectors?.length) return;
    setLoadingSelectors(true);
    try {
      const selectorData = { documents: [], timelineSteps: [] };
      if (tmpl.ui_selectors.includes('document')) {
        const res = await fetch(`${API}/workflows/selectors?selector_type=document${projectContext.projectId ? `&project_id=${projectContext.projectId}` : ''}`, { credentials: 'include', headers: getAuthHeaders() });
        if (res.ok) { const d = await res.json(); selectorData.documents = d.items || []; }
      }
      if (tmpl.ui_selectors.includes('timeline_step')) {
        const res = await fetch(`${API}/workflows/selectors?selector_type=timeline_step${projectContext.projectId ? `&project_id=${projectContext.projectId}` : ''}`, { credentials: 'include', headers: getAuthHeaders() });
        if (res.ok) { const d = await res.json(); selectorData.timelineSteps = d.items || []; }
      }
      setSelectors(selectorData);
    } catch (e) {
      console.error('Failed to fetch selectors:', e);
    } finally {
      setLoadingSelectors(false);
    }
  };

  // Reset state when opening
  const handleOpenChange = (isOpen) => {
    if (isOpen && template) {
      setWorkflowContext({});
      setWorkflowResult(null);
      setShowConfirmation(false);
      initSelectors(template);
    }
    onOpenChange(isOpen);
  };

  const validateContext = () => {
    if (!template) return { valid: false, errors: ['No workflow selected'] };
    const errors = [];
    const required = template.required_context || [];
    if (template.ui_selectors?.includes('document') && !workflowContext.document_id) errors.push('Please select a document');
    if (template.ui_selectors?.includes('timeline_step') && !workflowContext.step_id) errors.push('Please select a timeline step');
    if (required.includes('client_name') && !workflowContext.client_name?.trim()) errors.push('Client name is required');
    if (required.includes('client_email') && !workflowContext.client_email?.trim()) errors.push('Client email is required');
    if (required.includes('message_title') && !workflowContext.message_title?.trim()) errors.push('Message title is required');
    if (required.includes('message_content') && !workflowContext.message_content?.trim()) errors.push('Message content is required');
    if (required.includes('project_id') && !projectContext.projectId) errors.push('Please select a project first');
    return { valid: errors.length === 0, errors };
  };

  const canExecute = () => validateContext().valid && !executing && !loadingSelectors;

  const execute = async () => {
    if (!template) return;
    const validation = validateContext();
    if (!validation.valid) { validation.errors.forEach((e) => toast.error(e)); return; }

    setExecuting(true);
    setWorkflowResult(null);
    try {
      const ctx = { ...workflowContext, project_id: projectContext.projectId, client_id: projectContext.clientId, unit_id: projectContext.unitId };
      const res = await fetch(`${API}/workflows/execute`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', ...getAuthHeaders() },
        credentials: 'include',
        body: JSON.stringify({ template_id: template.template_id, context: ctx, mode: 'automatic' }),
      });
      if (res.ok) {
        const result = await res.json();
        setWorkflowResult(result.execution);
        if (result.success) {
          const hasWarnings = result.execution?.progress?.warnings > 0;
          toast[hasWarnings ? 'warning' : 'success'](hasWarnings ? 'Workflow completed with warnings.' : `Workflow "${template.name}" completed!`);
          if (onExecuted) onExecuted();
        } else {
          toast.error(`Workflow failed: ${result.execution?.error || 'Unknown error'}`);
        }
      } else {
        const err = await res.json();
        toast.error(err.detail || 'Failed to execute workflow');
      }
    } catch {
      toast.error('Failed to execute workflow');
    } finally {
      setExecuting(false);
    }
  };

  const retryStep = async (executionId, stepIndex) => {
    if (!executionId || stepIndex === undefined) return;
    setExecuting(true);
    try {
      const res = await fetch(`${API}/workflows/executions/${executionId}/steps/${stepIndex}/retry`, {
        method: 'POST', credentials: 'include', headers: getAuthHeaders(),
      });
      if (res.ok) {
        const result = await res.json();
        setWorkflowResult(result.execution);
        toast[result.success ? 'success' : 'error'](result.success ? 'Step retried successfully' : `Retry failed: ${result.error || 'Unknown'}`);
      } else {
        toast.error((await res.json()).detail || 'Failed to retry step');
      }
    } catch {
      toast.error('Failed to retry step');
    } finally {
      setExecuting(false);
    }
  };

  if (!template) return null;

  const IconComponent = getWorkflowIcon(template.icon);

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <DialogContent className="max-w-lg">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <IconComponent className="w-5 h-5 text-primary" />
            {template.name}
          </DialogTitle>
          <DialogDescription>{template.description}</DialogDescription>
        </DialogHeader>

        {/* Steps Preview + Context Form */}
        {!workflowResult && (
          <div className="space-y-4 py-4">
            <div className="space-y-2">
              <Label className="text-xs uppercase tracking-wider text-muted-foreground">Workflow Steps</Label>
              <div className="space-y-2">
                {template.steps_preview?.map((step, i) => (
                  <div key={step.name || `step-${i}`} className="flex items-center gap-3 p-2 rounded-lg bg-muted/50">
                    <div className="w-6 h-6 rounded-full bg-primary/10 text-primary flex items-center justify-center text-xs font-medium">{i + 1}</div>
                    <div className="flex-1">
                      <p className="text-sm font-medium">{step.name}</p>
                      <p className="text-xs text-muted-foreground">{step.description}</p>
                    </div>
                    {step.optional && <Badge variant="outline" className="text-[10px]">Optional</Badge>}
                  </div>
                ))}
              </div>
            </div>

            {/* Context Inputs */}
            {template.required_context?.length > 0 && (
              <div className="space-y-3 pt-2 border-t">
                <Label className="text-xs uppercase tracking-wider text-muted-foreground">Required Information</Label>

                {template.required_context.includes('client_name') && (
                  <div className="space-y-1">
                    <Label htmlFor="wf-client-name" className="text-sm">Client Name</Label>
                    <Input id="wf-client-name" placeholder="Enter client name" value={workflowContext.client_name || ''} onChange={(e) => setWorkflowContext({ ...workflowContext, client_name: e.target.value })} data-testid="wf-client-name-input" />
                  </div>
                )}
                {template.required_context.includes('client_email') && (
                  <div className="space-y-1">
                    <Label htmlFor="wf-client-email" className="text-sm">Client Email</Label>
                    <Input id="wf-client-email" type="email" placeholder="client@example.com" value={workflowContext.client_email || ''} onChange={(e) => setWorkflowContext({ ...workflowContext, client_email: e.target.value })} data-testid="wf-client-email-input" />
                  </div>
                )}
                {template.required_context.includes('message_title') && (
                  <div className="space-y-1">
                    <Label htmlFor="wf-message-title" className="text-sm">Message Title</Label>
                    <Input id="wf-message-title" placeholder="Enter message title" value={workflowContext.message_title || ''} onChange={(e) => setWorkflowContext({ ...workflowContext, message_title: e.target.value })} data-testid="wf-message-title-input" />
                  </div>
                )}
                {template.required_context.includes('message_content') && (
                  <div className="space-y-1">
                    <Label htmlFor="wf-message-content" className="text-sm">Message Content</Label>
                    <Input id="wf-message-content" placeholder="Enter message content" value={workflowContext.message_content || ''} onChange={(e) => setWorkflowContext({ ...workflowContext, message_content: e.target.value })} data-testid="wf-message-content-input" />
                  </div>
                )}

                {template.ui_selectors?.includes('document') && (
                  <div className="space-y-1">
                    <Label className="text-sm">Select Document</Label>
                    {loadingSelectors ? (
                      <div className="flex items-center gap-2 text-sm text-muted-foreground"><Loader2 className="w-4 h-4 animate-spin" />Loading documents...</div>
                    ) : (
                      <Select value={workflowContext.document_id || ''} onValueChange={(v) => setWorkflowContext({ ...workflowContext, document_id: v })}>
                        <SelectTrigger data-testid="wf-document-select"><SelectValue placeholder="Select a document..." /></SelectTrigger>
                        <SelectContent>
                          {selectors.documents.length === 0 ? <SelectItem value="_none" disabled>No documents found</SelectItem> : selectors.documents.map((doc) => (
                            <SelectItem key={doc.document_id} value={doc.document_id}>
                              <div className="flex items-center gap-2">
                                <span className={cn('px-1.5 py-0.5 text-[10px] rounded', doc.type === 'Invoice' ? 'bg-blue-500/10 text-blue-600' : 'bg-purple-500/10 text-purple-600')}>{doc.type}</span>
                                <span className="truncate">{doc.title || 'Untitled'}</span>
                                <span className="text-muted-foreground text-xs">({doc.status})</span>
                              </div>
                            </SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
                    )}
                  </div>
                )}

                {template.ui_selectors?.includes('timeline_step') && (
                  <div className="space-y-1">
                    <Label className="text-sm">Select Timeline Step</Label>
                    {loadingSelectors ? (
                      <div className="flex items-center gap-2 text-sm text-muted-foreground"><Loader2 className="w-4 h-4 animate-spin" />Loading steps...</div>
                    ) : (
                      <Select value={workflowContext.step_id || ''} onValueChange={(v) => setWorkflowContext({ ...workflowContext, step_id: v })}>
                        <SelectTrigger data-testid="wf-step-select"><SelectValue placeholder="Select a step..." /></SelectTrigger>
                        <SelectContent>
                          {selectors.timelineSteps.length === 0 ? <SelectItem value="_none" disabled>No steps found</SelectItem> : selectors.timelineSteps.map((step) => (
                            <SelectItem key={step.step_id} value={step.step_id}>
                              <div className="flex items-center gap-2">
                                <span className={cn('w-2 h-2 rounded-full', step.status === 'completed' ? 'bg-emerald-500' : step.status === 'in_progress' ? 'bg-amber-500' : 'bg-gray-300')} />
                                <span className="truncate">{step.name}</span>
                                <span className="text-muted-foreground text-xs">({step.project_name})</span>
                              </div>
                            </SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
                    )}
                  </div>
                )}

                {template.required_context.includes('project_id') && !template.ui_selectors?.length && (
                  <div className={cn('text-xs flex items-center gap-1 p-2 rounded', projectContext.projectId ? 'text-muted-foreground bg-muted/50' : 'text-amber-600 bg-amber-500/10')}>
                    {projectContext.projectId ? <><Info className="w-3 h-3" />Project: {projectContext.projectName || 'Selected'}</> : <><AlertCircle className="w-3 h-3" />Please select a project first</>}
                  </div>
                )}

                {!canExecute() && !loadingSelectors && (
                  <div className="text-xs text-amber-600 flex items-center gap-1 mt-2">
                    <AlertCircle className="w-3 h-3" />Fill in required fields to enable workflow execution
                  </div>
                )}
              </div>
            )}
          </div>
        )}

        {/* Workflow Result */}
        {workflowResult && (
          <WorkflowResultView result={workflowResult} executing={executing} onRetry={retryStep} />
        )}

        <DialogFooter>
          <Button variant="outline" onClick={() => { handleOpenChange(false); setWorkflowResult(null); setShowConfirmation(false); }}>
            {workflowResult ? 'Close' : 'Cancel'}
          </Button>
          {!workflowResult && (
            <Button
              onClick={() => {
                const isDestructive = template && ['invoice_paid_processing'].includes(template.template_id);
                if (isDestructive && !showConfirmation) { setShowConfirmation(true); } else { execute(); setShowConfirmation(false); }
              }}
              disabled={!canExecute()}
              data-testid="execute-workflow-btn"
              className={showConfirmation ? 'bg-amber-600 hover:bg-amber-700' : ''}
            >
              {executing ? <Loader2 className="w-4 h-4 mr-2 animate-spin" /> : showConfirmation ? <AlertCircle className="w-4 h-4 mr-2" /> : <Play className="w-4 h-4 mr-2" />}
              {showConfirmation ? 'Confirm & Run' : 'Run Workflow'}
            </Button>
          )}
        </DialogFooter>

        {showConfirmation && !workflowResult && (
          <div className="mt-4 p-3 rounded-lg bg-amber-500/15 border border-amber-500/40">
            <div className="flex items-start gap-2">
              <AlertCircle className="w-4 h-4 text-amber-600 mt-0.5 flex-shrink-0" />
              <div>
                <p className="text-sm font-medium text-amber-800 dark:text-amber-200">This action will modify data</p>
                <p className="text-xs text-amber-700 dark:text-amber-300 mt-1">
                  {template.template_id === 'invoice_paid_processing'
                    ? 'This will mark the selected invoice as Paid. This action cannot be easily undone.'
                    : 'This workflow will modify records. Please confirm to proceed.'}
                </p>
              </div>
            </div>
          </div>
        )}
      </DialogContent>
    </Dialog>
  );
};

const WorkflowResultView = ({ result, executing, onRetry }) => (
  <div className="space-y-4 py-4">
    <div className="flex items-center gap-2">
      {result.status === 'completed' ? <CheckCircle className="w-5 h-5 text-emerald-500" />
        : result.status === 'completed_with_warnings' ? <AlertCircle className="w-5 h-5 text-amber-500" />
        : result.status === 'failed' ? <AlertCircle className="w-5 h-5 text-destructive" />
        : <Loader2 className="w-5 h-5 animate-spin text-primary" />}
      <span className="font-medium">
        {result.status === 'completed' ? 'Workflow Completed' : result.status === 'completed_with_warnings' ? 'Completed with Warnings' : result.status === 'failed' ? 'Workflow Failed' : 'In Progress'}
      </span>
    </div>

    {result.status === 'completed_with_warnings' && (
      <div className="p-3 rounded-lg bg-amber-500/15 border border-amber-500/40">
        <div className="flex items-start gap-2">
          <AlertCircle className="w-4 h-4 text-amber-600 mt-0.5 flex-shrink-0" />
          <div>
            <p className="text-sm font-medium text-amber-800 dark:text-amber-200">Some steps completed with warnings</p>
            <p className="text-xs text-amber-700 dark:text-amber-300 mt-1">Main actions succeeded, but some side effects may have failed.</p>
          </div>
        </div>
      </div>
    )}

    <Progress value={(result.progress?.completed / result.progress?.total) * 100} className="h-2" />

    <div className="space-y-2">
      {result.steps?.map((step, i) => (
        <div key={step.name || `step-${i}`} className={cn('flex items-center gap-3 p-2 rounded-lg',
          step.status === 'completed' && 'bg-emerald-500/10',
          step.status === 'completed_with_warning' && 'bg-amber-500/15 border border-amber-500/30',
          step.status === 'failed' && 'bg-destructive/10 border border-destructive/30',
          step.status === 'skipped' && 'bg-muted'
        )} data-testid={`workflow-step-${i}`}>
          {step.status === 'completed' ? <CheckCircle className="w-4 h-4 text-emerald-500" />
            : step.status === 'completed_with_warning' ? <AlertCircle className="w-4 h-4 text-amber-500" />
            : step.status === 'failed' ? <AlertCircle className="w-4 h-4 text-destructive" />
            : step.status === 'skipped' ? <X className="w-4 h-4 text-muted-foreground" />
            : <div className="w-4 h-4 rounded-full border-2 border-muted-foreground" />}
          <div className="flex-1 min-w-0">
            <p className="text-sm">{step.name}</p>
            {step.error && <p className="text-xs text-destructive mt-0.5">{step.error}</p>}
            {step.warning && <p className="text-xs text-amber-600 dark:text-amber-400 mt-0.5"><span className="font-medium">Warning:</span> {step.warning}</p>}
          </div>
          {step.can_retry && (
            <Button variant="outline" size="sm"
              className={cn('h-7 px-2 text-xs flex-shrink-0',
                step.status === 'failed' && 'border-destructive/50 text-destructive hover:bg-destructive/10',
                step.status === 'completed_with_warning' && 'border-amber-500/50 text-amber-600 hover:bg-amber-500/10'
              )}
              onClick={() => onRetry(result.execution_id, step.step_index)}
              disabled={executing}
              data-testid={`retry-step-${i}`}
            >
              {executing ? <Loader2 className="w-3 h-3 animate-spin" /> : <><RefreshCw className="w-3 h-3 mr-1" />Retry</>}
            </Button>
          )}
        </div>
      ))}
    </div>
  </div>
);
