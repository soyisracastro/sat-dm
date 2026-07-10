import type { ReactNode } from 'react';

import { Icon } from '@/components/ui/icon';
import { cn } from '@/lib/utils';

interface PanelInicioProps {
  titulo: string;
  icono: string;
  /** Texto discreto a la derecha del título (p. ej. "últimos 6 meses"). */
  sub?: string;
  /** Nodo a la derecha (p. ej. botón "Ver historial"); excluye a `sub`. */
  accion?: ReactNode;
  className?: string;
  children: ReactNode;
}

/** Tarjeta base del Panel Ejecutivo: encabezado con icono + contenido. */
export function PanelInicio({
  titulo,
  icono,
  sub,
  accion,
  className,
  children,
}: PanelInicioProps) {
  return (
    <section className={cn('rounded-xl border bg-card p-5', className)}>
      <div className="mb-4 flex items-center justify-between gap-3">
        <h2 className="flex items-center gap-2 text-sm font-bold tracking-tight">
          <Icon icon={icono} className="size-4 shrink-0 text-muted-foreground" />
          {titulo}
        </h2>
        {sub && (
          <span className="text-[11px] font-medium text-muted-foreground/80">
            {sub}
          </span>
        )}
        {accion}
      </div>
      {children}
    </section>
  );
}

/** Estado vacío compacto para los paneles (sin datos aún). */
export function PanelVacio({
  icono,
  children,
}: {
  icono: string;
  children: ReactNode;
}) {
  return (
    <div className="flex flex-col items-center gap-2 py-8 text-center">
      <Icon icon={icono} className="size-6 text-muted-foreground/50" />
      <p className="max-w-xs text-[13px] text-muted-foreground">{children}</p>
    </div>
  );
}
