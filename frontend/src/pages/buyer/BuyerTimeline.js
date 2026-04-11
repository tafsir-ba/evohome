import { useState, useEffect, useCallback } from 'react';
import { useAuth } from '../../context/AuthContext';
import { useSettings } from '../../context/SettingsContext';
import { useWebSocket } from '../../hooks/useWebSocket';
import { Button } from '../../components/ui/button';
import { Card, CardContent } from '../../components/ui/card';
import { Textarea } from '../../components/ui/textarea';
import { Input } from '../../components/ui/input';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter, DialogDescription } from '../../components/ui/dialog';
import { toast } from 'sonner';
import { ThemeToggle } from '../../components/ThemeToggle';
import { NotificationCenter } from '../../components/NotificationCenter';
import { PdfViewer } from '../../components/PdfViewer';
import { 
  Home, 
  LogOut, 
  FileText, 
  Receipt, 
  CheckCircle, 
  XCircle, 
  MessageCircle,
  Clock,
  Download,
  ChevronDown,
  ChevronUp,
  HardHat,
  CreditCard,
  Send,
  Loader2,
  Calendar,
  Eye,
  Search,
  X,
  QrCode,
  Copy,
  ExternalLink,
  ImageIcon,
  Bell,
  Users,
  Mail,
  Phone,
  Building2,
  FolderOpen,
  FileCheck,
  AlertTriangle,
  File,
  FileSpreadsheet
} from 'lucide-react';
import { cn } from '../../lib/utils';
import { Feed } from '../../components/Feed';

const API = process.env.REACT_APP_BACKEND_URL + '/api';

const getAuthHeaders = () => {
  const token = localStorage.getItem('auth_token');
  return token ? { 'Authorization': `Bearer ${token}` } : {};
};

const formatCurrency = (amount, currency = 'CHF') => {
  return `${currency} ${new Intl.NumberFormat('de-CH', { 
    style: 'decimal', 
    minimumFractionDigits: 2,
    maximumFractionDigits: 2 
  }).format(amount)}`;
};

const formatDate = (dateStr) => {
  if (!dateStr) return '';
  const date = new Date(dateStr);
  return date.toLocaleDateString('en-GB', { day: 'numeric', month: 'short', year: 'numeric' });
};

const formatRelativeTime = (dateStr) => {
  const date = new Date(dateStr);
  const now = new Date();
  const diff = now - date;
  const days = Math.floor(diff / (1000 * 60 * 60 * 24));
  
  if (days === 0) return 'Today';
  if (days === 1) return 'Yesterday';
  if (days < 7) return `${days} days ago`;
  return formatDate(dateStr);
};

// Status configurations
const statusConfig = {
  'Sent': { 
    label: 'Awaiting Response', 
    color: 'bg-amber-500/10 text-amber-600 dark:text-amber-400 border-amber-500/20',
    icon: Clock
  },
  'Draft': { 
    label: 'Draft', 
    color: 'bg-gray-500/10 text-gray-600 dark:text-gray-400 border-gray-500/20',
    icon: FileText
  },
  'Change Requested': { 
    label: 'Under Review', 
    color: 'bg-blue-500/10 text-blue-600 dark:text-blue-400 border-blue-500/20',
    icon: MessageCircle
  },
  'Approved': { 
    label: 'Approved', 
    color: 'bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border-emerald-500/20',
    icon: CheckCircle
  },
  'Rejected': { 
    label: 'Declined', 
    color: 'bg-red-500/10 text-red-600 dark:text-red-400 border-red-500/20',
    icon: XCircle
  },
  'Paid': { 
    label: 'Paid', 
    color: 'bg-green-500/10 text-green-600 dark:text-green-400 border-green-500/20',
    icon: CheckCircle
  },
};

// E-Commerce Style Timeline Card
const TimelineCard = ({ event, onAction, onDownloadPdf, onPreviewPdf, onShowQrPayment }) => {
  const [expanded, setExpanded] = useState(event.actionRequired);
  const [showQuestionInput, setShowQuestionInput] = useState(false);
  const [question, setQuestion] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);

  const config = statusConfig[event.status] || statusConfig['Draft'];
  const StatusIcon = config.icon;
  
  const isQuote = event.type === 'quote';
  const isInvoice = event.type === 'invoice';
  const isQuoteActionable = isQuote && event.status === 'Sent';
  const needsPayment = isInvoice && event.status === 'Sent';

  const handleQuestionSubmit = async () => {
    if (!question.trim()) return;
    setIsSubmitting(true);
    await onAction(event.id, 'request_change', question);
    setQuestion('');
    setShowQuestionInput(false);
    setIsSubmitting(false);
  };

  return (
    <div className="mb-6" data-testid={`timeline-event-${event.id}`}>
      <Card className={cn(
        "overflow-hidden transition-all duration-300 hover:shadow-xl",
        event.actionRequired && "ring-2 ring-primary/30 shadow-lg",
        !event.actionRequired && "hover:shadow-lg"
      )}>
        {/* Hero Image or Placeholder */}
        <div className={cn(
          "relative overflow-hidden",
          event.heroImageUrl ? "h-44" : "h-32"
        )}>
          {event.heroImageUrl ? (
            <>
              <img 
                src={`${API.replace('/api', '')}${event.heroImageUrl}`}
                alt={event.title}
                className="w-full h-full object-cover"
              />
              <div className="absolute inset-0 bg-gradient-to-t from-black/60 via-transparent to-transparent" />
            </>
          ) : (
            <div className={cn(
              "w-full h-full flex items-center justify-center",
              isInvoice 
                ? "bg-gradient-to-br from-purple-500/20 via-purple-400/10 to-purple-600/20" 
                : "bg-gradient-to-br from-primary/20 via-blue-400/10 to-primary/20"
            )}>
              <div className="text-center">
                <div className={cn(
                  "w-14 h-14 rounded-2xl flex items-center justify-center mx-auto mb-2",
                  isInvoice ? "bg-purple-500/20" : "bg-primary/20"
                )}>
                  {isInvoice ? (
                    <Receipt className={cn("w-7 h-7", isInvoice ? "text-purple-500" : "text-primary")} />
                  ) : (
                    <FileText className="w-7 h-7 text-primary" />
                  )}
                </div>
                <p className={cn(
                  "text-xs font-medium uppercase tracking-wider",
                  isInvoice ? "text-purple-500/70" : "text-primary/70"
                )}>
                  {isInvoice ? 'Invoice' : 'Quote'}
                </p>
              </div>
            </div>
          )}
        </div>

        <CardContent className="p-0">
          {/* Main Card Content */}
          <div 
            className="p-5 cursor-pointer"
            onClick={() => setExpanded(!expanded)}
          >
            {/* Type & Status Row */}
            <div className="flex items-center gap-2 mb-3">
              <span className={cn(
                "inline-flex items-center px-2.5 py-1 text-[10px] font-bold rounded-full border uppercase tracking-wider",
                isInvoice 
                  ? "bg-purple-500/10 text-purple-600 dark:text-purple-400 border-purple-500/20" 
                  : "bg-blue-500/10 text-blue-600 dark:text-blue-400 border-blue-500/20"
              )}>
                {isInvoice ? 'Invoice' : 'Quote'}
              </span>
              <span className={cn(
                "inline-flex items-center px-2.5 py-1 text-[10px] font-bold rounded-full border uppercase tracking-wider",
                config.color
              )}>
                <StatusIcon className="w-3 h-3 mr-1" />
                {config.label}
              </span>
              {event.actionRequired && (
                <span className="ml-auto inline-flex items-center px-2.5 py-1 text-[10px] font-bold rounded-full bg-primary text-primary-foreground uppercase tracking-wider animate-pulse">
                  Action Required
                </span>
              )}
            </div>

            {/* Title & Amount */}
            <div className="flex flex-col sm:flex-row sm:items-start sm:justify-between gap-2 sm:gap-4 mb-3">
              <div className="flex-1 min-w-0">
                <h3 className="font-bold text-foreground text-lg sm:text-2xl leading-tight mb-1 break-words">{event.title}</h3>
                <p className="text-[10px] sm:text-[11px] text-muted-foreground/70">
                  {event.documentNumber} · <span className="text-muted-foreground/50">{event.supplierName || 'From your agent'}</span>
                </p>
              </div>
              <div className="sm:text-right flex-shrink-0">
                <p className="text-2xl sm:text-3xl font-bold text-foreground tracking-tight">{formatCurrency(event.amount, event.currency)}</p>
                {needsPayment && event.dueDate && (
                  <p className="text-xs text-amber-600 dark:text-amber-400 font-medium mt-0.5">
                    Due {formatDate(event.dueDate)}
                  </p>
                )}
              </div>
            </div>

            {/* Summary */}
            {event.summary && (
              <p className="text-sm text-muted-foreground mb-3 line-clamp-2">{event.summary}</p>
            )}

            {/* Footer: Date & Expand */}
            <div className="flex items-center justify-between pt-2 border-t border-border/50">
              <span className="text-xs text-muted-foreground flex items-center gap-1">
                <Calendar className="w-3 h-3" />
                {formatRelativeTime(event.date)}
              </span>
              <span className="text-xs text-muted-foreground flex items-center gap-1">
                {expanded ? 'Hide details' : 'Show details'}
                {expanded ? (
                  <ChevronUp className="w-4 h-4" />
                ) : (
                  <ChevronDown className="w-4 h-4" />
                )}
              </span>
            </div>
          </div>

          {/* Expanded Content */}
          {expanded && (
            <div className="border-t border-border p-5 space-y-4 animate-fade-in bg-muted/30">
              {/* Line Items Preview */}
              {event.items && event.items.length > 0 && (
                <div className="space-y-2">
                  <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">What's included</p>
                  <div className="grid gap-1.5">
                    {event.items.slice(0, 4).map((item, idx) => (
                      <div key={idx} className="flex items-center justify-between text-sm py-1.5 px-3 bg-background rounded-lg">
                        <span className="text-foreground">{item.description}</span>
                        <span className="text-muted-foreground font-medium">{formatCurrency(item.total, event.currency)}</span>
                      </div>
                    ))}
                    {event.items.length > 4 && (
                      <p className="text-xs text-muted-foreground px-3">+{event.items.length - 4} more items</p>
                    )}
                  </div>
                </div>
              )}

              {/* Change Request Comment */}
              {event.changeComment && (
                <div className="p-3 bg-blue-500/10 rounded-lg border border-blue-500/20">
                  <p className="text-xs font-semibold text-blue-600 dark:text-blue-400 mb-1">Your question</p>
                  <p className="text-sm text-foreground">{event.changeComment}</p>
                </div>
              )}

              {/* Document Actions */}
              <div className="flex gap-2">
                {event.hasSourcePdf && (
                  <Button
                    variant="outline"
                    size="sm"
                    className="flex-1"
                    onClick={(e) => {
                      e.stopPropagation();
                      onPreviewPdf(event.id, event.title);
                    }}
                    data-testid={`preview-pdf-${event.id}`}
                  >
                    <Eye className="w-4 h-4 mr-2" />
                    View Document
                  </Button>
                )}
                <Button
                  variant="outline"
                  size="sm"
                  className="flex-1"
                  onClick={(e) => {
                    e.stopPropagation();
                    onDownloadPdf(event.id);
                  }}
                  data-testid={`download-pdf-${event.id}`}
                >
                  <Download className="w-4 h-4 mr-2" />
                  Download PDF
                </Button>
              </div>

              {/* Action Buttons for Quotes */}
              {isQuoteActionable && !showQuestionInput && (
                <div className="flex flex-col sm:flex-row gap-2 sm:gap-3 pt-2">
                  <Button
                    className="bg-emerald-600 hover:bg-emerald-700 text-white h-12 sm:h-12 text-sm sm:text-base flex-1 font-medium"
                    onClick={(e) => {
                      e.stopPropagation();
                      onAction(event.id, 'approve');
                    }}
                    data-testid={`approve-${event.id}`}
                  >
                    <CheckCircle className="w-5 h-5 mr-2" />
                    Approve Quote
                  </Button>
                  <Button
                    variant="destructive"
                    className="h-12 sm:h-12 text-sm sm:text-base flex-1 font-medium"
                    onClick={(e) => {
                      e.stopPropagation();
                      onAction(event.id, 'reject');
                    }}
                    data-testid={`reject-${event.id}`}
                  >
                    <XCircle className="w-5 h-5 mr-2" />
                    Decline
                  </Button>
                  <Button
                    variant="outline"
                    className="h-12 sm:h-12 text-sm sm:text-base flex-1 font-medium"
                    onClick={(e) => {
                      e.stopPropagation();
                      setShowQuestionInput(true);
                    }}
                    data-testid={`question-${event.id}`}
                  >
                    <MessageCircle className="w-5 h-5 mr-2" />
                    Ask Question
                  </Button>
                </div>
              )}

              {/* Question Input - works for both quotes and invoices */}
              {showQuestionInput && (
                <div className="space-y-3 pt-2">
                  <Textarea
                    placeholder="Type your question or request..."
                    value={question}
                    onChange={(e) => setQuestion(e.target.value)}
                    rows={3}
                    className="resize-none"
                    data-testid={`question-input-${event.id}`}
                  />
                  <div className="flex gap-2">
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => setShowQuestionInput(false)}
                      className="flex-1"
                    >
                      Cancel
                    </Button>
                    <Button
                      size="sm"
                      onClick={handleQuestionSubmit}
                      disabled={!question.trim() || isSubmitting}
                      className="flex-1"
                      data-testid={`send-question-${event.id}`}
                    >
                      {isSubmitting ? (
                        <Loader2 className="w-4 h-4 animate-spin" />
                      ) : (
                        <>
                          <Send className="w-4 h-4 mr-1.5" />
                          Send
                        </>
                      )}
                    </Button>
                  </div>
                </div>
              )}

              {/* Paid Invoice Display */}
              {needsPayment && !showQuestionInput && (
                <div className="pt-2 space-y-3">
                  <div className="flex flex-col sm:flex-row gap-2 sm:gap-3">
                    <Button
                      className="h-12 sm:h-12 bg-primary hover:bg-primary/90 flex-1 text-sm sm:text-base font-medium"
                      onClick={(e) => {
                        e.stopPropagation();
                        onShowQrPayment(event);
                      }}
                      data-testid={`qr-payment-${event.id}`}
                    >
                      <QrCode className="w-5 h-5 mr-2" />
                      Pay with QR
                    </Button>
                    <Button
                      variant="outline"
                      className="h-12 sm:h-12 flex-1 text-sm sm:text-base font-medium"
                      onClick={(e) => {
                        e.stopPropagation();
                        onAction(event.id, 'confirm_payment');
                      }}
                      data-testid={`confirm-payment-${event.id}`}
                    >
                      <CheckCircle className="w-5 h-5 mr-2" />
                      I've Paid
                    </Button>
                    <Button
                      variant="outline"
                      className="h-12 sm:h-12 flex-1 text-sm sm:text-base font-medium"
                      onClick={(e) => {
                        e.stopPropagation();
                        setShowQuestionInput(true);
                      }}
                      data-testid={`invoice-question-${event.id}`}
                    >
                      <MessageCircle className="w-5 h-5 mr-2" />
                      Question
                    </Button>
                  </div>
                  <p className="text-xs text-muted-foreground text-center">
                    Scan QR with your banking app, confirm after transfer, or ask a question
                  </p>
                </div>
              )}

              {/* Paid Invoice Display */}
              {isInvoice && event.status === 'Paid' && (
                <div className="flex items-center gap-2 p-3 bg-green-500/10 rounded-lg">
                  <CheckCircle className="w-5 h-5 text-green-600" />
                  <span className="text-sm font-medium text-green-700 dark:text-green-400">
                    Payment completed
                  </span>
                </div>
              )}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
};

// Construction Phase Card
const ConstructionPhaseCard = ({ stages }) => {
  const [expanded, setExpanded] = useState(false);
  
  if (!stages || stages.length === 0) return null;
  
  const completedCount = stages.filter(s => s.status === 'completed' || s.status === 'approved').length;
  const currentStage = stages.find(s => s.status === 'in_progress') || stages.find(s => s.status === 'pending');
  const progressPercent = stages.length > 0 ? Math.round((completedCount / stages.length) * 100) : 0;

  const API_BASE = process.env.REACT_APP_BACKEND_URL;

  return (
    <Card className="mb-6 overflow-hidden">
      <CardContent className="p-0">
        <div 
          className="p-4 cursor-pointer bg-muted/30"
          onClick={() => setExpanded(!expanded)}
          data-testid="construction-progress-header"
        >
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-xl bg-primary/10 flex items-center justify-center">
                <HardHat className="w-5 h-5 text-primary" />
              </div>
              <div>
                <p className="text-xs text-muted-foreground uppercase tracking-wider font-medium">Construction Progress</p>
                <p className="font-semibold text-foreground">
                  {currentStage ? currentStage.name : 'All Complete'}
                </p>
              </div>
            </div>
            <div className="flex items-center gap-3">
              <div className="text-right">
                <p className="text-lg font-bold text-foreground">{progressPercent}%</p>
                <p className="text-xs text-muted-foreground">{completedCount}/{stages.length} stages</p>
              </div>
              {expanded ? (
                <ChevronUp className="w-5 h-5 text-muted-foreground" />
              ) : (
                <ChevronDown className="w-5 h-5 text-muted-foreground" />
              )}
            </div>
          </div>
          
          <div className="mt-3 h-2 bg-muted rounded-full overflow-hidden">
            <div 
              className="h-full bg-primary rounded-full transition-all duration-500"
              style={{ width: `${progressPercent}%` }}
            />
          </div>
        </div>

        {expanded && (
          <div className="border-t border-border p-4 space-y-3 animate-fade-in">
            {stages.map((stage, idx) => {
              const isCompleted = stage.status === 'completed' || stage.status === 'approved';
              const isCurrent = stage.status === 'in_progress';
              const isPending = stage.status === 'pending';
              
              return (
                <div 
                  key={stage.step_id} 
                  className={cn(
                    "p-3 rounded-lg border",
                    isCurrent && "bg-primary/5 border-primary/30",
                    isCompleted && "bg-emerald-500/5 border-emerald-500/20",
                    isPending && "bg-muted/30 border-border"
                  )}
                  data-testid={`construction-stage-${stage.step_id}`}
                >
                  <div className="flex items-start gap-3">
                    <div className={cn(
                      "w-8 h-8 rounded-full flex items-center justify-center flex-shrink-0 mt-0.5",
                      isCompleted && "bg-emerald-500 text-white",
                      isCurrent && "bg-primary text-primary-foreground",
                      isPending && "bg-muted text-muted-foreground"
                    )}>
                      {isCompleted ? (
                        <CheckCircle className="w-4 h-4" />
                      ) : isCurrent ? (
                        <Clock className="w-4 h-4" />
                      ) : (
                        <span className="text-xs font-bold">{idx + 1}</span>
                      )}
                    </div>
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2">
                        <span className="font-medium text-foreground">{stage.title}</span>
                        {isCurrent && (
                          <span className="text-[10px] font-semibold uppercase tracking-wider px-2 py-0.5 rounded-full bg-primary text-primary-foreground">
                            In Progress
                          </span>
                        )}
                        {isCompleted && (
                          <span className="text-[10px] font-semibold uppercase tracking-wider px-2 py-0.5 rounded-full bg-emerald-500/10 text-emerald-600">
                            Complete
                          </span>
                        )}
                      </div>
                      {stage.description && (
                        <p className="text-sm text-muted-foreground mt-1">{stage.description}</p>
                      )}
                      
                      {/* Dates */}
                      <div className="flex items-center gap-4 mt-2 text-xs text-muted-foreground">
                        {stage.planned_date && (
                          <span className="flex items-center gap-1">
                            <Calendar className="w-3 h-3" />
                            {isPending ? 'Planned' : 'Target'}: {new Date(stage.planned_date).toLocaleDateString('en-GB', { day: 'numeric', month: 'short' })}
                          </span>
                        )}
                        {stage.completed_at && (
                          <span className="flex items-center gap-1 text-emerald-600">
                            <CheckCircle className="w-3 h-3" />
                            Done: {new Date(stage.completed_at).toLocaleDateString('en-GB', { day: 'numeric', month: 'short' })}
                          </span>
                        )}
                      </div>
                      
                      {/* Linked documents - only for current and completed stages */}
                      {(isCurrent || isCompleted) && stage.documents && stage.documents.length > 0 && (
                        <div className="mt-3 flex flex-wrap gap-2">
                          {stage.documents.map(doc => (
                            <a
                              key={doc.activity_id}
                              href={doc.file_url ? `${API_BASE}${doc.file_url}` : '#'}
                              target="_blank"
                              rel="noopener noreferrer"
                              className="flex items-center gap-1.5 px-2 py-1 bg-background border border-border rounded text-xs hover:border-primary/50 transition-colors"
                            >
                              <FileText className="w-3 h-3 text-muted-foreground" />
                              <span className="truncate max-w-[120px]">{doc.title || doc.file_name || 'Document'}</span>
                              {doc.file_url && <Download className="w-3 h-3 text-primary" />}
                            </a>
                          ))}
                        </div>
                      )}
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </CardContent>
    </Card>
  );
};

// Vault Document Card for Buyers
const VaultDocumentCard = ({ document, onPreview, onDownload }) => {
  const getCategoryColor = (category) => {
    const colors = {
      'Contracts': 'bg-purple-500/10 text-purple-600 dark:text-purple-400 border-purple-500/20',
      'Plans': 'bg-blue-500/10 text-blue-600 dark:text-blue-400 border-blue-500/20',
      'Permits': 'bg-amber-500/10 text-amber-600 dark:text-amber-400 border-amber-500/20',
      'Reports': 'bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 border-emerald-500/20',
      'Other': 'bg-gray-500/10 text-gray-600 dark:text-gray-400 border-gray-500/20',
    };
    return colors[category] || colors['Other'];
  };

  const getDocTypeIcon = (docType) => {
    if (docType === 'action_required') {
      return <AlertTriangle className="w-4 h-4 text-amber-500" />;
    }
    return <FileCheck className="w-4 h-4 text-emerald-500" />;
  };

  const getFileIcon = (fileType, filename) => {
    // Check by mime type first
    if (fileType?.includes('pdf')) return <FileText className="w-5 h-5" />;
    if (fileType?.includes('image')) return <ImageIcon className="w-5 h-5" />;
    if (fileType?.includes('word') || fileType?.includes('document')) return <FileText className="w-5 h-5" />;
    if (fileType?.includes('sheet') || fileType?.includes('excel')) return <FileSpreadsheet className="w-5 h-5" />;
    
    // Fallback to extension
    const ext = (filename || '').split('.').pop()?.toLowerCase();
    if (['pdf'].includes(ext)) return <FileText className="w-5 h-5" />;
    if (['jpg', 'jpeg', 'png', 'gif', 'webp', 'svg'].includes(ext)) return <ImageIcon className="w-5 h-5" />;
    if (['doc', 'docx'].includes(ext)) return <FileText className="w-5 h-5" />;
    if (['xls', 'xlsx', 'csv'].includes(ext)) return <FileSpreadsheet className="w-5 h-5" />;
    return <File className="w-5 h-5" />;
  };

  const formatFileSize = (bytes) => {
    if (!bytes) return '';
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  };

  return (
    <Card 
      className={cn(
        "overflow-hidden transition-all duration-200 hover:shadow-md mb-3",
        document.doc_type === 'action_required' && "ring-1 ring-amber-500/30"
      )}
      data-testid={`vault-doc-${document.vault_id}`}
    >
      <CardContent className="p-3 sm:p-4">
        <div className="flex items-start gap-3 sm:gap-4">
          {/* File Icon */}
          <div className={cn(
            "w-10 h-10 sm:w-12 sm:h-12 rounded-xl flex items-center justify-center flex-shrink-0",
            document.doc_type === 'action_required' 
              ? "bg-amber-500/10 text-amber-600"
              : "bg-primary/10 text-primary"
          )}>
            {getFileIcon(document.file_type, document.original_filename)}
          </div>
          
          {/* Content */}
          <div className="flex-1 min-w-0">
            <div className="flex flex-col sm:flex-row sm:items-start sm:justify-between gap-1 sm:gap-2">
              <div className="min-w-0 flex-1">
                {/* Document title - full display, wraps on mobile */}
                <h3 className="font-medium text-foreground text-sm sm:text-base leading-tight break-words" title={document.name || document.original_filename}>
                  {document.name || document.original_filename || 'Untitled Document'}
                </h3>
                <div className="flex items-center gap-2 mt-1.5 flex-wrap">
                  <span className={cn(
                    "inline-flex items-center px-2 py-0.5 text-[10px] font-semibold rounded-full border uppercase tracking-wider",
                    getCategoryColor(document.category)
                  )}>
                    {document.category}
                  </span>
                  <span className="flex items-center gap-1 text-[10px] sm:text-xs text-muted-foreground">
                    {getDocTypeIcon(document.doc_type)}
                    <span className="hidden xs:inline">{document.doc_type === 'action_required' ? 'Action Required' : 'General'}</span>
                  </span>
                </div>
              </div>
            </div>
            
            {/* Notes */}
            {document.notes && (
              <p className="text-xs sm:text-sm text-muted-foreground mt-2 line-clamp-2">{document.notes}</p>
            )}
            
            {/* Meta & Actions */}
            <div className="flex flex-col xs:flex-row items-start xs:items-center justify-between gap-2 mt-3 pt-3 border-t border-border/50">
              <div className="flex items-center gap-2 sm:gap-3 text-[10px] sm:text-xs text-muted-foreground">
                <span className="flex items-center gap-1">
                  <Calendar className="w-3 h-3" />
                  {formatDate(document.created_at)}
                </span>
                {document.file_size && (
                  <span>{formatFileSize(document.file_size)}</span>
                )}
              </div>
              <div className="flex items-center gap-1 sm:gap-2 w-full xs:w-auto">
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => onPreview(document)}
                  className="h-8 px-2 sm:px-3 flex-1 xs:flex-initial text-xs"
                  data-testid={`preview-vault-doc-${document.vault_id}`}
                >
                  <Eye className="w-3 h-3 sm:w-4 sm:h-4 mr-1" />
                  View
                </Button>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => onDownload(document)}
                  className="h-8 px-2 sm:px-3 flex-1 xs:flex-initial text-xs"
                  data-testid={`download-vault-doc-${document.vault_id}`}
                >
                  <Download className="w-3 h-3 sm:w-4 sm:h-4 mr-1" />
                  Download
                </Button>
              </div>
            </div>
          </div>
        </div>
      </CardContent>
    </Card>
  );
};

// QR Payment Modal
const QrPaymentModal = ({ isOpen, onClose, invoice, qrData, loading }) => {
  const copyToClipboard = (text, label) => {
    navigator.clipboard.writeText(text);
    toast.success(`${label} copied to clipboard`);
  };

  return (
    <Dialog open={isOpen} onOpenChange={onClose}>
      <DialogContent className="max-w-md">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <QrCode className="w-5 h-5 text-primary" />
            Swiss QR Payment
          </DialogTitle>
          <DialogDescription>
            Scan with your banking app to pay
          </DialogDescription>
        </DialogHeader>

        {loading ? (
          <div className="flex items-center justify-center py-12">
            <Loader2 className="w-8 h-8 animate-spin text-primary" />
          </div>
        ) : qrData ? (
          <div className="space-y-4">
            {/* QR Code Display */}
            <div className="flex justify-center p-4 bg-white rounded-lg">
              <img 
                src={`data:image/svg+xml;base64,${qrData.qr_code_svg_base64}`}
                alt="Swiss QR Payment Code"
                className="w-64 h-64"
              />
            </div>

            {/* Payment Details */}
            <div className="space-y-3 p-4 bg-muted/50 rounded-lg">
              <div className="flex items-center justify-between">
                <span className="text-sm text-muted-foreground">Amount</span>
                <span className="font-bold text-lg">{formatCurrency(qrData.amount, qrData.currency)}</span>
              </div>
              
              <div className="flex items-center justify-between">
                <span className="text-sm text-muted-foreground">Reference</span>
                <div className="flex items-center gap-2">
                  <span className="font-mono text-sm">{qrData.document_number}</span>
                  <Button
                    variant="ghost"
                    size="icon"
                    className="h-6 w-6"
                    onClick={() => copyToClipboard(qrData.document_number, 'Reference')}
                  >
                    <Copy className="w-3 h-3" />
                  </Button>
                </div>
              </div>
              
              <div className="pt-2 border-t border-border">
                <p className="text-xs text-muted-foreground mb-1">Beneficiary</p>
                <p className="text-sm font-medium">{qrData.payment_info?.beneficiary}</p>
              </div>
              
              <div>
                <p className="text-xs text-muted-foreground mb-1">IBAN</p>
                <div className="flex items-center gap-2">
                  <span className="font-mono text-sm">{qrData.payment_info?.iban}</span>
                  <Button
                    variant="ghost"
                    size="icon"
                    className="h-6 w-6"
                    onClick={() => copyToClipboard(qrData.payment_info?.iban, 'IBAN')}
                  >
                    <Copy className="w-3 h-3" />
                  </Button>
                </div>
              </div>
            </div>

            <p className="text-xs text-muted-foreground text-center">
              Open your banking app, scan this QR code, and confirm the payment
            </p>
          </div>
        ) : (
          <div className="text-center py-8">
            <p className="text-muted-foreground">Failed to load QR code</p>
          </div>
        )}

        <DialogFooter>
          <Button variant="outline" onClick={onClose} className="w-full">
            Close
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
};

// Main Buyer Timeline Page
export const BuyerTimeline = () => {
  const { user, logout } = useAuth();
  const { getLogo, getCompanyName, t, formatCurrency: settingsFormatCurrency } = useSettings();
  const [loading, setLoading] = useState(true);
  const [events, setEvents] = useState([]);
  const [projectInfo, setProjectInfo] = useState(null);
  const [stages, setStages] = useState([]);
  const [confirmDialog, setConfirmDialog] = useState({ open: false, type: null, eventId: null });
  const [isProcessing, setIsProcessing] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');
  const [showSearch, setShowSearch] = useState(false);
  const [activeView, setActiveView] = useState('documents'); // 'documents', 'updates', 'team', or 'vault'
  const [unreadCount, setUnreadCount] = useState(0);
  const [teamMembers, setTeamMembers] = useState([]);
  const [constructionTimeline, setConstructionTimeline] = useState(null);
  const [vaultDocuments, setVaultDocuments] = useState([]);
  const [vaultLoading, setVaultLoading] = useState(false);
  
  // PDF Viewer state
  const [pdfViewer, setPdfViewer] = useState({ open: false, url: '', filename: '' });

  // Get agent branding
  const logoUrl = getLogo();
  const companyName = getCompanyName();
  
  // QR Payment Modal
  const [qrModal, setQrModal] = useState({ open: false, invoice: null, qrData: null, loading: false });

  // WebSocket for real-time updates
  const handleWebSocketMessage = useCallback((message) => {
    if (message.type === 'document_sent') {
      // Refresh data when new document is received
      fetchData();
    }
  }, []);
  
  const { isConnected } = useWebSocket(user?.user_id, handleWebSocketMessage);

  const fetchData = useCallback(async () => {
    try {
      const timelineRes = await fetch(`${API}/timeline`, { credentials: 'include', headers: getAuthHeaders() });
      
      if (timelineRes.ok) {
        const data = await timelineRes.json();
        setEvents(data.documents || []);
        setProjectInfo(data.project_info);
        
        if (data.project_info?.project_id) {
          // Fetch construction timeline (new workflow system)
          const ctRes = await fetch(`${API}/project-timeline`, { credentials: 'include', headers: getAuthHeaders() });
          if (ctRes.ok) {
            const ctData = await ctRes.json();
            setConstructionTimeline(ctData);
            // Use canonical field names directly
            if (ctData.steps && ctData.steps.length > 0) {
              const stepsFromTimeline = ctData.steps.map(step => ({
                step_id: step.step_id,
                title: step.title,
                status: step.status === 'approved' ? 'completed' : step.status,
                description: step.description,
                planned_date: step.planned_date,
                completed_at: step.completed_at,
                documents: step.documents
              }));
              setStages(stepsFromTimeline);
            }
          }
          
          // Fetch team members
          const teamRes = await fetch(`${API}/projects/${data.project_info.project_id}/team`, { credentials: 'include', headers: getAuthHeaders() });
          if (teamRes.ok) {
            const teamData = await teamRes.json();
            setTeamMembers(teamData);
          }
        }
      }
      
      // Fetch unread count
      const unreadRes = await fetch(`${API}/activities/unread-count`, { credentials: 'include', headers: getAuthHeaders() });
      if (unreadRes.ok) {
        const unreadData = await unreadRes.json();
        setUnreadCount(unreadData.unread_count);
      }
    } catch (error) {
      console.error('Failed to fetch data:', error);
      toast.error('Failed to load timeline');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  // Mark activities as seen when viewing Updates tab
  useEffect(() => {
    if (activeView === 'updates') {
      const markSeen = async () => {
        try {
          await fetch(`${API}/activities/mark-seen`, {
            method: 'POST',
            credentials: 'include'
          });
          setUnreadCount(0);
        } catch (error) {
          console.error('Failed to mark activities as seen:', error);
        }
      };
      markSeen();
    }
  }, [activeView]);

  // Fetch vault documents when vault tab is selected
  useEffect(() => {
    if (activeView === 'vault' && vaultDocuments.length === 0) {
      const fetchVaultDocuments = async () => {
        setVaultLoading(true);
        try {
          const res = await fetch(`${API}/vault/buyer`, { credentials: 'include', headers: getAuthHeaders() });
          if (res.ok) {
            const data = await res.json();
            setVaultDocuments(data);
          }
        } catch (error) {
          console.error('Failed to fetch vault documents:', error);
        } finally {
          setVaultLoading(false);
        }
      };
      fetchVaultDocuments();
    }
  }, [activeView, vaultDocuments.length]);

  const handleAction = async (eventId, action, comment = null) => {
    if (action === 'approve' || action === 'reject') {
      setConfirmDialog({ open: true, type: action, eventId });
      return;
    }

    if (action === 'confirm_payment') {
      setConfirmDialog({ open: true, type: 'payment', eventId });
      return;
    }

    if (action === 'request_change' && comment) {
      setIsProcessing(true);
      try {
        const res = await fetch(`${API}/documents/${eventId}/action`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json', ...getAuthHeaders() },
          credentials: 'include',
          body: JSON.stringify({ action: 'request_change', comment })
        });
        
        if (res.ok) {
          toast.success('Question sent to your agent');
          fetchData();
        } else {
          const err = await res.json();
          throw new Error(err.detail || 'Failed to send question');
        }
      } catch (error) {
        toast.error(error.message || 'Failed to send question');
      } finally {
        setIsProcessing(false);
      }
    }
  };

  const confirmAction = async () => {
    const { type, eventId } = confirmDialog;
    setIsProcessing(true);

    try {
      const res = await fetch(`${API}/documents/${eventId}/action`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', ...getAuthHeaders() },
        credentials: 'include',
        body: JSON.stringify({ action: type === 'payment' ? 'confirm_payment' : type })
      });

      if (res.ok) {
        const messages = {
          'approve': 'Quote approved! Invoice will be generated.',
          'reject': 'Quote declined',
          'payment': 'Payment confirmed'
        };
        toast.success(messages[type] || 'Action completed');
        fetchData();
      } else {
        const err = await res.json();
        throw new Error(err.detail || 'Action failed');
      }
    } catch (error) {
      toast.error(error.message || 'Action failed. Please try again.');
    } finally {
      setIsProcessing(false);
      setConfirmDialog({ open: false, type: null, eventId: null });
    }
  };

  const handleDownloadPdf = async (documentId) => {
    try {
      // Use source-pdf endpoint to download the original uploaded PDF
      const res = await fetch(`${API}/documents/${documentId}/source-pdf`, { credentials: 'include', headers: getAuthHeaders() });
      
      if (res.ok) {
        const blob = await res.blob();
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `document_${documentId}.pdf`;
        // Required for Safari and mobile browsers
        a.style.display = 'none';
        document.body.appendChild(a);
        a.click();
        // Cleanup
        setTimeout(() => {
          document.body.removeChild(a);
          window.URL.revokeObjectURL(url);
        }, 100);
      } else {
        throw new Error('Download failed');
      }
    } catch (error) {
      toast.error('Failed to download PDF');
    }
  };

  const handlePreviewPdf = (documentId, documentTitle) => {
    // Open the PDF in the in-app viewer
    setPdfViewer({
      open: true,
      url: `${API}/documents/${documentId}/source-pdf`,
      filename: documentTitle ? `${documentTitle}.pdf` : `document_${documentId}.pdf`
    });
  };

  const handleShowQrPayment = async (invoice) => {
    setQrModal({ open: true, invoice, qrData: null, loading: true });
    
    try {
      const res = await fetch(`${API}/documents/${invoice.id}/qr-code`, { credentials: 'include', headers: getAuthHeaders() });
      
      if (res.ok) {
        const qrData = await res.json();
        setQrModal(prev => ({ ...prev, qrData, loading: false }));
      } else {
        const err = await res.json();
        throw new Error(err.detail || 'Failed to load QR code');
      }
    } catch (error) {
      toast.error(error.message || 'Failed to load QR code');
      setQrModal(prev => ({ ...prev, loading: false }));
    }
  };

  const handleVaultPreview = (document) => {
    // Use the download endpoint for preview - it handles auth and file serving properly
    setPdfViewer({
      open: true,
      url: `${API}/vault/${document.vault_id}/download`,
      filename: document.original_filename || document.name || 'document.pdf'
    });
  };

  const handleVaultDownload = async (document) => {
    try {
      const res = await fetch(`${API}/vault/${document.vault_id}/download`, { credentials: 'include', headers: getAuthHeaders() });
      if (res.ok) {
        const blob = await res.blob();
        const url = window.URL.createObjectURL(blob);
        const a = window.document.createElement('a');
        a.href = url;
        a.download = document.original_filename || document.name || 'document';
        a.style.display = 'none';
        window.document.body.appendChild(a);
        a.click();
        setTimeout(() => {
          window.document.body.removeChild(a);
          window.URL.revokeObjectURL(url);
        }, 100);
      } else {
        throw new Error('Download failed');
      }
    } catch (error) {
      toast.error('Failed to download document');
    }
  };

  const currentPhase = stages.find(s => s.status === 'in_progress')?.name || 
                       (stages.every(s => s.status === 'completed') ? 'Complete' : 'Not started');

  const pendingCount = events.filter(e => e.actionRequired).length;

  const filteredEvents = events.filter(event => {
    if (!searchQuery.trim()) return true;
    const query = searchQuery.toLowerCase();
    return (
      event.title?.toLowerCase().includes(query) ||
      event.documentNumber?.toLowerCase().includes(query) ||
      event.status?.toLowerCase().includes(query) ||
      event.type?.toLowerCase().includes(query) ||
      event.supplierName?.toLowerCase().includes(query) ||
      event.summary?.toLowerCase().includes(query) ||
      formatDate(event.date)?.toLowerCase().includes(query) ||
      String(event.amount)?.includes(query)
    );
  });

  if (loading) {
    return (
      <div className="min-h-screen bg-background flex items-center justify-center">
        <div className="text-center">
          <Loader2 className="w-8 h-8 animate-spin text-primary mx-auto mb-4" />
          <p className="text-muted-foreground">Loading your timeline...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-background" data-testid="buyer-timeline">
      {/* Header */}
      <header className="sticky top-0 z-50 bg-background/80 backdrop-blur-xl border-b border-border">
        <div className="max-w-2xl mx-auto px-4 py-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              {logoUrl ? (
                <img 
                  src={logoUrl} 
                  alt={companyName} 
                  className="w-10 h-10 rounded-xl object-contain"
                />
              ) : (
                <div className="w-10 h-10 bg-primary rounded-xl flex items-center justify-center">
                  <Building2 className="w-5 h-5 text-primary-foreground" />
                </div>
              )}
              <div>
                <h1 className="font-semibold text-foreground">
                  {projectInfo?.unit_reference || t('buyer.yourProperty')}
                </h1>
                <p className="text-sm text-muted-foreground">
                  {companyName}
                </p>
              </div>
            </div>
            <div className="flex items-center gap-2">
              <Button
                variant="ghost"
                size="icon"
                onClick={() => setShowSearch(!showSearch)}
                className="h-9 w-9 rounded-lg"
                data-testid="search-toggle-btn"
              >
                <Search className="w-4 h-4" />
              </Button>
              <NotificationCenter />
              <ThemeToggle />
              <Button
                variant="ghost"
                size="icon"
                onClick={logout}
                className="h-9 w-9 rounded-lg text-muted-foreground hover:text-destructive"
                data-testid="logout-btn"
              >
                <LogOut className="w-4 h-4" />
              </Button>
            </div>
          </div>
          
          {/* Search Bar */}
          {showSearch && (
            <div className="mt-4 animate-fade-in">
              <div className="relative">
                <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
                <Input
                  type="text"
                  placeholder="Search quotes, invoices, amounts..."
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  className="pl-10 pr-10 h-11 rounded-xl"
                  autoFocus
                  data-testid="search-input"
                />
                {searchQuery && (
                  <Button
                    variant="ghost"
                    size="icon"
                    className="absolute right-1 top-1/2 -translate-y-1/2 h-8 w-8"
                    onClick={() => setSearchQuery('')}
                  >
                    <X className="w-4 h-4" />
                  </Button>
                )}
              </div>
              {searchQuery && (
                <p className="text-xs text-muted-foreground mt-2">
                  {filteredEvents.length} result{filteredEvents.length !== 1 ? 's' : ''} found
                </p>
              )}
            </div>
          )}
        </div>
      </header>

      {/* Main Content */}
      <main className="max-w-2xl mx-auto px-4 py-6">
        {/* User greeting */}
        <div className="mb-6">
          <p className="text-sm text-muted-foreground">Welcome back, {user?.name?.split(' ')[0]}</p>
          <div className="flex items-center gap-2 mt-1">
            <span className="text-xs px-2 py-0.5 rounded-full bg-muted text-muted-foreground">
              Current phase: {currentPhase}
            </span>
            {pendingCount > 0 && (
              <button
                onClick={() => {
                  // Find first actionable event and scroll to it
                  const firstActionable = filteredEvents.find(e => 
                    (e.type === 'quote' && e.status === 'Sent') ||
                    (e.type === 'invoice' && e.status === 'Sent')
                  );
                  if (firstActionable) {
                    const el = document.querySelector(`[data-testid="timeline-event-${firstActionable.id}"]`);
                    if (el) {
                      el.scrollIntoView({ behavior: 'smooth', block: 'center' });
                      el.classList.add('ring-2', 'ring-primary', 'ring-offset-2');
                      setTimeout(() => el.classList.remove('ring-2', 'ring-primary', 'ring-offset-2'), 2000);
                    }
                  }
                }}
                className="text-xs px-2 py-0.5 rounded-full bg-primary text-primary-foreground font-medium hover:bg-primary/90 transition-colors cursor-pointer"
                data-testid="action-needed-badge"
              >
                {pendingCount} action{pendingCount > 1 ? 's' : ''} needed
              </button>
            )}
          </div>
        </div>

        {/* Construction Progress */}
        <ConstructionPhaseCard stages={stages} />

        {/* View Tabs */}
        <div className="flex gap-1 p-1 bg-muted rounded-lg mb-6">
          <button
            onClick={() => setActiveView('documents')}
            className={cn(
              "flex-1 flex items-center justify-center gap-2 px-3 py-2.5 rounded-md text-sm font-medium transition-all",
              activeView === 'documents'
                ? "bg-background text-foreground shadow-sm"
                : "text-muted-foreground hover:text-foreground"
            )}
            data-testid="tab-documents"
          >
            <Receipt className="w-4 h-4" />
            <span className="hidden sm:inline">Quotes & Invoices</span>
            <span className="sm:hidden">Quotes</span>
            {pendingCount > 0 && (
              <span className="px-1.5 py-0.5 text-[10px] font-bold rounded-full bg-primary text-primary-foreground">
                {pendingCount}
              </span>
            )}
          </button>
          <button
            onClick={() => setActiveView('vault')}
            className={cn(
              "flex-1 flex items-center justify-center gap-2 px-3 py-2.5 rounded-md text-sm font-medium transition-all",
              activeView === 'vault'
                ? "bg-background text-foreground shadow-sm"
                : "text-muted-foreground hover:text-foreground"
            )}
            data-testid="tab-vault"
          >
            <FolderOpen className="w-4 h-4" />
            <span className="hidden sm:inline">Shared Files</span>
            <span className="sm:hidden">Files</span>
            {vaultDocuments.length > 0 && (
              <span className="px-1.5 py-0.5 text-[10px] font-bold rounded-full bg-muted-foreground/20 text-muted-foreground">
                {vaultDocuments.length}
              </span>
            )}
          </button>
          <button
            onClick={() => setActiveView('updates')}
            className={cn(
              "flex-1 flex items-center justify-center gap-2 px-3 py-2.5 rounded-md text-sm font-medium transition-all",
              activeView === 'updates'
                ? "bg-background text-foreground shadow-sm"
                : "text-muted-foreground hover:text-foreground"
            )}
            data-testid="tab-updates"
          >
            <Bell className="w-4 h-4" />
            <span className="hidden sm:inline">Updates</span>
            {unreadCount > 0 && (
              <span className="px-1.5 py-0.5 text-[10px] font-bold rounded-full bg-primary text-primary-foreground animate-pulse">
                {unreadCount}
              </span>
            )}
          </button>
          <button
            onClick={() => setActiveView('team')}
            className={cn(
              "flex-1 flex items-center justify-center gap-2 px-3 py-2.5 rounded-md text-sm font-medium transition-all",
              activeView === 'team'
                ? "bg-background text-foreground shadow-sm"
                : "text-muted-foreground hover:text-foreground"
            )}
            data-testid="tab-team"
          >
            <Users className="w-4 h-4" />
            <span className="hidden sm:inline">Team</span>
          </button>
        </div>

        {/* Documents View */}
        {activeView === 'documents' && (
          <div className="relative">
            {filteredEvents.length === 0 ? (
              <Card className="text-center py-12">
                <CardContent>
                  <FileText className="w-12 h-12 text-muted-foreground/30 mx-auto mb-4" />
                  <p className="text-muted-foreground">
                    {searchQuery ? 'No matching documents' : 'No documents yet'}
                  </p>
                  <p className="text-sm text-muted-foreground mt-1">
                    {searchQuery 
                      ? 'Try a different search term' 
                      : 'Your upgrade proposals and invoices will appear here'}
                  </p>
                </CardContent>
              </Card>
            ) : (
              filteredEvents.map(event => (
                <TimelineCard
                  key={event.id}
                  event={event}
                  onAction={handleAction}
                  onDownloadPdf={handleDownloadPdf}
                  onPreviewPdf={handlePreviewPdf}
                  onShowQrPayment={handleShowQrPayment}
                />
              ))
            )}
          </div>
        )}

        {/* Vault Documents View */}
        {activeView === 'vault' && (
          <div className="space-y-3" data-testid="buyer-vault-view">
            {vaultLoading ? (
              <div className="flex items-center justify-center py-12">
                <Loader2 className="w-8 h-8 animate-spin text-primary" />
              </div>
            ) : vaultDocuments.length === 0 ? (
              <Card className="text-center py-12">
                <CardContent>
                  <FolderOpen className="w-12 h-12 text-muted-foreground/30 mx-auto mb-4" />
                  <p className="text-muted-foreground font-medium">No shared files yet</p>
                  <p className="text-sm text-muted-foreground mt-1">
                    When your agent shares contracts, plans, or other documents with you, they'll appear here.
                  </p>
                </CardContent>
              </Card>
            ) : (
              <>
                {/* Section Header */}
                <div className="mb-4 pb-3 border-b border-border">
                  <p className="text-sm text-muted-foreground">
                    {vaultDocuments.length} file{vaultDocuments.length !== 1 ? 's' : ''} shared with you
                  </p>
                </div>
                
                {/* Action Required Documents First */}
                {vaultDocuments.filter(d => d.doc_type === 'action_required').length > 0 && (
                  <div className="mb-4">
                    <p className="text-xs font-semibold text-amber-600 dark:text-amber-400 uppercase tracking-wider mb-2 flex items-center gap-1.5">
                      <AlertTriangle className="w-3.5 h-3.5" />
                      Action Required
                    </p>
                    {vaultDocuments
                      .filter(d => d.doc_type === 'action_required')
                      .map(doc => (
                        <VaultDocumentCard
                          key={doc.vault_id}
                          document={doc}
                          onPreview={handleVaultPreview}
                          onDownload={handleVaultDownload}
                        />
                      ))}
                  </div>
                )}
                
                {/* General Documents */}
                {vaultDocuments.filter(d => d.doc_type !== 'action_required').length > 0 && (
                  <div>
                    {vaultDocuments.filter(d => d.doc_type === 'action_required').length > 0 && (
                      <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wider mb-2">
                        All Documents
                      </p>
                    )}
                    {vaultDocuments
                      .filter(d => d.doc_type !== 'action_required')
                      .map(doc => (
                        <VaultDocumentCard
                          key={doc.vault_id}
                          document={doc}
                          onPreview={handleVaultPreview}
                          onDownload={handleVaultDownload}
                        />
                      ))}
                  </div>
                )}
              </>
            )}
          </div>
        )}

        {/* Updates/Feed View */}
        {activeView === 'updates' && (
          <Feed isAgent={false} embedded={true} />
        )}

        {/* Team View */}
        {activeView === 'team' && (
          <div className="space-y-3">
            {teamMembers.length === 0 ? (
              <Card className="text-center py-12">
                <CardContent>
                  <Users className="w-12 h-12 text-muted-foreground/30 mx-auto mb-4" />
                  <p className="text-muted-foreground">No team contacts yet</p>
                  <p className="text-sm text-muted-foreground mt-1">
                    Your agent will add team contacts here
                  </p>
                </CardContent>
              </Card>
            ) : (
              teamMembers.map(member => (
                <Card key={member.member_id} className="border-border" data-testid={`team-member-${member.member_id}`}>
                  <CardContent className="py-4">
                    <div className="flex items-start justify-between">
                      <div className="flex items-start gap-3">
                        <div className="w-10 h-10 rounded-full bg-primary/10 flex items-center justify-center flex-shrink-0">
                          <span className="text-primary font-semibold text-sm">
                            {(member.company_name || member.name || '').split(' ').map(n => n[0]).join('').slice(0, 2)}
                          </span>
                        </div>
                        <div>
                          <h3 className="font-medium text-foreground">{member.company_name || member.name}</h3>
                          {member.contact_name && (
                            <p className="text-sm text-muted-foreground">{member.contact_name}</p>
                          )}
                          <p className="text-sm text-primary">{member.role}</p>
                          <div className="flex items-center gap-4 mt-2 flex-wrap">
                            {member.email && (
                              <a 
                                href={`mailto:${member.email}`}
                                className="flex items-center gap-1.5 text-sm text-muted-foreground hover:text-foreground"
                              >
                                <Mail className="w-3.5 h-3.5" />
                                <span>{member.email}</span>
                              </a>
                            )}
                            {member.phone && (
                              <a 
                                href={`tel:${member.phone}`}
                                className="flex items-center gap-1.5 text-sm text-muted-foreground hover:text-foreground"
                              >
                                <Phone className="w-3.5 h-3.5" />
                                <span>{member.phone}</span>
                              </a>
                            )}
                          </div>
                          {member.notes && (
                            <p className="text-sm text-muted-foreground mt-2">{member.notes}</p>
                          )}
                        </div>
                      </div>
                    </div>
                  </CardContent>
                </Card>
              ))
            )}
          </div>
        )}
      </main>

      {/* Confirmation Dialog */}
      <Dialog open={confirmDialog.open} onOpenChange={(open) => !open && setConfirmDialog({ open: false, type: null, eventId: null })}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>
              {confirmDialog.type === 'approve' && 'Approve this quote?'}
              {confirmDialog.type === 'reject' && 'Decline this quote?'}
              {confirmDialog.type === 'payment' && 'Confirm payment?'}
            </DialogTitle>
            <DialogDescription>
              {confirmDialog.type === 'approve' && 'Once approved, your agent will generate an invoice for payment.'}
              {confirmDialog.type === 'reject' && 'This will decline the upgrade proposal. You can request changes instead if needed.'}
              {confirmDialog.type === 'payment' && 'Please confirm you have completed the bank transfer. Your agent will verify the payment.'}
            </DialogDescription>
          </DialogHeader>
          <DialogFooter className="flex-col sm:flex-row gap-2">
            <Button
              variant="outline"
              onClick={() => setConfirmDialog({ open: false, type: null, eventId: null })}
              disabled={isProcessing}
            >
              Cancel
            </Button>
            <Button
              onClick={confirmAction}
              disabled={isProcessing}
              className={cn(
                confirmDialog.type === 'reject' && "bg-destructive hover:bg-destructive/90",
                confirmDialog.type === 'approve' && "bg-emerald-600 hover:bg-emerald-700"
              )}
            >
              {isProcessing ? (
                <Loader2 className="w-4 h-4 animate-spin" />
              ) : (
                <>
                  {confirmDialog.type === 'approve' && 'Yes, Approve'}
                  {confirmDialog.type === 'reject' && 'Yes, Decline'}
                  {confirmDialog.type === 'payment' && 'Confirm Payment'}
                </>
              )}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* QR Payment Modal */}
      <QrPaymentModal
        isOpen={qrModal.open}
        onClose={() => setQrModal({ open: false, invoice: null, qrData: null, loading: false })}
        invoice={qrModal.invoice}
        qrData={qrModal.qrData}
        loading={qrModal.loading}
      />

      {/* PDF Viewer Modal */}
      <PdfViewer
        isOpen={pdfViewer.open}
        onClose={() => setPdfViewer({ open: false, url: '', filename: '' })}
        url={pdfViewer.url}
        filename={pdfViewer.filename}
      />
    </div>
  );
};
