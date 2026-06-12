'use client';

import { useServer } from '@/providers/server-provider';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Icon } from '@/components/ui/icon';

/**
 * Banner no-intrusivo con el estado del navegador de descargas (Chromium).
 * El agente lo descarga en background al arrancar (primera vez o tras una
 * actualización); mientras tanto avisamos para que el usuario sepa por qué
 * una descarga del portal puede tardar en arrancar. Si está listo (o el
 * estado aún no se conoce), no se muestra nada.
 */
export function NavegadorStatusBanner() {
  const { navegador } = useServer();

  if (navegador?.estado === 'instalando') {
    return (
      <Alert>
        <AlertDescription className="flex items-center gap-2">
          <Icon icon="ph:circle-notch-light" className="size-4 shrink-0 animate-spin" />
          Preparando el navegador de descargas (~170 MB, solo la primera vez).
          Esto puede tardar unos minutos…
        </AlertDescription>
      </Alert>
    );
  }

  if (navegador?.estado === 'error') {
    return (
      <Alert variant="warning">
        <AlertDescription>
          No se pudo preparar el navegador de descargas. Verifica tu conexión a
          internet; se reintentará automáticamente al iniciar una descarga.
          {navegador.detalle ? ` Detalle: ${navegador.detalle}` : ''}
        </AlertDescription>
      </Alert>
    );
  }

  return null;
}
