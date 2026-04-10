import { useState, useEffect, useRef, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { AgentLayout } from '../../components/AgentLayout';
import { Card, CardContent, CardHeader, CardTitle } from '../../components/ui/card';
import { useDataContext } from '../../context/DataContext';
import { Button } from '../../components/ui/button';
import { Input } from '../../components/ui/input';
import { Badge } from '../../components/ui/badge';
import { 
  Select, 
  SelectContent, 
  SelectItem, 
  SelectTrigger, 
  SelectValue 
} from '../../components/ui/select';
import { Sheet, SheetContent, SheetHeader, SheetTitle, SheetFooter } from '../../components/ui/sheet';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogFooter } from '../../components/ui/dialog';
import { Label } from '../../components/ui/label';
import { Progress } from '../../components/ui/progress';
import { toast } from 'sonner';
import { cn } from '../../lib/utils';
import {
  Mic,
  MicOff,
  Upload,
  Send,
  FileText,
  Calendar,
  CreditCard,
  Building2,
  Clock,
  AlertCircle,
  CheckCircle,
  FileUp,
  X,
  ChevronRight,
  Sparkles,
  Loader2,
  Home,
  Pencil,
  User,
  RefreshCw,
  Info,
  Play,
  UserPlus,
  Flag,
  Workflow,
  ChevronDown,
  ChevronUp
} from 'lucide-react';

const API = process.env.REACT_APP_BACKEND_URL + '/api';

export const AgentHomePage = () => {
  const navigate = useNavigate();
  
  // SINGLE SOURCE OF TRUTH: DataContext
  // Projects come from context - NO independent fetch allowed
  const { 
    projects, 
    selectedProject,
    selectedProjectId,
    setSelectedProjectId,
    loading: projectsLoading,
    refreshProjects
  } = useDataContext();
  
  // Command state
  const [commandText, setCommandText] = useState('');
  const [isListening, setIsListening] = useState(false);
  const [isProcessing, setIsProcessing] = useState(false);
  const [attachments, setAttachments] = useState([]);
  const [isDragActive, setIsDragActive] = useState(false);
  const fileInputRef = useRef(null);
  const commandInputRef = useRef(null);
  
  // Local state for context-dependent data (clients, units)
  const [selectedClient, setSelectedClient] = useState('');
  const [selectedUnit, setSelectedUnit] = useState('');
  
  // Track current fetch to ignore stale responses
  const currentProjectFetchRef = useRef(null);
  
  // Context-dependent data (fetched when project changes)
  const [clients, setClients] = useState([]);
  const [units, setUnits] = useState([]);
  const [recentWork, setRecentWork] = useState([]);
  const [contextLoading, setContextLoading] = useState(false);
  
  // Preview drawer state
  const [previewOpen, setPreviewOpen] = useState(false);
  const [previewData, setPreviewData] = useState(null);
  const [executing, setExecuting] = useState(false);
  const [reExtracting, setReExtracting] = useState(false);
  const [overrideDocType, setOverrideDocType] = useState(null);

  // CRITICAL: Store uploaded file in a ref that persists across re-renders
  // This ensures the file is available for re-extraction even after state changes
  const uploadedFileRef = useRef(null);

  // Speech recognition
  const recognitionRef = useRef(null);

  // Keyboard shortcut: Cmd+K / Ctrl+K to focus command bar
  useEffect(() => {
    const handleKeyDown = (e) => {
      if ((e.metaKey || e.ctrlKey) && e.key === 'k') {
        e.preventDefault();
        commandInputRef.current?.focus();
      }
    };
    
    document.addEventListener('keydown', handleKeyDown);
    return () => document.removeEventListener('keydown', handleKeyDown);
  }, []);

  // Workflow state (for dialog - workflows hidden from homepage but dialog still functional)
  const [workflowTemplates, setWorkflowTemplates] = useState([]);
  const [workflowDialogOpen, setWorkflowDialogOpen] = useState(false);
  const [selectedWorkflow, setSelectedWorkflow] = useState(null);
  const [workflowContext, setWorkflowContext] = useState({});
  const [workflowExecuting, setWorkflowExecuting] = useState(false);
  const [workflowResult, setWorkflowResult] = useState(null);
  const [workflowSelectors, setWorkflowSelectors] = useState({ documents: [], timelineSteps: [] });
  const [loadingSelectors, setLoadingSelectors] = useState(false);
  const [showConfirmation, setShowConfirmation] = useState(false);

  useEffect(() => {
    // Projects are fetched by DataContext - only fetch secondary data here
    fetchRecentWork();
    initSpeechRecognition();
    fetchWorkflowTemplates();
  }, []);

  // Track last fetched project and fetching state
  const lastContextProjectRef = useRef(null);
  const fetchingContextRef = useRef(false);

  // On project change, fetch context-dependent data (clients, units)
  // selectedProjectId comes from DataContext - single source of truth
  useEffect(() => {
    // Skip if already fetching
    if (fetchingContextRef.current) return;
    
    // Skip if project hasn't actually changed
    if (lastContextProjectRef.current === selectedProjectId) {
      return;
    }
    
    const fetchId = Date.now();
    currentProjectFetchRef.current = fetchId;
    
    // Only clear state if switching to a DIFFERENT project (not initial load)
    if (lastContextProjectRef.current !== null && lastContextProjectRef.current !== selectedProjectId) {
      setClients([]);
      setUnits([]);
      setSelectedClient('');
      setSelectedUnit('');
    }
    
    lastContextProjectRef.current = selectedProjectId;
    
    if (selectedProjectId) {
      fetchingContextRef.current = true;
      fetchProjectContext(selectedProjectId, fetchId).finally(() => {
        fetchingContextRef.current = false;
      });
    }
  }, [selectedProjectId]);

  const [voiceSupported, setVoiceSupported] = useState(true);
  
  const initSpeechRecognition = () => {
    if ('webkitSpeechRecognition' in window || 'SpeechRecognition' in window) {
      const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
      recognitionRef.current = new SpeechRecognition();
      recognitionRef.current.continuous = false;
      recognitionRef.current.interimResults = true;
      recognitionRef.current.lang = 'en-US';

      recognitionRef.current.onresult = (event) => {
        const transcript = Array.from(event.results)
          .map(result => result[0].transcript)
          .join('');
        setCommandText(transcript);
      };

      recognitionRef.current.onend = () => {
        setIsListening(false);
      };

      recognitionRef.current.onerror = (event) => {
        console.error('Speech recognition error:', event.error);
        setIsListening(false);
        
        // Provide specific error messages based on error type
        const errorMessages = {
          'not-allowed': 'Microphone access denied. Please enable microphone permissions.',
          'no-speech': 'No speech detected. Please try again.',
          'audio-capture': 'No microphone found. Please connect a microphone.',
          'network': 'Network error. Please check your connection.',
          'aborted': 'Voice input cancelled.',
          'service-not-allowed': 'Voice recognition not available in this browser.'
        };
        
        const message = errorMessages[event.error] || 'Voice input failed. Please try again or type your command.';
        toast.error(message);
      };
      
      setVoiceSupported(true);
    } else {
      // Browser doesn't support speech recognition
      setVoiceSupported(false);
      console.warn('Speech recognition not supported in this browser');
    }
  };

  // Fetch recent work - independent of project fetching (secondary data)
  const fetchRecentWork = async () => {
    try {
      const res = await fetch(`${API}/command/recent-work`, { credentials: 'include' });
      if (res.ok) {
        const data = await res.json();
        setRecentWork(data.items || []);
      }
    } catch (error) {
      console.error('Failed to fetch recent work:', error);
    }
  };

  // Fetch project context (clients, units) - depends on selectedProjectId from DataContext
  // Called when project selection changes
  const fetchProjectContext = async (projectId, fetchId) => {
    if (!projectId) {
      setClients([]);
      setUnits([]);
      return;
    }
    
    try {
      const res = await fetch(`${API}/projects/${projectId}/context`, { credentials: 'include' });
      // Ignore if project changed
      if (currentProjectFetchRef.current !== fetchId) return;
      
      if (res.ok) {
        const data = await res.json();
        setClients(data.clients || []);
        setUnits(data.units || []);
      }
    } catch (error) {
      console.error('Failed to fetch project context:', error);
    }
  };

  // Fetch workflow templates
  const fetchWorkflowTemplates = async () => {
    try {
      const res = await fetch(`${API}/workflows/templates`, { credentials: 'include' });
      if (res.ok) {
        const data = await res.json();
        setWorkflowTemplates(data.templates || []);
      }
    } catch (error) {
      console.error('Failed to fetch workflow templates:', error);
    }
  };

  // Get icon component for workflow
  const getWorkflowIcon = (iconName) => {
    const icons = {
      'UserPlus': UserPlus,
      'CreditCard': CreditCard,
      'Flag': Flag,
      'Send': Send,
      'Megaphone': Megaphone
    };
    return icons[iconName] || Workflow;
  };

  // Validate workflow context before execution
  const validateWorkflowContext = () => {
    if (!selectedWorkflow) return { valid: false, errors: ['No workflow selected'] };
    
    const errors = [];
    const required = selectedWorkflow.required_context || [];
    
    // Check selector-based requirements
    if (selectedWorkflow.ui_selectors?.includes('document') && !workflowContext.document_id) {
      errors.push('Please select a document');
    }
    if (selectedWorkflow.ui_selectors?.includes('timeline_step') && !workflowContext.step_id) {
      errors.push('Please select a timeline step');
    }
    
    // Check manual input requirements
    if (required.includes('client_name') && !workflowContext.client_name?.trim()) {
      errors.push('Client name is required');
    }
    if (required.includes('client_email') && !workflowContext.client_email?.trim()) {
      errors.push('Client email is required');
    }
    if (required.includes('message_title') && !workflowContext.message_title?.trim()) {
      errors.push('Message title is required');
    }
    if (required.includes('message_content') && !workflowContext.message_content?.trim()) {
      errors.push('Message content is required');
    }
    
    // Check project requirement
    if (required.includes('project_id') && !selectedProjectId && !workflowContext.project_id) {
      errors.push('Please select a project first');
    }
    
    return { valid: errors.length === 0, errors };
  };

  // Check if workflow can be executed
  const canExecuteWorkflow = () => {
    const { valid } = validateWorkflowContext();
    return valid && !workflowExecuting && !loadingSelectors;
  };

  // Execute a workflow
  const executeWorkflow = async () => {
    if (!selectedWorkflow) return;
    
    // Validate before execution
    const validation = validateWorkflowContext();
    if (!validation.valid) {
      validation.errors.forEach(err => toast.error(err));
      return;
    }
    
    setWorkflowExecuting(true);
    setWorkflowResult(null);
    
    try {
      // Build context from form and selected values
      const context = {
        ...workflowContext,
        project_id: selectedProjectId,
        client_id: selectedClient,
        unit_id: selectedUnit
      };
      
      const res = await fetch(`${API}/workflows/execute`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
        body: JSON.stringify({
          template_id: selectedWorkflow.template_id,
          context,
          mode: 'automatic'
        })
      });
      
      if (res.ok) {
        const result = await res.json();
        setWorkflowResult(result.execution);
        
        if (result.success) {
          const hasWarnings = result.execution?.progress?.warnings > 0;
          if (hasWarnings) {
            toast.warning(`Workflow completed with warnings. Check details for more info.`);
          } else {
            toast.success(`Workflow "${selectedWorkflow.name}" completed successfully!`);
          }
          // Refresh data - projects from context, recent work separately
          refreshProjects();
          fetchRecentWork();
        } else {
          toast.error(`Workflow failed: ${result.execution?.error || 'Unknown error'}`);
        }
      } else {
        const error = await res.json();
        toast.error(error.detail || 'Failed to execute workflow');
      }
    } catch (error) {
      console.error('Workflow execution failed:', error);
      toast.error('Failed to execute workflow');
    } finally {
      setWorkflowExecuting(false);
    }
  };

  // Retry a failed or warning workflow step
  const retryWorkflowStep = async (executionId, stepIndex) => {
    if (!executionId || stepIndex === undefined) return;
    
    setWorkflowExecuting(true);
    
    try {
      const res = await fetch(`${API}/workflows/executions/${executionId}/steps/${stepIndex}/retry`, {
        method: 'POST',
        credentials: 'include'
      });
      
      if (res.ok) {
        const result = await res.json();
        setWorkflowResult(result.execution);
        
        if (result.success) {
          toast.success('Step retried successfully');
        } else {
          toast.error(`Retry failed: ${result.error || 'Unknown error'}`);
        }
      } else {
        const error = await res.json();
        toast.error(error.detail || 'Failed to retry step');
      }
    } catch (error) {
      console.error('Retry workflow step failed:', error);
      toast.error('Failed to retry step');
    } finally {
      setWorkflowExecuting(false);
    }
  };

  // Open workflow dialog
  const openWorkflowDialog = async (template) => {
    setSelectedWorkflow(template);
    setWorkflowContext({});
    setWorkflowResult(null);
    setShowConfirmation(false);
    setWorkflowDialogOpen(true);
    
    // Fetch selectors if needed
    if (template.ui_selectors && template.ui_selectors.length > 0) {
      setLoadingSelectors(true);
      try {
        const selectorData = { documents: [], timelineSteps: [] };
        
        if (template.ui_selectors.includes('document')) {
          const res = await fetch(`${API}/workflows/selectors?selector_type=document${selectedProjectId ? `&project_id=${selectedProjectId}` : ''}`, { credentials: 'include' });
          if (res.ok) {
            const data = await res.json();
            selectorData.documents = data.items || [];
          }
        }
        
        if (template.ui_selectors.includes('timeline_step')) {
          const res = await fetch(`${API}/workflows/selectors?selector_type=timeline_step${selectedProjectId ? `&project_id=${selectedProjectId}` : ''}`, { credentials: 'include' });
          if (res.ok) {
            const data = await res.json();
            selectorData.timelineSteps = data.items || [];
          }
        }
        
        setWorkflowSelectors(selectorData);
      } catch (error) {
        console.error('Failed to fetch workflow selectors:', error);
      } finally {
        setLoadingSelectors(false);
      }
    }
  };

  const toggleVoiceInput = () => {
    if (!voiceSupported || !recognitionRef.current) {
      toast.error('Voice input not supported in this browser. Please use Chrome or Edge, or type your command instead.');
      return;
    }

    if (isListening) {
      recognitionRef.current.stop();
      setIsListening(false);
    } else {
      try {
        recognitionRef.current.start();
        setIsListening(true);
        toast.info('Listening... Speak your command');
      } catch (err) {
        console.error('Failed to start voice input:', err);
        toast.error('Could not start voice input. Please check microphone permissions.');
        setIsListening(false);
      }
    }
  };

  const handleFileSelect = (e) => {
    const files = Array.from(e.target.files);
    if (files.length > 0) {
      // Store the first file in the ref for persistence during re-extraction
      uploadedFileRef.current = files[0];
      console.log('[File Select] Stored file in ref:', files[0].name);
    }
    setAttachments(prev => [...prev, ...files]);
  };

  const handleFileDrop = useCallback((e) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragActive(false);
    
    const files = Array.from(e.dataTransfer.files);
    // Filter to supported file types for document extraction (PDF and images)
    const supportedExtensions = ['.pdf', '.jpg', '.jpeg', '.png', '.webp'];
    const supportedTypes = ['application/pdf', 'image/jpeg', 'image/png', 'image/webp'];
    
    const supportedFiles = files.filter(f => 
      supportedTypes.includes(f.type) || 
      supportedExtensions.some(ext => f.name.toLowerCase().endsWith(ext))
    );
    
    if (supportedFiles.length === 0 && files.length > 0) {
      toast.error('Supported formats: PDF, JPG, PNG, WEBP');
      return;
    }
    
    if (supportedFiles.length > 0) {
      // Store the first file in the ref for persistence during re-extraction
      uploadedFileRef.current = supportedFiles[0];
      console.log('[File Drop] Stored file in ref:', supportedFiles[0].name);
      setAttachments(prev => [...prev, ...supportedFiles]);
      toast.success(`${supportedFiles.length} file${supportedFiles.length > 1 ? 's' : ''} added`);
    }
  }, []);

  const handleDragOver = useCallback((e) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragActive(true);
  }, []);

  const handleDragLeave = useCallback((e) => {
    e.preventDefault();
    e.stopPropagation();
    // Only set inactive if leaving the drop zone entirely
    if (e.currentTarget.contains(e.relatedTarget)) return;
    setIsDragActive(false);
  }, []);

  const removeAttachment = (index) => {
    setAttachments(prev => prev.filter((_, i) => i !== index));
  };

  // Direct file upload trigger - used by the upload button
  const triggerFileUpload = useCallback(() => {
    console.log('[Upload Button] Triggering file input click');
    if (fileInputRef.current) {
      fileInputRef.current.value = ''; // Reset to allow same file selection
      fileInputRef.current.click();
    }
  }, []);

  const handleCommandSubmit = async () => {
    // CRITICAL: Capture current values immediately to avoid stale closure issues
    const currentAttachments = [...attachments];
    const currentText = commandText.trim();
    
    // Validate: need at least text OR a file
    if (!currentText && currentAttachments.length === 0) {
      toast.error('Please enter a command or attach a file');
      return;
    }

    setIsProcessing(true);

    try {
      // PRIORITY: File upload ALWAYS takes precedence over text commands
      // When a file is present, route to document processing flow
      // Text input (if any) is treated as optional context, not as primary command
      if (currentAttachments.length > 0) {
        const file = currentAttachments[0];
        if (file) {
          // Pass optional text as context hint
          await handleDocumentUpload(file, currentText || null);
          return;
        }
      }

      // TEXT-ONLY FLOW: No file attached, process as text command
      const formData = new FormData();
      formData.append('command', currentText);
      formData.append('context', JSON.stringify({
        project_id: selectedProjectId,
        client_id: selectedClient,
        unit_id: selectedUnit
      }));

      const res = await fetch(`${API}/command/interpret`, {
        method: 'POST',
        credentials: 'include',
        body: formData
      });

      if (res.ok) {
        const plan = await res.json();
        setPreviewData(plan);
        setPreviewOpen(true);
        
        // Show a warning if command cannot be executed
        if (!plan.can_execute && plan.missing_fields?.some(f => f.required)) {
          const missingRequired = plan.missing_fields.filter(f => f.required).map(f => f.name.replace('_', ' '));
          toast.warning(`Missing required fields: ${missingRequired.join(', ')}. Select from the context dropdowns above.`);
        }
      } else {
        // Fallback: show simple interpretation
        const mockPlan = interpretCommandLocally(currentText, currentAttachments);
        setPreviewData(mockPlan);
        setPreviewOpen(true);
      }
    } catch (error) {
      console.error('Command interpretation failed:', error);
      // Fallback to local interpretation
      const mockPlan = interpretCommandLocally(currentText, currentAttachments);
      setPreviewData(mockPlan);
      setPreviewOpen(true);
    } finally {
      setIsProcessing(false);
    }
  };

  // Handle document upload through the command system (Phase 3)
  // textContext is optional - user-provided text that can serve as a hint
  const handleDocumentUpload = async (file, textContext = null) => {
    // Declare classification at the outer scope so it's available in catch
    let classification = null;
    
    try {
      // Validate file type - PDFs and images are supported for document extraction
      const allowedTypes = ['application/pdf', 'image/jpeg', 'image/png', 'image/webp'];
      const allowedExtensions = ['.pdf', '.jpg', '.jpeg', '.png', '.webp'];
      const fileExtension = file.name.toLowerCase().slice(file.name.lastIndexOf('.'));
      
      if (!allowedTypes.includes(file.type) && !allowedExtensions.includes(fileExtension)) {
        toast.error('Supported formats: PDF, JPG, PNG, WEBP. Please upload a supported file.');
        setIsProcessing(false);
        return;
      }
      
      // Step 1: Classify the document
      toast.info('Analyzing document...');
      if (textContext) {
        console.log('[Document Upload] Text context provided:', textContext);
      }
      
      const classifyFormData = new FormData();
      classifyFormData.append('file', file);
      // Pass text as optional context hint for classification
      if (textContext) {
        classifyFormData.append('text_hint', textContext);
      }
      
      const classifyRes = await fetch(`${API}/command/classify-document`, {
        method: 'POST',
        credentials: 'include',
        body: classifyFormData
      });
      
      if (!classifyRes.ok) {
        throw new Error('Document classification failed');
      }
      
      classification = await classifyRes.json();
      
      // If classification is unknown, show preview with manual selection required
      if (classification.document_type === 'unknown') {
        toast.warning('Could not automatically classify document. Please select the document type.');
        setPreviewData({
          intent: 'unknown',
          document_type: 'unknown',
          can_execute: false,
          requires_manual_classification: true,
          classification: classification,
          attachments: [{ name: file.name, size: file.size }],
          fields: [],
          missing_fields: [{
            name: 'document_type',
            description: 'Select document type to continue',
            required: true
          }],
          source_file: classification.file_path,
          original_file: file,  // Keep reference to original file for re-upload if needed
          interpretation_log: [
            `Classification confidence too low (${Math.round(classification.confidence * 100)}%)`,
            'Please select document type manually'
          ]
        });
        setPreviewOpen(true);
        return;
      }
      
      // Show classification result
      toast.success(`Detected: ${classification.document_type} (${Math.round(classification.confidence * 100)}% confidence)`);
      
      // Step 2: Extract data from the document
      const extractFormData = new FormData();
      extractFormData.append('file_path', classification.file_path);
      extractFormData.append('document_type', classification.document_type);
      extractFormData.append('context', JSON.stringify({
        project_id: selectedProjectId,
        client_id: selectedClient,
        unit_id: selectedUnit,
        text_hint: textContext  // Pass user text as additional context
      }));
      
      const extractRes = await fetch(`${API}/command/extract-document`, {
        method: 'POST',
        credentials: 'include',
        body: extractFormData
      });
      
      if (!extractRes.ok) {
        throw new Error('Document extraction failed');
      }
      
      const extractedPlan = await extractRes.json();
      
      // Add classification info and file references to the plan
      extractedPlan.classification = classification;
      extractedPlan.attachments = [{ name: file.name, size: file.size }];
      extractedPlan.source_file = classification.file_path;  // Ensure file path is preserved
      extractedPlan.original_file = file;  // Keep original file reference for re-extraction
      
      // Show the preview
      setPreviewData(extractedPlan);
      setPreviewOpen(true);
      
      if (!extractedPlan.can_execute && extractedPlan.missing_fields?.some(f => f.required)) {
        const missingRequired = extractedPlan.missing_fields.filter(f => f.required).map(f => f.name.replace('_', ' '));
        toast.warning(`Missing required fields: ${missingRequired.join(', ')}`);
      }
      
    } catch (error) {
      console.error('Document processing failed:', error);
      
      // Try to get file_path from response if available
      let filePath = null;
      let classificationData = null;
      if (error.response) {
        try {
          const errData = await error.response.json();
          filePath = errData.file_path;
        } catch (e) {
          // Ignore JSON parse errors
        }
      }
      
      // Check if we have a successful classification from a previous step
      // This happens when classify succeeds but extract fails
      if (classification && classification.document_type && classification.document_type !== 'unknown') {
        classificationData = classification;
        filePath = classification.file_path || filePath;
      }
      
      toast.error('Failed to process document. Please try again.');
      
      // Fallback: show manual classification option
      // Preserve classification if it succeeded
      const fallbackDocType = classificationData?.document_type || 'unknown';
      const intentFromType = {
        'invoice': 'extract_invoice',
        'quote': 'extract_quote',
        'timeline': 'extract_timeline',
        'contacts': 'extract_contacts'
      };
      
      setPreviewData({
        intent: intentFromType[fallbackDocType] || 'unknown',
        document_type: fallbackDocType,
        can_execute: false,
        requires_manual_classification: fallbackDocType === 'unknown',
        classification: classificationData || {
          filename: file.name,
          document_type: fallbackDocType,
          confidence: 0.5
        },
        attachments: [{ name: file.name, size: file.size }],
        fields: [],
        // Store a reference to the original file for re-upload if needed
        original_file: file,
        source_file: filePath,
        missing_fields: fallbackDocType === 'unknown' ? [{
          name: 'document_type',
          description: 'Select document type manually',
          required: true
        }] : [{
          name: 'extraction_failed',
          description: 'Document extraction failed. Click Re-run Extraction to try again.',
          required: false
        }],
        interpretation_log: fallbackDocType === 'unknown' 
          ? ['Automatic classification failed', 'Please select document type manually']
          : [`Document classified as ${fallbackDocType}`, 'Extraction failed - click Re-run Extraction to try again']
      });
      setPreviewOpen(true);
    } finally {
      setIsProcessing(false);
    }
  };

  // Local fallback interpretation (until AI service is ready)
  const interpretCommandLocally = (text, files) => {
    const lowerText = text.toLowerCase();
    
    let intent = 'unknown';
    let fields = {};
    
    if (lowerText.includes('invoice') || lowerText.includes('bill')) {
      intent = 'create_invoice';
    } else if (lowerText.includes('quote') || lowerText.includes('estimate') || lowerText.includes('offerte')) {
      intent = 'create_quote';
    } else if (lowerText.includes('message') || lowerText.includes('send') || lowerText.includes('email')) {
      intent = 'send_message';
    } else if (lowerText.includes('post') || lowerText.includes('update') || lowerText.includes('announce')) {
      intent = 'create_feed_post';
    } else if (lowerText.includes('timeline') || lowerText.includes('schedule') || lowerText.includes('planning')) {
      intent = 'upload_timeline';
    } else if (files.length > 0) {
      // Determine from file type
      const fileName = files[0].name.toLowerCase();
      if (fileName.includes('invoice') || fileName.includes('facture')) {
        intent = 'extract_invoice';
      } else if (fileName.includes('quote') || fileName.includes('offerte') || fileName.includes('devis')) {
        intent = 'extract_quote';
      } else if (fileName.includes('timeline') || fileName.includes('planning') || fileName.includes('schedule')) {
        intent = 'extract_timeline';
      } else {
        intent = 'upload_document';
      }
    }

    // Extract amounts if present - handles both comma-as-thousands (10,000) and comma-as-decimal (10,50)
    const parseAmount = (str) => {
      // Check if comma is thousands separator (e.g., 10,000 or 1,000,000)
      if (/^\d{1,3}(?:[,']\d{3})+(?:\.\d{1,2})?$/.test(str)) {
        // Thousands separator format: remove commas and apostrophes
        return parseFloat(str.replace(/[,']/g, ''));
      }
      // European decimal format (10,50)
      if (/^\d+,\d{1,2}$/.test(str)) {
        return parseFloat(str.replace(',', '.'));
      }
      // Standard number or US format
      return parseFloat(str.replace(',', ''));
    };

    // Match amounts with optional currency
    const amountMatch = text.match(/(\d{1,3}(?:[,']\d{3})*(?:\.\d{1,2})?|\d+(?:[.,]\d{1,2})?)\s*(?:chf|eur|usd|\$|€)?/i);
    if (amountMatch) {
      fields.amount = parseAmount(amountMatch[1]);
    }

    // Find project/client references in context
    const selectedClientObj = clients.find(c => c.client_id === selectedClient);

    return {
      intent,
      confidence: 0.75,
      entities: {
        project_id: selectedProjectId,
        project_name: selectedProject?.name,
        client_id: selectedClient,
        client_name: selectedClientObj?.name,
        unit_id: selectedUnit
      },
      fields,
      attachments: files.map(f => ({ name: f.name, size: f.size, type: f.type })),
      raw_command: text,
      requires_confirmation: true,
      suggested_action: getSuggestedAction(intent)
    };
  };

  const getSuggestedAction = (intent) => {
    switch (intent) {
      case 'create_invoice':
        return { label: 'Create Invoice', path: '/agent/invoices/new' };
      case 'create_quote':
        return { label: 'Create Quote', path: '/agent/quotes/new' };
      case 'send_message':
        return { label: 'Send Message', path: '/agent/feed' };
      case 'create_feed_post':
        return { label: 'Post Update', path: '/agent/feed' };
      case 'upload_timeline':
      case 'extract_timeline':
        return { label: 'Go to Timeline', path: '/agent/timeline' };
      case 'extract_invoice':
        return { label: 'Upload Invoice', path: '/agent/invoices/new' };
      case 'extract_quote':
        return { label: 'Upload Quote', path: '/agent/quotes/new' };
      case 'upload_document':
        return { label: 'Go to Vault', path: '/agent/vault' };
      default:
        return { label: 'View Dashboard', path: '/agent/dashboard-legacy' };
    }
  };

  // Re-run extraction with same or different document type
  const handleReExtract = async (newDocType = null) => {
    const filePath = previewData?.source_file || previewData?.classification?.file_path;
    const originalFile = previewData?.original_file;
    
    // CRITICAL: Use the ref as the most reliable fallback
    // The ref persists across state changes, unlike the attachments array
    const refFile = uploadedFileRef.current;
    const attachmentFile = attachments.length > 0 ? attachments[0] : null;
    
    // Debug logging
    console.log('[Re-extract] File sources:', {
      filePath,
      hasOriginalFile: !!originalFile,
      hasRefFile: !!refFile,
      refFileName: refFile?.name,
      hasAttachmentFile: !!attachmentFile,
      attachmentsLength: attachments.length,
      previewDataKeys: previewData ? Object.keys(previewData) : []
    });
    
    // Priority: filePath > originalFile > refFile > attachmentFile
    const availableFile = originalFile || refFile || attachmentFile;
    
    // If no file path AND no file available, we can't proceed
    if (!filePath && !availableFile) {
      toast.error('No source file available for re-extraction. Please re-upload the document.');
      return;
    }

    setReExtracting(true);
    const docType = newDocType || overrideDocType || previewData?.document_type || previewData?.classification?.document_type || 'unknown';

    try {
      toast.info(`Re-extracting as ${docType}...`);
      
      let actualFilePath = filePath;
      
      // If we don't have a file path, re-upload from available file sources
      if (!actualFilePath && availableFile) {
        toast.info('Re-uploading document...');
        
        const classifyFormData = new FormData();
        classifyFormData.append('file', availableFile);
        
        const classifyRes = await fetch(`${API}/command/classify-document`, {
          method: 'POST',
          credentials: 'include',
          body: classifyFormData
        });
        
        if (!classifyRes.ok) {
          const errData = await classifyRes.json().catch(() => ({}));
          throw new Error(errData.detail || 'Failed to re-upload document');
        }
        
        const classification = await classifyRes.json();
        actualFilePath = classification.file_path;
        
        // Update previewData with the new file path and preserve file reference
        setPreviewData(prev => ({
          ...prev,
          source_file: actualFilePath,
          classification: classification,
          original_file: availableFile
        }));
      }
      
      const extractFormData = new FormData();
      extractFormData.append('file_path', actualFilePath);
      extractFormData.append('document_type', docType);
      extractFormData.append('context', JSON.stringify({
        project_id: selectedProjectId,
        client_id: selectedClient,
        unit_id: selectedUnit
      }));
      
      const extractRes = await fetch(`${API}/command/extract-document`, {
        method: 'POST',
        credentials: 'include',
        body: extractFormData
      });
      
      if (!extractRes.ok) {
        throw new Error('Re-extraction failed');
      }
      
      const extractedPlan = await extractRes.json();
      
      // Preserve classification info but update document type
      // CRITICAL: Also preserve the original_file reference
      extractedPlan.classification = {
        ...previewData.classification,
        document_type: docType,
        was_overridden: newDocType !== null
      };
      extractedPlan.attachments = previewData.attachments;
      extractedPlan.original_file = availableFile; // Preserve file reference
      extractedPlan.source_file = actualFilePath; // Preserve file path
      
      setPreviewData(extractedPlan);
      setOverrideDocType(null);
      toast.success('Extraction complete');
      
    } catch (error) {
      console.error('Re-extraction failed:', error);
      toast.error('Re-extraction failed. Please try again.');
    } finally {
      setReExtracting(false);
    }
  };

  // Get confidence level label and color
  const getConfidenceDisplay = (confidence) => {
    if (confidence >= 0.8) return { label: 'High', color: 'text-emerald-600 bg-emerald-500/10' };
    if (confidence >= 0.5) return { label: 'Medium', color: 'text-amber-600 bg-amber-500/10' };
    return { label: 'Low', color: 'text-red-600 bg-red-500/10' };
  };

  const handleExecuteAction = async () => {
    if (!previewData) return;

    setExecuting(true);
    
    try {
      // Step 1: Create draft from plan
      const draftRes = await fetch(`${API}/command/draft`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
        body: JSON.stringify(previewData)
      });

      if (!draftRes.ok) {
        const error = await draftRes.json();
        throw new Error(error.detail || 'Failed to create draft');
      }

      const draft = await draftRes.json();
      
      // Step 2: Execute the draft
      const execRes = await fetch(`${API}/command/execute`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
        body: JSON.stringify({
          draft_id: draft.draft_id,
          confirmed: true
        })
      });

      if (execRes.ok) {
        const result = await execRes.json();
        const docType = result.result?.type || previewData.intent.replace('create_', '');
        const docNumber = result.result?.number || '';
        
        toast.success(`${docType.charAt(0).toUpperCase() + docType.slice(1)} ${docNumber} created successfully!`, {
          description: `Redirecting to ${docType} detail page...`,
          duration: 3000
        });
        
        // Short delay then redirect
        setTimeout(() => {
          if (result.result?.redirect) {
            navigate(result.result.redirect);
          } else {
            // Fallback: navigate to the list
            const listPath = docType === 'invoice' ? '/agent/invoices' 
              : docType === 'quote' ? '/agent/quotes' 
              : '/agent/feed';
            navigate(listPath);
          }
        }, 500);
      } else {
        const error = await execRes.json();
        throw new Error(error.detail || 'Execution failed');
      }
    } catch (error) {
      console.error('Command execution failed:', error);
      // Fallback navigation for suggested action
      if (previewData.suggested_action?.path) {
        navigate(previewData.suggested_action.path);
        toast.info(`Navigating to ${previewData.suggested_action.label}`);
      } else {
        toast.error(error.message || 'Failed to execute command');
      }
    } finally {
      setExecuting(false);
      setPreviewOpen(false);
      setCommandText('');
      setAttachments([]);
      setPreviewData(null);
      // Clear the file ref only after successful execution
      uploadedFileRef.current = null;
    }
  };

  const formatCurrency = (amount) => {
    return new Intl.NumberFormat('de-CH', { style: 'currency', currency: 'CHF' }).format(amount || 0);
  };

  const getIntentLabel = (intent) => {
    const labels = {
      'create_invoice': 'Create Invoice',
      'create_quote': 'Create Quote',
      'create_message': 'Send Message',
      'send_message': 'Send Message',
      'create_feed_post': 'Post Update',
      'upload_timeline': 'Upload Timeline',
      // Phase 3: Extraction intents
      'extract_invoice': 'Extract Invoice',
      'extract_quote': 'Extract Quote',
      'extract_timeline': 'Extract Timeline',
      'extract_contacts': 'Extract Contacts',
      'extract_invoice_document': 'Extract Invoice',
      'extract_quote_document': 'Extract Quote',
      'extract_timeline_document': 'Extract Timeline',
      'extract_contacts_document': 'Extract Contacts',
      'upload_document': 'Upload Document',
      'unknown': 'General Action'
    };
    return labels[intent] || intent;
  };

  return (
    <AgentLayout>
      <div className="space-y-6" data-testid="agent-home-page">
        {/* Simplified Header */}
        <div>
          <h1 className="text-2xl font-outfit font-semibold text-foreground tracking-tight flex items-center gap-2">
            <Sparkles className="w-6 h-6 text-primary" />
            Command Center
          </h1>
          <p className="text-sm text-muted-foreground mt-1">
            Type, speak, or upload to get things done.
          </p>
        </div>

        {/* Context Selector */}
        <Card className="border-border">
          <CardContent className="py-4">
            <div className="flex flex-wrap items-center gap-4">
              <div className="flex items-center gap-2 text-sm text-muted-foreground">
                <Home className="w-4 h-4" />
                <span>Working Context:</span>
              </div>
              
              <Select value={selectedProjectId} onValueChange={setSelectedProjectId}>
                <SelectTrigger className="w-[200px]" data-testid="context-project-select">
                  <SelectValue placeholder="Select Project" />
                </SelectTrigger>
                <SelectContent>
                  {projects.map(p => (
                    <SelectItem key={p.project_id} value={p.project_id}>
                      <span className="flex items-center gap-2">
                        <Building2 className="w-4 h-4" />
                        {p.name}
                      </span>
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>

              <Select value={selectedClient || "all"} onValueChange={(val) => setSelectedClient(val === "all" ? "" : val)}>
                <SelectTrigger className="w-[200px]" data-testid="context-client-select">
                  <SelectValue placeholder="Select Client" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">All Clients</SelectItem>
                  {clients.map(c => (
                    <SelectItem key={c.client_id} value={c.client_id}>
                      <span className="flex items-center gap-2">
                        <User className="w-4 h-4" />
                        {c.name}
                      </span>
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>

              {units.length > 0 && (
                <Select value={selectedUnit || "all"} onValueChange={(val) => setSelectedUnit(val === "all" ? "" : val)}>
                  <SelectTrigger className="w-[150px]" data-testid="context-unit-select">
                    <SelectValue placeholder="Select Unit" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="all">All Units</SelectItem>
                    {units.map(u => (
                      <SelectItem key={u.unit_id} value={u.unit_id}>
                        {u.unit_reference || u.name}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              )}
            </div>
          </CardContent>
        </Card>

        {/* Command Workspace - THE DOMINANT BLOCK */}
        <Card className="border-primary/30 bg-gradient-to-br from-primary/5 to-transparent shadow-sm">
          <CardContent className="pt-6 space-y-4">
            {/* Hidden file input - OUTSIDE drop zone to prevent event interference */}
            <input
              ref={fileInputRef}
              type="file"
              id="command-file-input"
              className="hidden"
              onChange={handleFileSelect}
              accept=".pdf,application/pdf,.jpg,.jpeg,.png,.webp,image/jpeg,image/png,image/webp"
              title="Supports PDF, JPG, PNG, WEBP files"
            />
            
            {/* Command Input - Full drag-and-drop zone */}
            <div 
              className={cn(
                "relative rounded-xl border-2 transition-all duration-200 p-4",
                isDragActive 
                  ? "border-primary bg-primary/10 border-solid scale-[1.02] shadow-lg" 
                  : attachments.length > 0 
                    ? "border-primary/50 bg-primary/5 border-dashed" 
                    : "border-border bg-background border-dashed hover:border-primary/30"
              )}
              onDragOver={handleDragOver}
              onDragLeave={handleDragLeave}
              onDrop={handleFileDrop}
              data-testid="command-drop-zone"
            >
              {/* Drag overlay indicator */}
              {isDragActive && (
                <div className="absolute inset-0 flex items-center justify-center bg-primary/5 rounded-xl z-10 pointer-events-none">
                  <div className="flex flex-col items-center gap-2 text-primary">
                    <Upload className="w-10 h-10 animate-bounce" />
                    <span className="font-medium text-lg">Drop file here</span>
                    <span className="text-sm text-muted-foreground">Supports PDF, JPG, PNG, WEBP</span>
                  </div>
                </div>
              )}
              
              <div className="flex items-center gap-3">
                {voiceSupported ? (
                  <Button
                    variant={isListening ? "default" : "outline"}
                    size="icon"
                    className={cn("rounded-full flex-shrink-0", isListening && "bg-red-500 hover:bg-red-600")}
                    onClick={toggleVoiceInput}
                    data-testid="voice-input-btn"
                    title={isListening ? "Stop listening" : "Voice input (Chrome/Edge only)"}
                  >
                    {isListening ? <MicOff className="w-5 h-5" /> : <Mic className="w-5 h-5" />}
                  </Button>
                ) : (
                  <Button
                    variant="outline"
                    size="icon"
                    className="rounded-full flex-shrink-0 opacity-50 cursor-not-allowed"
                    disabled
                    title="Voice input not supported in this browser. Use Chrome or Edge."
                    data-testid="voice-input-btn-disabled"
                  >
                    <Mic className="w-5 h-5" />
                  </Button>
                )}
                
                <Input
                  ref={commandInputRef}
                  value={commandText}
                  onChange={(e) => setCommandText(e.target.value)}
                  onKeyDown={(e) => e.key === 'Enter' && !e.shiftKey && handleCommandSubmit()}
                  placeholder={isDragActive ? "Drop file to upload..." : "Type a command or drop a file... (⌘K to focus)"}
                  className="flex-1 border-0 bg-transparent text-lg focus-visible:ring-0 focus-visible:ring-offset-0"
                  disabled={isProcessing || isDragActive}
                  data-testid="command-input"
                />
                
                <Button
                  variant="outline"
                  size="icon"
                  className="rounded-full flex-shrink-0 relative z-20"
                  onClick={triggerFileUpload}
                  type="button"
                  data-testid="file-upload-btn"
                  title="Upload PDF document"
                >
                  <Upload className="w-5 h-5" />
                </Button>

                <Button
                  size="icon"
                  className="rounded-full flex-shrink-0"
                  onClick={handleCommandSubmit}
                  disabled={isProcessing || (!commandText.trim() && attachments.length === 0)}
                  data-testid="submit-command-btn"
                >
                  {isProcessing ? <Loader2 className="w-5 h-5 animate-spin" /> : <Send className="w-5 h-5" />}
                </Button>
              </div>

              {/* Attachments */}
              {attachments.length > 0 && (
                <div className="flex flex-wrap gap-2 mt-3 pt-3 border-t border-border">
                  {attachments.map((file, i) => (
                    <Badge key={i} variant="secondary" className="flex items-center gap-2 py-1.5 px-3">
                      <FileUp className="w-3 h-3" />
                      <span className="max-w-[150px] truncate">{file.name}</span>
                      <button onClick={() => removeAttachment(i)} className="hover:text-destructive">
                        <X className="w-3 h-3" />
                      </button>
                    </Badge>
                  ))}
                </div>
              )}

              {/* Alternative upload hint when no attachments */}
              {attachments.length === 0 && !isDragActive && (
                <label 
                  htmlFor="command-file-input"
                  className="flex items-center justify-center gap-2 mt-2 py-2 text-xs text-muted-foreground hover:text-primary cursor-pointer transition-colors"
                >
                  <FileUp className="w-3 h-3" />
                  <span>Click here or drag a file to upload (PDF, JPG, PNG, WEBP)</span>
                </label>
              )}

              {isListening && (
                <div className="absolute inset-0 bg-red-500/10 rounded-xl flex items-center justify-center pointer-events-none">
                  <div className="flex items-center gap-2 text-red-600">
                    <span className="w-3 h-3 bg-red-500 rounded-full animate-pulse" />
                    <span className="font-medium">Listening...</span>
                  </div>
                </div>
              )}
            </div>
          </CardContent>
        </Card>

        {/* Supporting Block - Deterministic: Has activity → Recent Activity | No activity → CTA */}
        {recentWork.length > 0 ? (
          <Card>
            <CardHeader className="pb-3">
              <CardTitle className="text-base font-outfit flex items-center gap-2">
                <Clock className="w-4 h-4 text-muted-foreground" />
                Recent Activity
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-2">
                {recentWork.slice(0, 6).map(item => (
                  <div
                    key={item.id}
                    className="flex items-center gap-3 p-3 rounded-lg border border-border hover:bg-muted/50 cursor-pointer transition-colors"
                    onClick={() => navigate(item.path)}
                    data-testid={`recent-item-${item.id}`}
                  >
                    <div className="w-8 h-8 rounded-lg bg-muted flex items-center justify-center flex-shrink-0">
                      {item.type === 'client' ? <User className="w-4 h-4" /> : 
                       item.type === 'project' ? <Building2 className="w-4 h-4" /> :
                       <FileText className="w-4 h-4" />}
                    </div>
                    <div className="flex-1 min-w-0">
                      <p className="text-sm font-medium truncate">{item.title}</p>
                      <p className="text-xs text-muted-foreground truncate">{item.subtitle}</p>
                    </div>
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>
        ) : (
          <Card className="border-dashed">
            <CardContent className="py-8">
              <div className="text-center">
                <div className="w-12 h-12 rounded-full bg-primary/10 flex items-center justify-center mx-auto mb-4">
                  <Sparkles className="w-6 h-6 text-primary" />
                </div>
                <h3 className="font-medium mb-1">Get Started</h3>
                <p className="text-sm text-muted-foreground mb-4 max-w-sm mx-auto">
                  Upload a document or type a command above to start managing your projects.
                </p>
                <Button 
                  variant="outline" 
                  onClick={() => commandInputRef.current?.focus()}
                  data-testid="cta-focus-command"
                >
                  <Send className="w-4 h-4 mr-2" />
                  Start with a Command
                </Button>
              </div>
            </CardContent>
          </Card>
        )}
      </div>

      {/* Action Preview Drawer */}
      <Sheet open={previewOpen} onOpenChange={setPreviewOpen}>
        <SheetContent className="sm:max-w-lg overflow-y-auto">
          <SheetHeader>
            <SheetTitle className="flex items-center gap-2">
              <Sparkles className="w-5 h-5 text-primary" />
              Action Preview
            </SheetTitle>
          </SheetHeader>

          {previewData && (
            <div className="mt-6 space-y-5">
              {/* Intent & Confidence - Primary Debug Info */}
              <div className="p-4 rounded-lg bg-muted/50 border border-border">
                <div className="flex items-center justify-between mb-3">
                  <p className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">Detected Intent</p>
                  {(previewData.intent_confidence || previewData.confidence) && (
                    <Badge 
                      variant={
                        (previewData.intent_confidence || previewData.confidence) >= 0.8 
                          ? "default" 
                          : (previewData.intent_confidence || previewData.confidence) >= 0.5 
                            ? "secondary" 
                            : "outline"
                      }
                      className="text-xs"
                    >
                      {Math.round((previewData.intent_confidence || previewData.confidence) * 100)}% confidence
                    </Badge>
                  )}
                </div>
                <div className="flex items-center gap-2">
                  <Badge 
                    variant={previewData.can_execute ? "default" : "secondary"} 
                    className="text-sm py-1.5 px-3"
                  >
                    {getIntentLabel(previewData.intent)}
                  </Badge>
                  {previewData.is_valid && (
                    <CheckCircle className="w-4 h-4 text-emerald-500" />
                  )}
                  {!previewData.is_valid && previewData.intent !== 'unknown' && (
                    <AlertCircle className="w-4 h-4 text-amber-500" />
                  )}
                </div>
              </div>

              {/* Document Classification (Phase 3) - With Override and Re-extract */}
              {(previewData.classification || previewData.document_type) && (
                <div className="p-4 rounded-lg bg-blue-500/10 border border-blue-500/30">
                  <div className="flex items-center justify-between mb-3">
                    <p className="text-xs font-semibold uppercase tracking-wider text-blue-600 dark:text-blue-400">Document Classification</p>
                    {previewData.classification?.was_overridden && (
                      <Badge variant="outline" className="text-xs border-amber-500/50 text-amber-600">
                        Overridden
                      </Badge>
                    )}
                  </div>
                  
                  {/* File info */}
                  {previewData.classification?.filename && (
                    <div className="flex items-center gap-2 text-sm mb-3">
                      <FileUp className="w-4 h-4 text-blue-500" />
                      <span className="text-muted-foreground truncate">{previewData.classification.filename}</span>
                    </div>
                  )}
                  
                  {/* Document Type Override Dropdown */}
                  <div className="flex items-center gap-2 mb-3">
                    <span className="text-sm text-muted-foreground">Type:</span>
                    <Select 
                      value={overrideDocType || previewData.document_type || previewData.classification?.document_type} 
                      onValueChange={(val) => setOverrideDocType(val)}
                    >
                      <SelectTrigger className="w-40 h-8 text-sm">
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="invoice">Invoice</SelectItem>
                        <SelectItem value="quote">Quote</SelectItem>
                        <SelectItem value="timeline">Timeline</SelectItem>
                        <SelectItem value="contacts">Contacts</SelectItem>
                      </SelectContent>
                    </Select>
                    <span className={cn(
                      "text-xs px-2 py-0.5 rounded",
                      getConfidenceDisplay(previewData.classification?.confidence || previewData.intent_confidence || 0.5).color
                    )}>
                      {getConfidenceDisplay(previewData.classification?.confidence || previewData.intent_confidence || 0.5).label}
                    </span>
                  </div>
                  
                  {/* Re-extract Button */}
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => handleReExtract(overrideDocType)}
                    disabled={reExtracting}
                    className="w-full border-blue-500/30 text-blue-600 hover:bg-blue-500/10"
                  >
                    {reExtracting ? (
                      <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                    ) : (
                      <RefreshCw className="w-4 h-4 mr-2" />
                    )}
                    {overrideDocType && overrideDocType !== (previewData.document_type || previewData.classification?.document_type)
                      ? `Re-extract as ${overrideDocType}`
                      : 'Re-run Extraction'
                    }
                  </Button>
                </div>
              )}

              {/* Validation Status */}
              {previewData.validation_errors && previewData.validation_errors.length > 0 && (
                <div className="p-3 rounded-lg bg-destructive/10 border border-destructive/20">
                  <p className="text-xs font-semibold uppercase tracking-wider text-destructive mb-2">Validation Issues</p>
                  <ul className="text-sm space-y-1">
                    {previewData.validation_errors.map((err, i) => (
                      <li key={i} className="text-destructive flex items-center gap-2">
                        <X className="w-3 h-3" />
                        {err}
                      </li>
                    ))}
                  </ul>
                </div>
              )}

              {/* Existing Timeline Warning */}
              {previewData.timeline_exists && previewData.existing_timeline && (
                <div className="p-4 rounded-lg bg-amber-500/10 border border-amber-500/30">
                  <div className="flex items-start gap-3">
                    <AlertCircle className="w-5 h-5 text-amber-600 flex-shrink-0 mt-0.5" />
                    <div className="flex-1">
                      <p className="font-medium text-amber-800 dark:text-amber-200">Timeline Already Exists</p>
                      <p className="text-sm text-amber-700 dark:text-amber-300 mt-1">
                        This project already has a timeline: <strong>"{previewData.existing_timeline.name}"</strong>
                      </p>
                      <p className="text-xs text-amber-600 dark:text-amber-400 mt-2">
                        {previewData.message}
                      </p>
                      <div className="flex gap-2 mt-3">
                        {previewData.available_actions?.map((action, i) => (
                          <Button
                            key={i}
                            variant={action.action === 'view' ? 'default' : 'outline'}
                            size="sm"
                            onClick={() => {
                              if (action.action === 'view') {
                                navigate(action.path);
                                setPreviewOpen(false);
                              } else if (action.action === 'replace') {
                                if (window.confirm('Are you sure you want to replace the existing timeline? This action cannot be undone.')) {
                                  // TODO: Implement replace timeline
                                  toast.info('Replace timeline feature coming soon');
                                }
                              }
                            }}
                            className={action.action === 'view' ? '' : 'border-amber-500/50 text-amber-700 hover:bg-amber-500/10'}
                          >
                            {action.action === 'view' && <Eye className="w-4 h-4 mr-2" />}
                            {action.label}
                          </Button>
                        ))}
                      </div>
                    </div>
                  </div>
                </div>
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

              {/* Extracted Fields - With Field-Level Confidence */}
              {previewData.fields && previewData.fields.length > 0 && (
                <div>
                  <div className="flex items-center justify-between mb-2">
                    <p className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                      Extracted Fields
                    </p>
                    <div className="flex items-center gap-1 text-xs text-muted-foreground">
                      <Info className="w-3 h-3" />
                      <span>Confidence shown per field</span>
                    </div>
                  </div>
                  <div className="space-y-2">
                    {previewData.fields.map((field, i) => {
                      const conf = getConfidenceDisplay(field.confidence || 0.5);
                      return (
                        <div 
                          key={i} 
                          className="flex items-center justify-between p-3 rounded-lg border border-border bg-card hover:bg-muted/20 transition-colors"
                        >
                          <div className="flex-1 min-w-0">
                            <div className="flex items-center gap-2 mb-1">
                              <span className="text-xs font-medium uppercase text-muted-foreground">
                                {field.name.replace(/_/g, ' ')}
                              </span>
                              <span className={cn("text-[10px] px-1.5 py-0.5 rounded font-medium", conf.color)}>
                                {conf.label}
                              </span>
                              {field.source === 'ai_extraction' && (
                                <span className="text-[10px] px-1.5 py-0.5 rounded bg-purple-500/10 text-purple-600">
                                  AI
                                </span>
                              )}
                              {field.source === 'context' && (
                                <span className="text-[10px] px-1.5 py-0.5 rounded bg-blue-500/10 text-blue-600">
                                  Context
                                </span>
                              )}
                            </div>
                            <p className="text-sm font-medium truncate">
                              {field.name === 'amount' || field.name === 'total_amount'
                                ? formatCurrency(field.value) 
                                : field.name === 'line_items' && Array.isArray(field.value)
                                  ? `${field.value.length} items`
                                  : field.name === 'stages' && Array.isArray(field.value)
                                    ? `${field.value.length} stages: ${field.value.map(s => s.name || s.title || s.stage || 'Stage').join(', ').substring(0, 50)}${field.value.length > 3 ? '...' : ''}`
                                    : Array.isArray(field.value)
                                      ? `${field.value.length} items`
                                      : typeof field.value === 'object' && field.value !== null
                                        ? JSON.stringify(field.value).substring(0, 60) + (JSON.stringify(field.value).length > 60 ? '...' : '')
                                        : String(field.value || '—').substring(0, 60) + (String(field.value || '').length > 60 ? '...' : '')}
                            </p>
                          </div>
                          {field.confidence < 0.5 && (
                            <AlertCircle className="w-4 h-4 text-amber-500 flex-shrink-0 ml-2" />
                          )}
                        </div>
                      );
                    })}
                  </div>
                </div>
              )}

              {/* Timeline Stages - Special rendering for timeline extractions */}
              {previewData.fields?.some(f => f.name === 'stages' && Array.isArray(f.value) && f.value.length > 0) && (
                <div>
                  <p className="text-xs font-semibold uppercase tracking-wider text-muted-foreground mb-2">
                    Timeline Stages
                  </p>
                  <div className="space-y-2">
                    {previewData.fields.find(f => f.name === 'stages')?.value.map((stage, i) => (
                      <div 
                        key={i}
                        className="p-3 rounded-lg border border-border bg-card"
                      >
                        <div className="flex items-center justify-between mb-1">
                          <span className="font-medium text-sm">
                            {stage.name || stage.title || stage.stage || `Stage ${i + 1}`}
                          </span>
                          {stage.status && (
                            <span className={cn(
                              "text-xs px-2 py-0.5 rounded",
                              stage.status === 'completed' ? "bg-emerald-500/10 text-emerald-600" :
                              stage.status === 'in_progress' ? "bg-blue-500/10 text-blue-600" :
                              "bg-muted text-muted-foreground"
                            )}>
                              {stage.status.replace('_', ' ')}
                            </span>
                          )}
                        </div>
                        {(stage.date_text || stage.start_date || stage.end_date || stage.date) && (
                          <p className="text-xs text-muted-foreground flex items-center gap-1">
                            <Calendar className="w-3 h-3" />
                            {stage.date_text || 
                             (stage.start_date && stage.end_date 
                              ? `${stage.start_date} → ${stage.end_date}`
                              : stage.date || stage.start_date || stage.end_date)}
                          </p>
                        )}
                        {stage.description && (
                          <p className="text-xs text-muted-foreground mt-1">{stage.description}</p>
                        )}
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Missing Fields - Important Debug Info */}
              {previewData.missing_fields && previewData.missing_fields.length > 0 && (
                <div>
                  <p className="text-xs font-semibold uppercase tracking-wider text-muted-foreground mb-2">
                    Missing Fields
                  </p>
                  <div className="space-y-2">
                    {previewData.missing_fields.map((field, i) => (
                      <div 
                        key={i} 
                        className={cn(
                          "flex items-start gap-2 p-2 rounded-lg border",
                          field.required 
                            ? "bg-amber-500/10 border-amber-500/30" 
                            : "bg-muted/30 border-border"
                        )}
                      >
                        {field.required ? (
                          <AlertCircle className="w-4 h-4 text-amber-500 mt-0.5 flex-shrink-0" />
                        ) : (
                          <Clock className="w-4 h-4 text-muted-foreground mt-0.5 flex-shrink-0" />
                        )}
                        <div>
                          <p className="text-sm font-medium capitalize">
                            {field.name.replace(/_/g, ' ')}
                            {field.required && <span className="text-amber-500 ml-1">*</span>}
                          </p>
                          <p className="text-xs text-muted-foreground">{field.description}</p>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Attachments */}
              {previewData.attachments && previewData.attachments.length > 0 && (
                <div>
                  <p className="text-xs font-semibold uppercase tracking-wider text-muted-foreground mb-2">Attachments</p>
                  <div className="space-y-2">
                    {previewData.attachments.map((file, i) => (
                      <div key={i} className="flex items-center gap-2 p-2 rounded-lg bg-muted/50">
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
                "p-4 rounded-lg border",
                previewData.can_execute 
                  ? "bg-emerald-500/10 border-emerald-500/30" 
                  : "bg-amber-500/10 border-amber-500/30"
              )}>
                <div className="flex items-center gap-2">
                  {previewData.can_execute ? (
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
                        <p className="font-medium text-amber-700 dark:text-amber-400">Cannot Execute</p>
                        <p className="text-xs text-amber-600 dark:text-amber-500">Fill in missing required fields first</p>
                      </div>
                    </>
                  )}
                </div>
              </div>

              {/* Debug Log (collapsible) */}
              {previewData.interpretation_log && previewData.interpretation_log.length > 0 && (
                <details className="group">
                  <summary className="cursor-pointer text-xs font-semibold uppercase tracking-wider text-muted-foreground flex items-center gap-1">
                    <ChevronRight className="w-3 h-3 group-open:rotate-90 transition-transform" />
                    Debug Log
                  </summary>
                  <div className="mt-2 p-2 rounded-lg bg-muted/30 font-mono text-xs space-y-1">
                    {previewData.interpretation_log.map((log, i) => (
                      <p key={i} className="text-muted-foreground">{log}</p>
                    ))}
                  </div>
                </details>
              )}
            </div>
          )}

          <SheetFooter className="mt-8 gap-2">
            <Button
              variant="outline"
              onClick={() => setPreviewOpen(false)}
              disabled={executing}
            >
              Cancel
            </Button>
            <Button
              variant="outline"
              onClick={() => {
                // Edit mode - navigate to the form for this intent
                const editPaths = {
                  'create_invoice': '/agent/invoices/new',
                  'create_quote': '/agent/quotes/new',
                  'create_message': '/agent/feed',
                };
                const path = editPaths[previewData?.intent] || previewData?.suggested_action?.path;
                if (path) {
                  navigate(path);
                  setPreviewOpen(false);
                }
              }}
              disabled={executing}
            >
              <Pencil className="w-4 h-4 mr-2" />
              Edit Manually
            </Button>
            <Button
              onClick={handleExecuteAction}
              disabled={executing || !previewData?.can_execute}
              data-testid="confirm-action-btn"
            >
              {executing ? (
                <Loader2 className="w-4 h-4 mr-2 animate-spin" />
              ) : (
                <CheckCircle className="w-4 h-4 mr-2" />
              )}
              Create Draft
            </Button>
          </SheetFooter>
        </SheetContent>
      </Sheet>

      {/* Workflow Execution Dialog */}
      <Dialog open={workflowDialogOpen} onOpenChange={setWorkflowDialogOpen}>
        <DialogContent className="max-w-lg">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              {selectedWorkflow && (() => {
                const IconComponent = getWorkflowIcon(selectedWorkflow.icon);
                return <IconComponent className="w-5 h-5 text-primary" />;
              })()}
              {selectedWorkflow?.name}
            </DialogTitle>
            <DialogDescription>
              {selectedWorkflow?.description}
            </DialogDescription>
          </DialogHeader>
          
          {/* Workflow Steps Preview */}
          {selectedWorkflow && !workflowResult && (
            <div className="space-y-4 py-4">
              <div className="space-y-2">
                <Label className="text-xs uppercase tracking-wider text-muted-foreground">
                  Workflow Steps
                </Label>
                <div className="space-y-2">
                  {selectedWorkflow.steps_preview?.map((step, i) => (
                    <div 
                      key={i} 
                      className="flex items-center gap-3 p-2 rounded-lg bg-muted/50"
                    >
                      <div className="w-6 h-6 rounded-full bg-primary/10 text-primary flex items-center justify-center text-xs font-medium">
                        {i + 1}
                      </div>
                      <div className="flex-1">
                        <p className="text-sm font-medium">{step.name}</p>
                        <p className="text-xs text-muted-foreground">{step.description}</p>
                      </div>
                      {step.optional && (
                        <Badge variant="outline" className="text-[10px]">Optional</Badge>
                      )}
                    </div>
                  ))}
                </div>
              </div>
              
              {/* Context inputs based on required fields */}
              {selectedWorkflow.required_context?.length > 0 && (
                <div className="space-y-3 pt-2 border-t">
                  <Label className="text-xs uppercase tracking-wider text-muted-foreground">
                    Required Information
                  </Label>
                  
                  {selectedWorkflow.required_context.includes('client_name') && (
                    <div className="space-y-1">
                      <Label htmlFor="wf-client-name" className="text-sm">Client Name</Label>
                      <Input
                        id="wf-client-name"
                        placeholder="Enter client name"
                        value={workflowContext.client_name || ''}
                        onChange={(e) => setWorkflowContext({...workflowContext, client_name: e.target.value})}
                        data-testid="wf-client-name-input"
                      />
                    </div>
                  )}
                  
                  {selectedWorkflow.required_context.includes('client_email') && (
                    <div className="space-y-1">
                      <Label htmlFor="wf-client-email" className="text-sm">Client Email</Label>
                      <Input
                        id="wf-client-email"
                        type="email"
                        placeholder="client@example.com"
                        value={workflowContext.client_email || ''}
                        onChange={(e) => setWorkflowContext({...workflowContext, client_email: e.target.value})}
                        data-testid="wf-client-email-input"
                      />
                    </div>
                  )}
                  
                  {selectedWorkflow.required_context.includes('message_title') && (
                    <div className="space-y-1">
                      <Label htmlFor="wf-message-title" className="text-sm">Message Title</Label>
                      <Input
                        id="wf-message-title"
                        placeholder="Enter message title"
                        value={workflowContext.message_title || ''}
                        onChange={(e) => setWorkflowContext({...workflowContext, message_title: e.target.value})}
                        data-testid="wf-message-title-input"
                      />
                    </div>
                  )}
                  
                  {selectedWorkflow.required_context.includes('message_content') && (
                    <div className="space-y-1">
                      <Label htmlFor="wf-message-content" className="text-sm">Message Content</Label>
                      <Input
                        id="wf-message-content"
                        placeholder="Enter message content"
                        value={workflowContext.message_content || ''}
                        onChange={(e) => setWorkflowContext({...workflowContext, message_content: e.target.value})}
                        data-testid="wf-message-content-input"
                      />
                    </div>
                  )}
                  
                  {selectedWorkflow.ui_selectors?.includes('document') && (
                    <div className="space-y-1">
                      <Label className="text-sm">Select Document</Label>
                      {loadingSelectors ? (
                        <div className="flex items-center gap-2 text-sm text-muted-foreground">
                          <Loader2 className="w-4 h-4 animate-spin" />
                          Loading documents...
                        </div>
                      ) : (
                        <Select 
                          value={workflowContext.document_id || ''} 
                          onValueChange={(value) => setWorkflowContext({...workflowContext, document_id: value})}
                        >
                          <SelectTrigger data-testid="wf-document-select">
                            <SelectValue placeholder="Select a document..." />
                          </SelectTrigger>
                          <SelectContent>
                            {workflowSelectors.documents.length === 0 ? (
                              <SelectItem value="_none" disabled>No documents found</SelectItem>
                            ) : (
                              workflowSelectors.documents.map(doc => (
                                <SelectItem key={doc.document_id} value={doc.document_id}>
                                  <div className="flex items-center gap-2">
                                    <span className={cn(
                                      "px-1.5 py-0.5 text-[10px] rounded",
                                      doc.type === 'Invoice' ? "bg-blue-500/10 text-blue-600" : "bg-purple-500/10 text-purple-600"
                                    )}>
                                      {doc.type}
                                    </span>
                                    <span className="truncate">{doc.title || 'Untitled'}</span>
                                    <span className="text-muted-foreground text-xs">({doc.status})</span>
                                  </div>
                                </SelectItem>
                              ))
                            )}
                          </SelectContent>
                        </Select>
                      )}
                    </div>
                  )}
                  
                  {selectedWorkflow.ui_selectors?.includes('timeline_step') && (
                    <div className="space-y-1">
                      <Label className="text-sm">Select Timeline Step</Label>
                      {loadingSelectors ? (
                        <div className="flex items-center gap-2 text-sm text-muted-foreground">
                          <Loader2 className="w-4 h-4 animate-spin" />
                          Loading steps...
                        </div>
                      ) : (
                        <Select 
                          value={workflowContext.step_id || ''} 
                          onValueChange={(value) => setWorkflowContext({...workflowContext, step_id: value})}
                        >
                          <SelectTrigger data-testid="wf-step-select">
                            <SelectValue placeholder="Select a step..." />
                          </SelectTrigger>
                          <SelectContent>
                            {workflowSelectors.timelineSteps.length === 0 ? (
                              <SelectItem value="_none" disabled>No steps found</SelectItem>
                            ) : (
                              workflowSelectors.timelineSteps.map(step => (
                                <SelectItem key={step.step_id} value={step.step_id}>
                                  <div className="flex items-center gap-2">
                                    <span className={cn(
                                      "w-2 h-2 rounded-full",
                                      step.status === 'completed' ? "bg-emerald-500" :
                                      step.status === 'in_progress' ? "bg-amber-500" : "bg-gray-300"
                                    )} />
                                    <span className="truncate">{step.name}</span>
                                    <span className="text-muted-foreground text-xs">({step.project_name})</span>
                                  </div>
                                </SelectItem>
                              ))
                            )}
                          </SelectContent>
                        </Select>
                      )}
                    </div>
                  )}
                  
                  {/* Show notice for project context */}
                  {selectedWorkflow.required_context.includes('project_id') && !selectedWorkflow.ui_selectors?.length && (
                    <div className={cn(
                      "text-xs flex items-center gap-1 p-2 rounded",
                      selectedProject ? "text-muted-foreground bg-muted/50" : "text-amber-600 bg-amber-500/10"
                    )}>
                      {selectedProject ? (
                        <>
                          <Info className="w-3 h-3" />
                          Project: {selectedProject.name || 'Unknown'}
                        </>
                      ) : (
                        <>
                          <AlertCircle className="w-3 h-3" />
                          Please select a project from the sidebar first
                        </>
                      )}
                    </div>
                  )}
                  
                  {/* Validation feedback */}
                  {!canExecuteWorkflow() && !loadingSelectors && (
                    <div className="text-xs text-amber-600 flex items-center gap-1 mt-2">
                      <AlertCircle className="w-3 h-3" />
                      Fill in required fields to enable workflow execution
                    </div>
                  )}
                </div>
              )}
            </div>
          )}
          
          {/* Workflow Result */}
          {workflowResult && (
            <div className="space-y-4 py-4">
              <div className="flex items-center gap-2">
                {workflowResult.status === 'completed' ? (
                  <CheckCircle className="w-5 h-5 text-emerald-500" />
                ) : workflowResult.status === 'completed_with_warnings' ? (
                  <AlertCircle className="w-5 h-5 text-amber-500" />
                ) : workflowResult.status === 'failed' ? (
                  <AlertCircle className="w-5 h-5 text-destructive" />
                ) : (
                  <Loader2 className="w-5 h-5 animate-spin text-primary" />
                )}
                <span className="font-medium">
                  {workflowResult.status === 'completed' ? 'Workflow Completed' :
                   workflowResult.status === 'completed_with_warnings' ? 'Completed with Warnings' :
                   workflowResult.status === 'failed' ? 'Workflow Failed' : 'In Progress'}
                </span>
              </div>
              
              {/* Warning Banner for workflows with warnings */}
              {workflowResult.status === 'completed_with_warnings' && (
                <div className="p-3 rounded-lg bg-amber-500/15 border border-amber-500/40">
                  <div className="flex items-start gap-2">
                    <AlertCircle className="w-4 h-4 text-amber-600 mt-0.5 flex-shrink-0" />
                    <div>
                      <p className="text-sm font-medium text-amber-800 dark:text-amber-200">
                        Some steps completed with warnings
                      </p>
                      <p className="text-xs text-amber-700 dark:text-amber-300 mt-1">
                        The main actions succeeded, but some side effects (like email notifications) may have failed. 
                        You can retry the affected steps below.
                      </p>
                    </div>
                  </div>
                </div>
              )}
              
              {/* Progress */}
              <Progress 
                value={(workflowResult.progress?.completed / workflowResult.progress?.total) * 100} 
                className="h-2"
              />
              
              {/* Steps status with retry button */}
              <div className="space-y-2">
                {workflowResult.steps?.map((step, i) => (
                  <div 
                    key={i}
                    className={cn(
                      "flex items-center gap-3 p-2 rounded-lg",
                      step.status === 'completed' && "bg-emerald-500/10",
                      step.status === 'completed_with_warning' && "bg-amber-500/15 border border-amber-500/30",
                      step.status === 'failed' && "bg-destructive/10 border border-destructive/30",
                      step.status === 'skipped' && "bg-muted"
                    )}
                    data-testid={`workflow-step-${i}`}
                  >
                    {step.status === 'completed' ? (
                      <CheckCircle className="w-4 h-4 text-emerald-500" />
                    ) : step.status === 'completed_with_warning' ? (
                      <AlertCircle className="w-4 h-4 text-amber-500" />
                    ) : step.status === 'failed' ? (
                      <AlertCircle className="w-4 h-4 text-destructive" />
                    ) : step.status === 'skipped' ? (
                      <X className="w-4 h-4 text-muted-foreground" />
                    ) : (
                      <div className="w-4 h-4 rounded-full border-2 border-muted-foreground" />
                    )}
                    <div className="flex-1 min-w-0">
                      <p className="text-sm">{step.name}</p>
                      {step.error && (
                        <p className="text-xs text-destructive mt-0.5">{step.error}</p>
                      )}
                      {step.warning && (
                        <p className="text-xs text-amber-600 dark:text-amber-400 mt-0.5">
                          <span className="font-medium">Warning:</span> {step.warning}
                        </p>
                      )}
                    </div>
                    {/* Retry button for failed/warning steps */}
                    {step.can_retry && (
                      <Button
                        variant="outline"
                        size="sm"
                        className={cn(
                          "h-7 px-2 text-xs flex-shrink-0",
                          step.status === 'failed' && "border-destructive/50 text-destructive hover:bg-destructive/10",
                          step.status === 'completed_with_warning' && "border-amber-500/50 text-amber-600 hover:bg-amber-500/10"
                        )}
                        onClick={() => retryWorkflowStep(workflowResult.execution_id, step.step_index)}
                        disabled={workflowExecuting}
                        data-testid={`retry-step-${i}`}
                      >
                        {workflowExecuting ? (
                          <Loader2 className="w-3 h-3 animate-spin" />
                        ) : (
                          <>
                            <RefreshCw className="w-3 h-3 mr-1" />
                            Retry
                          </>
                        )}
                      </Button>
                    )}
                  </div>
                ))}
              </div>
            </div>
          )}
          
          <DialogFooter>
            <Button 
              variant="outline" 
              onClick={() => {
                setWorkflowDialogOpen(false);
                setWorkflowResult(null);
                setShowConfirmation(false);
              }}
            >
              {workflowResult ? 'Close' : 'Cancel'}
            </Button>
            {!workflowResult && (
              <Button
                onClick={() => {
                  // Check if workflow is destructive and needs confirmation
                  const isDestructive = selectedWorkflow && ['invoice_paid_processing'].includes(selectedWorkflow.template_id);
                  if (isDestructive && !showConfirmation) {
                    setShowConfirmation(true);
                  } else {
                    executeWorkflow();
                    setShowConfirmation(false);
                  }
                }}
                disabled={!canExecuteWorkflow()}
                data-testid="execute-workflow-btn"
                className={showConfirmation ? 'bg-amber-600 hover:bg-amber-700' : ''}
              >
                {workflowExecuting ? (
                  <Loader2 className="w-4 h-4 mr-2 animate-spin" />
                ) : showConfirmation ? (
                  <AlertCircle className="w-4 h-4 mr-2" />
                ) : (
                  <Play className="w-4 h-4 mr-2" />
                )}
                {showConfirmation ? 'Confirm & Run' : 'Run Workflow'}
              </Button>
            )}
          </DialogFooter>
          
          {/* Confirmation Warning for Destructive Workflows */}
          {showConfirmation && !workflowResult && (
            <div className="mt-4 p-3 rounded-lg bg-amber-500/15 border border-amber-500/40">
              <div className="flex items-start gap-2">
                <AlertCircle className="w-4 h-4 text-amber-600 mt-0.5 flex-shrink-0" />
                <div>
                  <p className="text-sm font-medium text-amber-800 dark:text-amber-200">
                    This action will modify data
                  </p>
                  <p className="text-xs text-amber-700 dark:text-amber-300 mt-1">
                    {selectedWorkflow?.template_id === 'invoice_paid_processing' 
                      ? 'This will mark the selected invoice as Paid. This action cannot be easily undone.'
                      : 'This workflow will modify records. Please confirm to proceed.'}
                  </p>
                </div>
              </div>
            </div>
          )}
        </DialogContent>
      </Dialog>
    </AgentLayout>
  );
};

export default AgentHomePage;
