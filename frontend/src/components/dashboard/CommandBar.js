import { useState, useEffect, useRef, useCallback, forwardRef, useImperativeHandle } from 'react';
import { Card, CardContent } from '../ui/card';
import { Button } from '../ui/button';
import { Input } from '../ui/input';
import { Badge } from '../ui/badge';
import { toast } from 'sonner';
import { cn } from '../../lib/utils';
import { API, getAuthHeaders, getSuggestedAction } from './utils';
import {
  Mic,
  MicOff,
  Upload,
  Send,
  FileUp,
  X,
  Sparkles,
  Loader2,
} from 'lucide-react';

/**
 * CommandBar — handles text, voice, and file input.
 * Emits normalized results via onPreviewReady callback.
 * Does NOT own extraction review or execution logic.
 */
export const CommandBar = forwardRef(({ context, onPreviewReady }, ref) => {
  const [commandText, setCommandText] = useState('');
  const [isListening, setIsListening] = useState(false);
  const [isProcessing, setIsProcessing] = useState(false);
  const [attachments, setAttachments] = useState([]);
  const [isDragActive, setIsDragActive] = useState(false);
  const [voiceSupported, setVoiceSupported] = useState(true);

  const fileInputRef = useRef(null);
  const commandInputRef = useRef(null);
  const recognitionRef = useRef(null);
  const uploadedFileRef = useRef(null);

  // Expose focus method to parent
  useImperativeHandle(ref, () => ({
    focus: () => commandInputRef.current?.focus(),
  }));

  // Keyboard shortcut: Cmd+K / Ctrl+K
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

  // Speech recognition init
  useEffect(() => {
    if ('webkitSpeechRecognition' in window || 'SpeechRecognition' in window) {
      const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
      recognitionRef.current = new SpeechRecognition();
      recognitionRef.current.continuous = false;
      recognitionRef.current.interimResults = true;
      recognitionRef.current.lang = 'en-US';

      recognitionRef.current.onresult = (event) => {
        const transcript = Array.from(event.results).map((r) => r[0].transcript).join('');
        setCommandText(transcript);
      };
      recognitionRef.current.onend = () => setIsListening(false);
      recognitionRef.current.onerror = (event) => {
        setIsListening(false);
        const messages = {
          'not-allowed': 'Microphone access denied.',
          'no-speech': 'No speech detected.',
          'audio-capture': 'No microphone found.',
        };
        toast.error(messages[event.error] || 'Voice input failed.');
      };
      setVoiceSupported(true);
    } else {
      setVoiceSupported(false);
    }
  }, []);

  const toggleVoiceInput = () => {
    if (!voiceSupported || !recognitionRef.current) {
      toast.error('Voice input not supported. Use Chrome or Edge.');
      return;
    }
    if (isListening) {
      recognitionRef.current.stop();
      setIsListening(false);
    } else {
      try {
        recognitionRef.current.start();
        setIsListening(true);
        toast.info('Listening...');
      } catch {
        setIsListening(false);
        toast.error('Could not start voice input.');
      }
    }
  };

  const handleFileSelect = (e) => {
    const files = Array.from(e.target.files);
    if (files.length > 0) {
      uploadedFileRef.current = files[0];
      setAttachments((prev) => [...prev, ...files]);
    }
  };

  const handleFileDrop = useCallback((e) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragActive(false);

    const files = Array.from(e.dataTransfer.files);
    const supported = ['.pdf', '.jpg', '.jpeg', '.png', '.webp'];
    const valid = files.filter((f) => supported.some((ext) => f.name.toLowerCase().endsWith(ext)));

    if (valid.length === 0 && files.length > 0) {
      toast.error('Supported formats: PDF, JPG, PNG, WEBP');
      return;
    }
    if (valid.length > 0) {
      uploadedFileRef.current = valid[0];
      setAttachments((prev) => [...prev, ...valid]);
      toast.success(`${valid.length} file${valid.length > 1 ? 's' : ''} added`);
    }
  }, []);

  const handleDragOver = useCallback((e) => { e.preventDefault(); e.stopPropagation(); setIsDragActive(true); }, []);
  const handleDragLeave = useCallback((e) => {
    e.preventDefault(); e.stopPropagation();
    if (e.currentTarget.contains(e.relatedTarget)) return;
    setIsDragActive(false);
  }, []);

  const removeAttachment = (index) => setAttachments((prev) => prev.filter((_, i) => i !== index));

  const triggerFileUpload = useCallback(() => {
    if (fileInputRef.current) {
      fileInputRef.current.value = '';
      fileInputRef.current.click();
    }
  }, []);

  // --- Submit handlers ---

  const handleCommandSubmit = async () => {
    const currentAttachments = [...attachments];
    const currentText = commandText.trim();

    if (!currentText && currentAttachments.length === 0) {
      toast.error('Please enter a command or attach a file');
      return;
    }

    setIsProcessing(true);

    try {
      if (currentAttachments.length > 0) {
        await handleDocumentUpload(currentAttachments[0], currentText || null);
        return;
      }

      // Text-only command
      const formData = new FormData();
      formData.append('command', currentText);
      formData.append('context', JSON.stringify({
        project_id: context.projectId,
        client_id: context.clientId,
        unit_id: context.unitId,
      }));

      const res = await fetch(`${API}/command/interpret`, {
        method: 'POST',
        credentials: 'include',
        headers: getAuthHeaders(),
        body: formData,
      });

      if (res.ok) {
        const plan = await res.json();
        emitPreview(plan);
        if (!plan.can_execute && plan.missing_fields?.some((f) => f.required)) {
          const missing = plan.missing_fields.filter((f) => f.required).map((f) => f.name.replace('_', ' '));
          toast.warning(`Missing required fields: ${missing.join(', ')}`);
        }
      } else {
        emitPreview(interpretLocally(currentText, currentAttachments));
      }
    } catch {
      emitPreview(interpretLocally(currentText, currentAttachments));
    } finally {
      setIsProcessing(false);
    }
  };

  const handleDocumentUpload = async (file, textContext = null) => {
    let classification = null;
    try {
      const allowedTypes = ['application/pdf', 'image/jpeg', 'image/png', 'image/webp'];
      const ext = file.name.toLowerCase().slice(file.name.lastIndexOf('.'));
      if (!allowedTypes.includes(file.type) && !['.pdf', '.jpg', '.jpeg', '.png', '.webp'].includes(ext)) {
        toast.error('Supported formats: PDF, JPG, PNG, WEBP');
        setIsProcessing(false);
        return;
      }

      toast.info('Analyzing document...');
      const classifyForm = new FormData();
      classifyForm.append('file', file);
      if (textContext) classifyForm.append('text_hint', textContext);

      const classifyRes = await fetch(`${API}/command/classify-document`, {
        method: 'POST', credentials: 'include', headers: getAuthHeaders(), body: classifyForm,
      });
      if (!classifyRes.ok) throw new Error('Classification failed');
      classification = await classifyRes.json();

      if (classification.document_type === 'unknown') {
        toast.warning('Could not classify document. Please select type.');
        emitPreview({
          intent: 'unknown', document_type: 'unknown', can_execute: false,
          requires_manual_classification: true, classification,
          attachments: [{ name: file.name, size: file.size }], fields: [],
          missing_fields: [{ name: 'document_type', description: 'Select document type', required: true }],
          source_file: classification.file_path, original_file: file,
          interpretation_log: [`Low confidence (${Math.round(classification.confidence * 100)}%)`],
        });
        return;
      }

      toast.success(`Detected: ${classification.document_type} (${Math.round(classification.confidence * 100)}%)`);

      const extractForm = new FormData();
      extractForm.append('file_path', classification.file_path);
      extractForm.append('document_type', classification.document_type);
      extractForm.append('context', JSON.stringify({
        project_id: context.projectId, client_id: context.clientId, unit_id: context.unitId,
        text_hint: textContext,
      }));

      const extractRes = await fetch(`${API}/command/extract-document`, {
        method: 'POST', credentials: 'include', headers: getAuthHeaders(), body: extractForm,
      });
      if (!extractRes.ok) throw new Error('Extraction failed');

      const plan = await extractRes.json();
      plan.classification = classification;
      plan.attachments = [{ name: file.name, size: file.size }];
      plan.source_file = classification.file_path;
      plan.original_file = file;

      emitPreview(plan);
      if (!plan.can_execute && plan.missing_fields?.some((f) => f.required)) {
        toast.warning(`Missing fields: ${plan.missing_fields.filter((f) => f.required).map((f) => f.name.replace('_', ' ')).join(', ')}`);
      }
    } catch {
      toast.error('Failed to process document.');
      const fallbackType = classification?.document_type || 'unknown';
      emitPreview({
        intent: fallbackType === 'unknown' ? 'unknown' : `extract_${fallbackType}`,
        document_type: fallbackType, can_execute: false,
        requires_manual_classification: fallbackType === 'unknown',
        classification: classification || { filename: file.name, document_type: fallbackType, confidence: 0.5 },
        attachments: [{ name: file.name, size: file.size }], fields: [],
        original_file: file, source_file: classification?.file_path,
        missing_fields: fallbackType === 'unknown'
          ? [{ name: 'document_type', description: 'Select type manually', required: true }]
          : [{ name: 'extraction_failed', description: 'Click Re-run Extraction', required: false }],
        interpretation_log: fallbackType === 'unknown'
          ? ['Classification failed', 'Select type manually']
          : [`Classified as ${fallbackType}`, 'Extraction failed'],
      });
    } finally {
      setIsProcessing(false);
    }
  };

  const emitPreview = (data) => {
    if (onPreviewReady) onPreviewReady(data, uploadedFileRef);
  };

  const clearState = () => {
    setCommandText('');
    setAttachments([]);
    uploadedFileRef.current = null;
  };

  // Expose clearState so parent can call it after execution
  useImperativeHandle(ref, () => ({
    focus: () => commandInputRef.current?.focus(),
    clear: clearState,
    getUploadedFileRef: () => uploadedFileRef,
  }));

  const interpretLocally = (text, files) => {
    const lower = text.toLowerCase();
    let intent = 'unknown';
    if (lower.includes('invoice') || lower.includes('bill')) intent = 'create_invoice';
    else if (lower.includes('quote') || lower.includes('estimate')) intent = 'create_quote';
    else if (lower.includes('message') || lower.includes('send')) intent = 'send_message';
    else if (lower.includes('post') || lower.includes('update')) intent = 'create_feed_post';
    else if (lower.includes('timeline') || lower.includes('schedule')) intent = 'upload_timeline';
    else if (files.length > 0) intent = 'upload_document';

    return {
      intent, confidence: 0.75,
      entities: { project_id: context.projectId, client_id: context.clientId, unit_id: context.unitId },
      fields: {}, attachments: files.map((f) => ({ name: f.name, size: f.size, type: f.type })),
      raw_command: text, requires_confirmation: true,
      suggested_action: getSuggestedAction(intent),
    };
  };

  return (
    <Card className="border-primary/20 bg-gradient-to-br from-primary/5 to-transparent shadow-sm">
      <CardContent className="pt-5 pb-4 space-y-3">
        <div className="flex items-center gap-2 text-sm text-muted-foreground mb-1">
          <Sparkles className="w-4 h-4 text-primary" />
          <span>Command Bar</span>
          <span className="text-xs text-muted-foreground/60 ml-auto">Type, speak, or drop a file</span>
        </div>

        <input
          ref={fileInputRef}
          type="file"
          id="command-file-input"
          className="hidden"
          onChange={handleFileSelect}
          accept=".pdf,application/pdf,.jpg,.jpeg,.png,.webp,image/jpeg,image/png,image/webp"
        />

        <div
          className={cn(
            'relative rounded-xl border-2 transition-all duration-200 p-4',
            isDragActive ? 'border-primary bg-primary/10 border-solid scale-[1.02] shadow-lg'
              : attachments.length > 0 ? 'border-primary/50 bg-primary/5 border-dashed'
              : 'border-border bg-background border-dashed hover:border-primary/30'
          )}
          onDragOver={handleDragOver}
          onDragLeave={handleDragLeave}
          onDrop={handleFileDrop}
          data-testid="command-drop-zone"
        >
          {isDragActive && (
            <div className="absolute inset-0 flex items-center justify-center bg-primary/5 rounded-xl z-10 pointer-events-none">
              <div className="flex flex-col items-center gap-2 text-primary">
                <Upload className="w-10 h-10 animate-bounce" />
                <span className="font-medium text-lg">Drop file here</span>
                <span className="text-sm text-muted-foreground">PDF, JPG, PNG, WEBP</span>
              </div>
            </div>
          )}

          <div className="flex items-center gap-3">
            {voiceSupported ? (
              <Button
                variant={isListening ? 'default' : 'outline'}
                size="icon"
                className={cn('rounded-full flex-shrink-0', isListening && 'bg-red-500 hover:bg-red-600')}
                onClick={toggleVoiceInput}
                data-testid="voice-input-btn"
              >
                {isListening ? <MicOff className="w-5 h-5" /> : <Mic className="w-5 h-5" />}
              </Button>
            ) : (
              <Button variant="outline" size="icon" className="rounded-full flex-shrink-0 opacity-50" disabled data-testid="voice-input-btn-disabled">
                <Mic className="w-5 h-5" />
              </Button>
            )}

            <Input
              ref={commandInputRef}
              value={commandText}
              onChange={(e) => setCommandText(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && !e.shiftKey && handleCommandSubmit()}
              placeholder={isDragActive ? 'Drop file to upload...' : 'Type a command or drop a file... (Cmd+K)'}
              className="flex-1 border-0 bg-transparent text-lg focus-visible:ring-0 focus-visible:ring-offset-0"
              disabled={isProcessing || isDragActive}
              data-testid="command-input"
            />

            <Button variant="outline" size="icon" className="rounded-full flex-shrink-0 relative z-20" onClick={triggerFileUpload} type="button" data-testid="file-upload-btn">
              <Upload className="w-5 h-5" />
            </Button>

            <Button size="icon" className="rounded-full flex-shrink-0" onClick={handleCommandSubmit} disabled={isProcessing || (!commandText.trim() && attachments.length === 0)} data-testid="submit-command-btn">
              {isProcessing ? <Loader2 className="w-5 h-5 animate-spin" /> : <Send className="w-5 h-5" />}
            </Button>
          </div>

          {attachments.length > 0 && (
            <div className="flex flex-wrap gap-2 mt-3 pt-3 border-t border-border">
              {attachments.map((file, i) => (
                <Badge key={file.name + i} variant="secondary" className="flex items-center gap-2 py-1.5 px-3">
                  <FileUp className="w-3 h-3" />
                  <span className="max-w-[150px] truncate">{file.name}</span>
                  <button onClick={() => removeAttachment(i)} className="hover:text-destructive"><X className="w-3 h-3" /></button>
                </Badge>
              ))}
            </div>
          )}

          {attachments.length === 0 && !isDragActive && (
            <label htmlFor="command-file-input" className="flex items-center justify-center gap-2 mt-2 py-2 text-xs text-muted-foreground hover:text-primary cursor-pointer transition-colors">
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
  );
});

CommandBar.displayName = 'CommandBar';
