'use client';

// Error boundary a nivel de segmento raíz (App Router). Atrapa errores de
// runtime de CUALQUIER página renderizada bajo el layout y muestra un mensaje
// en vez de dejar la pantalla en blanco (el síntoma clásico de "la página se
// perdió"). Se renderiza DENTRO del layout, así que el shell/sidebar siguen y
// el usuario puede navegar a otra sección. Los errores del propio layout raíz
// los cubre `global-error.tsx`.

import { useEffect } from 'react';
import Link from 'next/link';

import { Button } from '@/components/ui/button';
import { Icon } from '@/components/ui/icon';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { capturarExcepcion } from '@/lib/telemetria';

export default function Error({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    // Queda en la consola del renderer (visible en DevTools / `debug:packaged`).
    console.error('[error-boundary]', error);
    // Y se reporta a Sentry (no-op fuera de Electron / sin DSN).
    capturarExcepcion(error, { boundary: 'segment', digest: error?.digest });
  }, [error]);

  return (
    <div className="mx-auto max-w-lg space-y-4 py-12">
      <div className="flex items-center gap-2 text-lg font-medium">
        <Icon icon="ph:warning-octagon-light" className="size-5 text-destructive" />
        Algo salió mal en esta sección
      </div>
      <p className="text-sm text-muted-foreground">
        Ocurrió un error al mostrar esta página. Puedes reintentar o volver al inicio; el resto de
        la app sigue funcionando.
      </p>
      {error?.message && (
        <Alert variant="destructive">
          <AlertDescription className="wrap-break-word font-mono text-xs">
            {error.message}
          </AlertDescription>
        </Alert>
      )}
      <div className="flex gap-2">
        <Button onClick={reset}>
          <Icon icon="ph:arrow-clockwise-light" className="size-4" /> Reintentar
        </Button>
        <Button variant="outline" asChild>
          <Link href="/">
            <Icon icon="ph:squares-four-light" className="size-4" /> Ir al inicio
          </Link>
        </Button>
      </div>
    </div>
  );
}
