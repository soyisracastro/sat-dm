'use client';

import { cn } from '@/lib/utils';
import { Icon } from '@/components/ui/icon';

export interface FaseItem {
  /** Etiqueta visible del renglón. */
  label: string;
  /** Fases del SSE que caen en este renglón (varias fases → un mismo paso visual). */
  fases: string[];
}

interface FasesProgresoProps {
  items: FaseItem[];
  /** Última fase emitida por el job (useJob().fase). */
  faseActual: string | null;
  /** Estado del job: con 'done' todos los renglones se marcan completados. */
  estado: 'idle' | 'iniciando' | 'corriendo' | 'captcha' | 'done' | 'error' | 'cancelled';
}

/**
 * Checklist de progreso de un trámite (jobs de Certifica): spinner en el paso en
 * curso, check en los pasados, tenue en los futuros. El índice actual se deriva
 * de a qué renglón pertenece la última fase SSE recibida.
 */
export function FasesProgreso({ items, faseActual, estado }: FasesProgresoProps) {
  const terminado = estado === 'done';
  let actual = faseActual
    ? items.findIndex((it) => it.fases.includes(faseActual))
    : -1;
  if (actual === -1 && (estado === 'corriendo' || estado === 'iniciando')) actual = 0;

  return (
    <div className="flex flex-col gap-1 py-2">
      {items.map((it, idx) => {
        const done = terminado || idx < actual;
        const run = !terminado && idx === actual && (estado === 'corriendo' || estado === 'iniciando');
        return (
          <div
            key={it.label}
            className={cn(
              'flex items-center gap-3 rounded-lg px-3 py-2.5 text-[13px] transition-colors',
              run && 'bg-accent font-semibold text-foreground',
              done && !run && 'text-muted-foreground',
              !done && !run && 'text-muted-foreground/50',
            )}
          >
            <span className="flex size-5 shrink-0 items-center justify-center">
              {done ? (
                <Icon icon="ph:check-circle-light" className="size-4.5 text-success" />
              ) : run ? (
                <Icon icon="ph:circle-notch-light" className="size-4 animate-spin text-primary" />
              ) : (
                <span className="size-2 rounded-full border-2 border-input" />
              )}
            </span>
            <span>{it.label}</span>
          </div>
        );
      })}
    </div>
  );
}
