'use client';

import { cn } from '@/lib/utils';
import { Icon } from '@/components/ui/icon';

interface WizardStepsProps {
  pasos: string[];
  /** Índice (0-based) del paso actual. Los anteriores se pintan como completados. */
  actual: number;
}

/**
 * Barra de pasos de los asistentes (Renovar e.firma / Generar CSD): círculo con
 * número (o check si ya pasó) + etiqueta corta, uno por paso.
 */
export function WizardSteps({ pasos, actual }: WizardStepsProps) {
  return (
    <div className="flex items-center gap-1.5">
      {pasos.map((label, i) => {
        const done = i < actual;
        const on = i === actual;
        return (
          <div key={label} className="flex min-w-0 flex-1 items-center gap-1.5">
            <span
              className={cn(
                'flex size-6 shrink-0 items-center justify-center rounded-full border text-xs font-bold',
                done && 'border-transparent bg-success/10 text-success',
                on && 'border-primary bg-primary text-primary-foreground',
                !done && !on && 'border-border bg-secondary text-muted-foreground',
              )}
            >
              {done ? <Icon icon="ph:check-light" className="size-3.5" /> : i + 1}
            </span>
            <span
              className={cn(
                'truncate text-[11.5px] font-semibold',
                on ? 'text-foreground' : 'text-muted-foreground',
              )}
            >
              {label}
            </span>
          </div>
        );
      })}
    </div>
  );
}
