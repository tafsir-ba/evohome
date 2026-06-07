import { Loader2, Check, AlertCircle } from 'lucide-react';

export const GanttSaveIndicator = ({ saving, dirty }) => {
  if (saving) {
    return (
      <span className="inline-flex items-center gap-1.5 text-xs text-muted-foreground">
        <Loader2 className="h-3 w-3 animate-spin" />
        Saving…
      </span>
    );
  }

  if (dirty) {
    return (
      <span className="inline-flex items-center gap-1.5 text-xs text-amber-600 dark:text-amber-500">
        <AlertCircle className="h-3 w-3" />
        Unsaved changes
      </span>
    );
  }

  return (
    <span className="inline-flex items-center gap-1.5 text-xs text-muted-foreground">
      <Check className="h-3 w-3 text-emerald-600 dark:text-emerald-500" />
      All changes saved
    </span>
  );
};
