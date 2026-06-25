'use client';

import type { ReactNode } from 'react';

import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert';
import { Button } from '@/components/ui/button';
import { Icon } from '@/components/ui/icon';
import { cn } from '@/lib/utils';

interface ProcesadorEstadoProps {
  /** Datos agregados ya cargados. `null` = el agente aún no respondió. */
  stats: unknown | null;
  /** Mensaje de error de la última carga (o `null`). */
  error: string | null;
  /** ¿Hay una carga en curso? Deshabilita el botón de reintento. */
  loading: boolean;
  /** Reintenta la carga (normalmente el `recargar` del hook). */
  onReintentar: () => void;
  children: ReactNode;
}

/**
 * Envuelve el cuerpo de un procesador (CFDI / Pagos / Nómina) con el chrome de
 * carga y error, para que la página nunca quede en blanco mientras el agente
 * no responde.
 *
 * - `stats === null` sin error → spinner ("Preparando el procesador…").
 * - `stats === null` con error → aviso accionable + "Reintentar". Típico en
 *   Windows la primera vez, cuando el antivirus analiza la app sin firma y la
 *   petición inicial se cae o cuelga.
 * - en cuanto hay `stats` → renderiza el contenido real.
 *
 * El hook ya reintenta solo con backoff; el botón es el respaldo manual.
 */
export function ProcesadorEstado({
  stats,
  error,
  loading,
  onReintentar,
  children,
}: ProcesadorEstadoProps) {
  if (stats === null && !error) {
    return (
      <div className="flex flex-col items-center justify-center gap-3 py-20 text-center text-muted-foreground">
        <Icon icon="ph:circle-notch-light" className="size-8 animate-spin" />
        <p className="text-sm">Preparando el procesador…</p>
      </div>
    );
  }

  if (stats === null && error) {
    return (
      <Alert variant="warning">
        <Icon icon="ph:warning-light" />
        <AlertTitle>No se pudo abrir el procesador</AlertTitle>
        <AlertDescription className="space-y-3">
          <p>
            El motor de la app tardó en responder. En Windows esto puede pasar la
            primera vez, mientras el antivirus revisa la aplicación; suele
            resolverse en unos segundos.
          </p>
          <Button
            variant="outline"
            size="sm"
            onClick={onReintentar}
            disabled={loading}
          >
            <Icon
              icon="ph:arrow-clockwise-light"
              className={cn('size-4', loading && 'animate-spin')}
            />
            Reintentar
          </Button>
        </AlertDescription>
      </Alert>
    );
  }

  return <>{children}</>;
}
