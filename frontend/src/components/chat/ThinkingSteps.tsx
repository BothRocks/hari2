import { Loader2 } from 'lucide-react';

export interface ThinkingStep {
  step: string;
  message: string;
  isError?: boolean;
}

interface ThinkingStepsProps {
  steps: ThinkingStep[];
  isLoading?: boolean;
}

export function ThinkingSteps({ steps, isLoading }: ThinkingStepsProps) {
  if (steps.length === 0) {
    return null;
  }

  return (
    <div className="space-y-1 text-sm mb-3 p-3 bg-muted/50 rounded-lg">
      {steps.map((step, i) => (
        <div
          key={i}
          className={`flex items-center gap-2 ${
            step.isError ? 'text-yellow-600' : 'text-muted-foreground'
          }`}
        >
          {isLoading && i === steps.length - 1 ? (
            <Loader2 className="h-3 w-3 animate-spin" />
          ) : (
            <span className="w-3 h-3 text-center">
              {step.isError ? '!' : '✓'}
            </span>
          )}
          <span>{step.message}</span>
        </div>
      ))}
    </div>
  );
}
