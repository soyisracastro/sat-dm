'use client';

import { cn } from '@/lib/utils';

interface ToggleRowProps {
  titulo: string;
  descripcion?: string;
  activo: boolean;
  onCambiar: (valor: boolean) => void;
  /** id para asociar la fila con un `<Label>` externo si hiciera falta. */
  id?: string;
}

/**
 * Fila conmutable de las calculadoras: toda la fila es clicable y se resalta
 * (borde primario + fondo acento) cuando está activa. El interruptor es
 * puramente visual (`aria-hidden`); el control accesible es el propio botón
 * (`role="switch"` + `aria-checked`), así evitamos anidar el `<button>` del
 * Switch de Radix dentro de otro `<button>`.
 */
export function ToggleRow({ titulo, descripcion, activo, onCambiar, id }: ToggleRowProps) {
  return (
    <button
      type="button"
      role="switch"
      id={id}
      aria-checked={activo}
      onClick={() => onCambiar(!activo)}
      className={cn(
        'flex w-full items-center justify-between gap-4 rounded-lg border px-3.5 py-3 text-left',
        'transition-colors outline-none focus-visible:border-ring focus-visible:ring-[3px] focus-visible:ring-ring/50',
        activo ? 'border-primary bg-accent' : 'border-border hover:border-primary/60',
      )}
    >
      <span className="min-w-0 space-y-0.5">
        <span className="block text-[13.5px] font-bold tracking-tight text-foreground">
          {titulo}
        </span>
        {descripcion && (
          <span className="block text-xs leading-snug text-muted-foreground">
            {descripcion}
          </span>
        )}
      </span>
      <span
        aria-hidden
        data-state={activo ? 'checked' : 'unchecked'}
        className={cn(
          'inline-flex h-[1.15rem] w-8 shrink-0 items-center rounded-full border border-transparent shadow-xs transition-colors',
          activo ? 'bg-primary' : 'bg-input dark:bg-input/80',
        )}
      >
        <span
          className={cn(
            'pointer-events-none block size-4 rounded-full bg-background shadow-sm transition-transform',
            activo
              ? 'translate-x-[calc(100%-2px)] dark:bg-primary-foreground'
              : 'translate-x-0 dark:bg-foreground',
          )}
        />
      </span>
    </button>
  );
}
