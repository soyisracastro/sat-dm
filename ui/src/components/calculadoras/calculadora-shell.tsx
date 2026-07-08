import Link from 'next/link';
import type { ReactNode } from 'react';

import { Card, CardContent } from '@/components/ui/card';
import { Icon } from '@/components/ui/icon';

interface CalculadoraShellProps {
  titulo: string;
  descripcion: ReactNode;
  /** Formulario de captura; se renderiza dentro de una Card a la izquierda. */
  formulario: ReactNode;
  /** Columna de resultados (derecha; abajo en pantallas chicas). */
  resultados: ReactNode;
  /** true → apila form y resultados a lo ancho (formularios anchos, p. ej. PTU). */
  unaColumna?: boolean;
  /** Muestra un indicador sutil de "Calculando…" junto al título. */
  calculando?: boolean;
  /** Acciones del encabezado (p. ej. botón de exportar), alineadas a la derecha. */
  acciones?: ReactNode;
}

/**
 * Encabezado + layout de dos columnas de las páginas de calculadoras:
 * link de regreso al índice, título, descripción y grid responsivo con el
 * formulario en Card a la izquierda y los resultados a la derecha.
 */
export function CalculadoraShell({
  titulo,
  descripcion,
  formulario,
  resultados,
  unaColumna = false,
  calculando = false,
  acciones,
}: CalculadoraShellProps) {
  return (
    <div className="space-y-6">
      <div className="space-y-2">
        <Link
          href="/calculadoras"
          className="inline-flex items-center gap-1.5 text-sm font-semibold text-muted-foreground transition-colors hover:text-primary"
        >
          <Icon icon="ph:arrow-left-light" className="size-4" />
          Calculadoras
        </Link>
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div className="space-y-1.5">
            <h1 className="flex items-center gap-3 text-[1.75rem] leading-tight font-extrabold tracking-tight">
              {titulo}
              {calculando && (
                <span className="inline-flex items-center gap-1 text-xs font-normal text-muted-foreground">
                  <Icon icon="ph:circle-notch-light" className="size-3.5 animate-spin" />
                  Calculando…
                </span>
              )}
            </h1>
            <p className="max-w-3xl leading-relaxed text-muted-foreground">{descripcion}</p>
          </div>
          {acciones && <div className="shrink-0">{acciones}</div>}
        </div>
      </div>

      <div
        className={
          unaColumna
            ? 'space-y-6'
            : 'grid grid-cols-1 items-start gap-6 xl:grid-cols-[minmax(0,26rem)_minmax(0,1fr)]'
        }
      >
        <Card>
          <CardContent>{formulario}</CardContent>
        </Card>
        <div className="min-w-0 space-y-4">{resultados}</div>
      </div>
    </div>
  );
}

/** Placeholder de la columna de resultados mientras no hay cálculo. */
export function SinResultado({
  restaurando = false,
  icono,
  mensaje,
}: {
  restaurando?: boolean;
  /** Icono Phosphor de la calculadora (p. ej. "ph:gift-light"). */
  icono?: string;
  /** Mensaje personalizado cuando no hay cálculo (por defecto, el genérico). */
  mensaje?: string;
}) {
  return (
    <Card>
      <CardContent className="flex min-h-70 flex-col items-center justify-center gap-3 py-10 text-center">
        {icono && <Icon icon={icono} className="size-8 text-muted-foreground/50" />}
        <p className="max-w-xs text-sm leading-relaxed text-muted-foreground">
          {restaurando
            ? 'Cargando el último cálculo de la empresa…'
            : (mensaje ?? 'Captura los datos para ver el cálculo en tiempo real.')}
        </p>
      </CardContent>
    </Card>
  );
}
