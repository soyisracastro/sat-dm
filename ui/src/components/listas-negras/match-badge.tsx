'use client';

import { Icon } from '@/components/ui/icon';
import { cn } from '@/lib/utils';
import type { ListaNegraMatch } from '@/lib/types';

/**
 * Etiqueta corta consistente con la columna `*_en_lista_negra` del backend.
 * Coincide con `clasificar()` en `utils/listas_negras.py`.
 */
export type EtiquetaLista = 'EFOS' | 'Aclarado' | '69' | 'Limpio';

export function etiquetaDeMatch(m: ListaNegraMatch): EtiquetaLista {
  if (m.en_lista_69b && (m.situacion_69b === 'Definitivo' || m.situacion_69b === 'Presunto')) {
    return 'EFOS';
  }
  if (m.en_lista_69b) return 'Aclarado';
  if (m.en_lista_69) return '69';
  return 'Limpio';
}

/**
 * Paleta tonal compartida para badges de estado (listas negras + estatus SAT).
 * Cualquier badge que represente un veredicto del SAT debe consumir esta
 * paleta para que los colores sean consistentes entre vistas.
 */
export type Tono = 'rojo' | 'amber' | 'verde' | 'neutro';

export const TONO_CLASES: Record<Tono, string> = {
  rojo: 'border-red-300 bg-red-50 text-red-700 dark:border-red-800 dark:bg-red-950/40 dark:text-red-300',
  amber: 'border-amber-300 bg-amber-50 text-amber-700 dark:border-amber-800 dark:bg-amber-950/40 dark:text-amber-300',
  verde: 'border-green-300 bg-green-50 text-green-700 dark:border-green-800 dark:bg-green-950/40 dark:text-green-300',
  neutro: 'border-border bg-muted text-muted-foreground',
};

/** Clase base común para todos los badges tonales. */
export const TONO_BASE_CLASE =
  'inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-xs font-medium';

const ESTILOS: Record<EtiquetaLista, { label: string; icon: string; tono: Tono }> = {
  EFOS:     { label: 'EFOS',     icon: 'ph:warning-light',        tono: 'rojo' },
  Aclarado: { label: 'Aclarado', icon: 'ph:warning-circle-light', tono: 'amber' },
  '69':     { label: 'Art. 69',  icon: 'ph:warning-circle-light', tono: 'amber' },
  Limpio:   { label: 'Limpio',   icon: 'ph:shield-check-light',   tono: 'verde' },
};

interface Props {
  etiqueta: EtiquetaLista;
  className?: string;
}

export function MatchBadge({ etiqueta, className }: Props) {
  const e = ESTILOS[etiqueta];
  return (
    <span className={cn(TONO_BASE_CLASE, TONO_CLASES[e.tono], className)}>
      <Icon icon={e.icon} className="size-3 shrink-0" />
      {e.label}
    </span>
  );
}
