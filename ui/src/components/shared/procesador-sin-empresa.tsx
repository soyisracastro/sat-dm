'use client';

import Link from 'next/link';

import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert';
import { Button } from '@/components/ui/button';
import { Icon } from '@/components/ui/icon';

interface Props {
  /**
   * `true` cuando el catálogo ya cargó y confirmó que no hay empresa activa.
   * Mientras carga (`false`) se muestra un spinner para no parpadear el aviso.
   */
  listo: boolean;
}

/**
 * Estado "sin empresa activa" de los procesadores de comprobantes. El buffer
 * del procesador vive POR empresa en el agente, así que sin empresa activa no
 * hay nada que cargar ni consultar.
 */
export function ProcesadorSinEmpresa({ listo }: Props) {
  if (!listo) {
    return (
      <div className="flex items-center justify-center gap-2 py-10 text-sm text-muted-foreground">
        <Icon icon="ph:circle-notch-light" className="size-4 animate-spin" />
        Cargando empresas…
      </div>
    );
  }

  return (
    <Alert variant="warning">
      <Icon icon="ph:warning-light" className="size-4" />
      <AlertTitle>No hay empresa activa</AlertTitle>
      <AlertDescription className="space-y-3">
        <p>
          El procesador guarda los comprobantes por empresa: activa una para
          cargar y consultar sus XMLs.
        </p>
        <Button variant="outline" size="sm" asChild>
          <Link href="/empresas">
            <Icon icon="ph:buildings-light" className="size-4" />
            Ir a Empresas
          </Link>
        </Button>
      </AlertDescription>
    </Alert>
  );
}
