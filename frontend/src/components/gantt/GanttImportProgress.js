import { useEffect, useState } from 'react';
import { Progress } from '../ui/progress';
import { Loader2, Check } from 'lucide-react';
import { cn } from '../../lib/utils';

/**
 * Stepped progress while a single async operation runs (upload or extract).
 * Advances through labels on an interval; completes when active becomes false.
 */
export const GanttImportProgress = ({ active, steps, label }) => {
  const [stepIndex, setStepIndex] = useState(0);
  const [completed, setCompleted] = useState(false);

  useEffect(() => {
    if (!active) {
      if (steps.length > 0) {
        setStepIndex(steps.length - 1);
        setCompleted(true);
      }
      return;
    }

    setStepIndex(0);
    setCompleted(false);

    const interval = setInterval(() => {
      setStepIndex((prev) => {
        const cap = Math.max(0, steps.length - 2);
        return prev < cap ? prev + 1 : prev;
      });
    }, 1800);

    return () => clearInterval(interval);
  }, [active, steps]);

  if (!active && !completed) return null;

  const progressValue =
    steps.length <= 1
      ? active
        ? 50
        : 100
      : ((stepIndex + (active ? 0.35 : 1)) / steps.length) * 100;

  const currentStep = steps[stepIndex] || steps[steps.length - 1];

  return (
    <div className="rounded-lg border bg-muted/30 p-4 space-y-3">
      <div className="flex items-center gap-2 text-sm font-medium">
        {active ? (
          <Loader2 className="h-4 w-4 animate-spin text-primary shrink-0" />
        ) : (
          <Check className="h-4 w-4 text-emerald-600 shrink-0" />
        )}
        <span>{label}</span>
      </div>
      <Progress value={Math.min(100, progressValue)} className="h-2" />
      <p className="text-sm text-muted-foreground">{currentStep}</p>
      <ul className="space-y-1">
        {steps.map((step, index) => (
          <li
            key={step}
            className={cn(
              'text-xs flex items-center gap-2',
              index < stepIndex || (!active && completed)
                ? 'text-muted-foreground'
                : index === stepIndex
                  ? 'text-foreground font-medium'
                  : 'text-muted-foreground/60'
            )}
          >
            <span
              className={cn(
                'h-1.5 w-1.5 rounded-full shrink-0',
                index < stepIndex || (!active && completed)
                  ? 'bg-emerald-500'
                  : index === stepIndex && active
                    ? 'bg-primary animate-pulse'
                    : 'bg-muted-foreground/30'
              )}
            />
            {step}
          </li>
        ))}
      </ul>
    </div>
  );
};
