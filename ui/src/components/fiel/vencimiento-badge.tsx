'use client';

import { cn } from '@/lib/utils';
import { Icon } from '@/components/ui/icon';
import { semaforoVencimiento, type EstadoVencimiento } from '@/lib/vencimiento';

// Estilos del semáforo (mismo criterio que TodoConta: verde >30d, amarillo ≤30d, rojo ≤5d/vencida).
const ESTILO_BADGE: Record<EstadoVencimiento, string> = {
  verde:
    'border-green-200 bg-green-50 text-green-700 dark:border-green-900 dark:bg-green-950 dark:text-green-400',
  amarillo:
    'border-amber-200 bg-amber-50 text-amber-800 dark:border-amber-900 dark:bg-amber-950 dark:text-amber-400',
  rojo: 'border-red-200 bg-red-50 text-red-700 dark:border-red-900 dark:bg-red-950 dark:text-red-400',
};

const ESTILO_PUNTO: Record<EstadoVencimiento, string> = {
  verde: 'bg-green-500',
  amarillo: 'bg-amber-500',
  rojo: 'bg-red-500',
};

const ICONO: Record<EstadoVencimiento, string> = {
  verde: 'ph:calendar-check-light',
  amarillo: 'ph:calendar-light',
  rojo: 'ph:warning-light',
};

/**
 * Badge con el semáforo de vencimiento de la e.firma. Devuelve null si no hay
 * fecha válida (p. ej. empresa solo-CIEC). `compact` muestra solo el ícono + días.
 */
export function VencimientoBadge({
  vencimiento,
  className,
}: {
  vencimiento?: string | null;
  className?: string;
}) {
  const s = semaforoVencimiento(vencimiento);
  if (!s) return null;
  return (
    <span
      className={cn(
        'inline-flex w-fit items-center gap-1 rounded-full border px-2 py-0.5 text-xs font-medium',
        ESTILO_BADGE[s.estado],
        className,
      )}
      title={`Vence el ${s.fecha}`}
    >
      <Icon icon={ICONO[s.estado]} className="size-3 shrink-0" />
      {s.label}
    </span>
  );
}

/** Punto de color del semáforo (para listas compactas). Null si no hay fecha. */
export function VencimientoDot({
  vencimiento,
  className,
}: {
  vencimiento?: string | null;
  className?: string;
}) {
  const s = semaforoVencimiento(vencimiento);
  if (!s) return null;
  return (
    <span
      className={cn('inline-block size-2 shrink-0 rounded-full', ESTILO_PUNTO[s.estado], className)}
      title={`${s.label} (vence ${s.fecha})`}
    />
  );
}
